from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from council.schemas import SchemaModel, strict_json_schema

from .base import (
    AttemptLog,
    BaseProvider,
    ProviderResult,
    ProviderUnavailable,
    classify_failure,
)


def _extract_codex_usage(stdout: str) -> tuple[dict[str, int], bool]:
    selected: dict | None = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        usage = event.get("usage") or event.get("token_usage")
        if isinstance(usage, dict):
            selected = usage
    if selected is None:
        return {
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "cache_write_tokens": 0,
            "output_tokens": 0,
        }, False
    total_input = int(selected.get("input_tokens", selected.get("input", 0)) or 0)
    cached = int(selected.get("cached_input_tokens", selected.get("cached_input", 0)) or 0)
    return {
        "input_tokens": max(0, total_input - cached),
        "cached_input_tokens": cached,
        "cache_write_tokens": 0,
        "output_tokens": int(selected.get("output_tokens", selected.get("output", 0)) or 0),
    }, True


def _subscription_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "AZURE_OPENAI_API_KEY"):
        env.pop(name, None)
    return env


class OpenAIProvider(BaseProvider):
    """ChatGPT-authenticated Codex CLI provider; no OpenAI API fallback."""

    async def _verify_subscription(self, runtime: Path) -> str:
        runtime.mkdir(parents=True, exist_ok=True)
        result = await self._run_process(
            [self.config.command or "codex", "login", "status"],
            cwd=runtime,
            env=_subscription_env(),
        )
        self._ensure_process_success(result)
        combined = "\n".join((result.stdout, result.stderr)).strip()
        lowered = combined.casefold()
        if "chatgpt" in lowered:
            return "OPENAI_API_KEY was ignored; Codex confirmed ChatGPT authentication" if self.config.api_key else ""
        if "api key" in lowered or "apikey" in lowered:
            raise ProviderUnavailable(
                "Codex is authenticated with an API key, not ChatGPT; execution was stopped",
                provider=self.config.name,
                model=self.config.model,
                reason="api_key_auth",
                latency_ms=result.latency_ms,
                exit_code=result.exit_code,
                stderr=combined,
            )
        reason = classify_failure(combined, exit_code=result.exit_code)
        raise ProviderUnavailable(
            "Codex ChatGPT authentication could not be confirmed",
            provider=self.config.name,
            model=self.config.model,
            reason="login_expired" if reason == "provider_error" else reason,
            latency_ms=result.latency_ms,
            exit_code=result.exit_code,
            stderr=combined,
        )

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[SchemaModel],
        schema_name: str,
        deterministic: bool,
    ) -> ProviderResult:
        runtime = Path(self.runtime_dir or Path.cwd() / ".runtime") / "codex"
        runtime.mkdir(parents=True, exist_ok=True)
        auth_warning = await self._verify_subscription(runtime)
        prompt = f"{system_prompt}\n\n{user_prompt}"
        with tempfile.TemporaryDirectory(prefix="call-", dir=runtime) as temporary:
            call_dir = Path(temporary)
            schema_path = call_dir / f"{schema_name}.schema.json"
            output_path = call_dir / "last-message.json"
            schema_path.write_text(
                json.dumps(strict_json_schema(schema_model), ensure_ascii=False),
                encoding="utf-8",
            )
            command = [
                self.config.command or "codex",
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--json",
                "--output-schema",
                str(schema_path),
                "-o",
                str(output_path),
                "-C",
                str(call_dir),
            ]
            if self.config.model and self.config.model != "default":
                command.extend(("--model", self.config.model))
            command.append("-")
            result = await self._run_process(command, stdin=prompt, cwd=call_dir, env=_subscription_env())
            self._ensure_process_success(result)
            combined = "\n".join((result.stderr, result.stdout[-2000:]))
            failure = classify_failure(combined)
            if failure in {"usage_limit", "login_expired"}:
                raise ProviderUnavailable(
                    f"Codex unavailable: {failure}",
                    provider=self.config.name,
                    model=self.config.model,
                    reason=failure,
                    latency_ms=result.latency_ms,
                    exit_code=result.exit_code,
                    stderr=result.stderr,
                )
            if not output_path.exists():
                raise ProviderUnavailable(
                    "Codex did not write -o output",
                    provider=self.config.name,
                    model=self.config.model,
                    reason="invalid_json",
                    latency_ms=result.latency_ms,
                    exit_code=result.exit_code,
                    stderr=result.stderr,
                )
            raw_text = output_path.read_text(encoding="utf-8")
            try:
                parsed = self._validate(raw_text, schema_model)
            except ProviderUnavailable as exc:
                exc.latency_ms = result.latency_ms
                exc.exit_code = result.exit_code
                exc.stderr = result.stderr
                raise
        usage, usage_available = _extract_codex_usage(result.stdout)
        stderr = "\n".join(item for item in (auth_warning, result.stderr) if item)
        return ProviderResult(
            provider=self.config.name,
            model=self.config.model,
            response_id=None,
            raw_text=raw_text,
            parsed=parsed,
            usage=usage,
            estimated_cost_usd=0.0,
            latency_ms=result.latency_ms,
            attempts=[AttemptLog(1, None, result.latency_ms, None, exit_code=0, stderr=stderr)],
            billing_mode="subscription",
            exit_code=0,
            stderr=stderr,
            usage_available=usage_available,
        )

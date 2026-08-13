from __future__ import annotations

import json
import os
from pathlib import Path

from council.schemas import SchemaModel, strict_json_schema

from .base import (
    AttemptLog,
    BaseProvider,
    ProviderResult,
    ProviderUnavailable,
    classify_failure,
    parse_json_text,
)


def _subscription_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(name, None)
    return env


class ClaudeProvider(BaseProvider):
    """Claude Code CLI provider. It never falls back to the Anthropic API."""

    async def _verify_subscription(self, runtime: Path) -> None:
        runtime.mkdir(parents=True, exist_ok=True)
        if self.config.api_key:
            raise ProviderUnavailable(
                "ANTHROPIC_API_KEY is set; Claude Code execution was stopped to prevent API billing",
                provider=self.config.name,
                model=self.config.model,
                reason="api_key_present",
            )
        result = await self._run_process(
            [self.config.command or "claude", "auth", "status", "--json"],
            cwd=runtime,
            env=_subscription_env(),
        )
        try:
            status = parse_json_text(result.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            self._ensure_process_success(result)
            raise ProviderUnavailable(
                "Claude auth status returned invalid JSON",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=result.latency_ms,
                exit_code=result.exit_code,
                stderr=result.stderr,
            ) from exc
        if not status.get("loggedIn") or status.get("authMethod") != "claude.ai":
            raise ProviderUnavailable(
                "Claude Code is not authenticated with a Claude.ai subscription",
                provider=self.config.name,
                model=self.config.model,
                reason="login_expired",
                latency_ms=result.latency_ms,
                exit_code=result.exit_code,
                stderr=result.stderr,
            )
        self._ensure_process_success(result)

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[SchemaModel],
        schema_name: str,
        deterministic: bool,
    ) -> ProviderResult:
        runtime = Path(self.runtime_dir or Path.cwd() / ".runtime") / "claude"
        runtime.mkdir(parents=True, exist_ok=True)
        await self._verify_subscription(runtime)
        schema = strict_json_schema(schema_model)
        prompt = f"{system_prompt}\n\n{user_prompt}"
        command = [
            self.config.command or "claude",
            "-p",
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(schema, ensure_ascii=False, separators=(",", ":")),
            "--model",
            self.config.model,
            "--no-session-persistence",
            "--tools",
            "",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--no-chrome",
        ]
        result = await self._run_process(command, stdin=prompt, cwd=runtime, env=_subscription_env())
        self._ensure_process_success(result)
        failure = classify_failure("\n".join((result.stderr, result.stdout[-1000:])))
        if failure in {"usage_limit", "login_expired"}:
            raise ProviderUnavailable(
                f"Claude Code unavailable: {failure}",
                provider=self.config.name,
                model=self.config.model,
                reason=failure,
                latency_ms=result.latency_ms,
                exit_code=result.exit_code,
                stderr=result.stderr,
            )
        try:
            envelope = parse_json_text(result.stdout)
            structured = envelope.get("structured_output")
            if structured is None:
                structured = parse_json_text(str(envelope.get("result", "")))
            parsed = schema_model.model_validate(structured).model_dump(mode="json")
        except Exception as exc:
            raise ProviderUnavailable(
                "Claude Code returned invalid structured JSON",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                latency_ms=result.latency_ms,
                exit_code=result.exit_code,
                stderr=f"{result.stderr}\n{type(exc).__name__}: {exc}",
            ) from exc
        source_usage = envelope.get("usage", {}) or {}
        usage = {
            "input_tokens": int(source_usage.get("input_tokens", 0) or 0),
            "cached_input_tokens": int(source_usage.get("cache_read_input_tokens", 0) or 0),
            "cache_write_tokens": int(source_usage.get("cache_creation_input_tokens", 0) or 0),
            "output_tokens": int(source_usage.get("output_tokens", 0) or 0),
        }
        model_usage = envelope.get("modelUsage") or {}
        reported_model = next(iter(model_usage), self.config.model) if isinstance(model_usage, dict) else self.config.model
        return ProviderResult(
            provider=self.config.name,
            model=reported_model,
            response_id=envelope.get("session_id"),
            raw_text=json.dumps(parsed, ensure_ascii=False),
            parsed=parsed,
            usage=usage,
            estimated_cost_usd=0.0,
            latency_ms=result.latency_ms,
            attempts=[AttemptLog(1, None, result.latency_ms, None, exit_code=0, stderr=result.stderr)],
            billing_mode="subscription",
            exit_code=0,
            stderr=result.stderr,
        )

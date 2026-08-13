from __future__ import annotations

import asyncio
import json
import os
import random
import re
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from council.config import ProviderConfig
from council.schemas import SchemaModel


TRANSIENT_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
USAGE_LIMIT_PATTERNS = (
    "usage limit",
    "rate limit",
    "quota exceeded",
    "credit balance",
    "insufficient_quota",
    "limit reached",
    "hit your limit",
    "capacity limit",
)
LOGIN_EXPIRED_PATTERNS = (
    "login required",
    "not logged in",
    "authentication required",
    "authentication failed",
    "unauthorized",
    "token expired",
    "login expired",
    "please log in",
    "please run codex login",
)


def sanitize_diagnostic(value: str | None, limit: int = 2000) -> str:
    if not value:
        return ""
    text = value[:limit]
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)\b(sk-[A-Za-z0-9_-]{8,}|fish_[A-Za-z0-9_-]{8,})\b", "[REDACTED]", text)
    return text


def classify_failure(text: str, *, exit_code: int | None = None) -> str:
    lowered = text.casefold()
    if any(pattern in lowered for pattern in USAGE_LIMIT_PATTERNS):
        return "usage_limit"
    if any(pattern in lowered for pattern in LOGIN_EXPIRED_PATTERNS):
        return "login_expired"
    if exit_code not in (None, 0):
        return "exit_code"
    if text.strip():
        return "stderr"
    return "provider_error"


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "provider_error"):
        super().__init__(message)
        self.reason = reason


class ProviderUnavailable(ProviderError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str,
        reason: str,
        latency_ms: int = 0,
        exit_code: int | None = None,
        stderr: str = "",
        attempts: list["AttemptLog"] | None = None,
    ):
        super().__init__(message, reason=reason)
        self.provider = provider
        self.model = model
        self.latency_ms = latency_ms
        self.exit_code = exit_code
        self.stderr = sanitize_diagnostic(stderr)
        self.attempts = attempts or []

    def audit_dict(self, stage: str | None = None) -> dict[str, Any]:
        return {
            "status": "provider_unavailable",
            "stage": stage,
            "provider": self.provider,
            "model": self.model,
            "reason": self.reason,
            "message": sanitize_diagnostic(str(self), 500),
            "latency_ms": self.latency_ms,
            "exit_code": self.exit_code,
            "stderr": self.stderr,
            "attempts": [asdict(attempt) for attempt in self.attempts],
            "automatic_api_fallback": False,
        }


@dataclass
class AttemptLog:
    attempt: int
    status_code: int | None
    latency_ms: int
    error: str | None
    category: str | None = None
    exit_code: int | None = None
    stderr: str = ""


@dataclass
class ProviderResult:
    provider: str
    model: str
    response_id: str | None
    raw_text: str
    parsed: dict[str, Any]
    usage: dict[str, int]
    estimated_cost_usd: float
    latency_ms: int
    attempts: list[AttemptLog] = field(default_factory=list)
    billing_mode: str = "unknown"
    exit_code: int | None = None
    stderr: str = ""
    status: str = "ok"
    usage_available: bool = True

    def audit_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["estimated_cost_usd"] = round(self.estimated_cost_usd, 9)
        data["stderr"] = sanitize_diagnostic(self.stderr)
        return data


@dataclass
class ProcessResult:
    stdout: str
    stderr: str
    exit_code: int
    latency_ms: int


def parse_json_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Provider returned a JSON value that is not an object")
    return parsed


def estimate_cost(config: ProviderConfig, usage: dict[str, int]) -> float:
    prices = config.prices
    normal_input = max(0, usage.get("input_tokens", 0))
    cached = max(0, usage.get("cached_input_tokens", 0))
    cache_write = max(0, usage.get("cache_write_tokens", 0))
    output = max(0, usage.get("output_tokens", 0))
    cached_rate = prices.cached_input_per_m if prices.cached_input_per_m is not None else prices.input_per_m
    write_rate = prices.cache_write_per_m if prices.cache_write_per_m is not None else prices.input_per_m
    return (
        normal_input * prices.input_per_m
        + cached * cached_rate
        + cache_write * write_rate
        + output * prices.output_per_m
    ) / 1_000_000


class BaseProvider(ABC):
    def __init__(
        self,
        config: ProviderConfig,
        *,
        timeout_seconds: float,
        max_retries: int,
        client: httpx.AsyncClient | None = None,
        runtime_dir=None,
    ):
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.runtime_dir = runtime_dir
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _run_process(
        self,
        command: list[str],
        *,
        stdin: str = "",
        cwd=None,
        env: dict[str, str] | None = None,
    ) -> ProcessResult:
        started = time.perf_counter()
        resolved_command = list(command)
        if os.name == "nt":
            requested = command[0]
            wrapper = shutil.which(requested + ".cmd")
            native = None
            if Path(requested).name.casefold() == "claude" and wrapper:
                candidate = (
                    Path(wrapper).parent
                    / "node_modules"
                    / "@anthropic-ai"
                    / "claude-code"
                    / "bin"
                    / "claude.exe"
                )
                if candidate.is_file():
                    native = str(candidate)
            if Path(requested).name.casefold() == "codex" and wrapper:
                candidates = list(
                    (Path(wrapper).parent / "node_modules" / "@openai" / "codex").glob(
                        "node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe"
                    )
                )
                if candidates:
                    native = str(candidates[0])
            resolved = native or wrapper or shutil.which(requested)
            if resolved and Path(resolved).suffix.casefold() in {".cmd", ".bat"}:
                resolved_command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", resolved, *command[1:]]
            elif resolved:
                resolved_command[0] = resolved
        try:
            process = await asyncio.create_subprocess_exec(
                *resolved_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
        except (FileNotFoundError, OSError) as exc:
            raise ProviderUnavailable(
                f"{self.config.name} CLI could not be started: {exc}",
                provider=self.config.name,
                model=self.config.model,
                reason="not_installed",
            ) from exc
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(stdin.encode("utf-8")),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            latency = int((time.perf_counter() - started) * 1000)
            raise ProviderUnavailable(
                f"{self.config.name} timed out after {self.timeout_seconds:g}s",
                provider=self.config.name,
                model=self.config.model,
                reason="timeout",
                latency_ms=latency,
                exit_code=process.returncode,
            ) from exc
        return ProcessResult(
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=sanitize_diagnostic(stderr_bytes.decode("utf-8", errors="replace")),
            exit_code=int(process.returncode or 0),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _ensure_process_success(self, result: ProcessResult) -> None:
        if result.exit_code == 0:
            return
        combined = "\n".join((result.stderr, result.stdout[-2000:]))
        reason = classify_failure(combined, exit_code=result.exit_code)
        diagnostic = result.stderr or sanitize_diagnostic(result.stdout[-2000:])
        raise ProviderUnavailable(
            f"{self.config.name} CLI exited with code {result.exit_code}",
            provider=self.config.name,
            model=self.config.model,
            reason=reason,
            latency_ms=result.latency_ms,
            exit_code=result.exit_code,
            stderr=diagnostic,
            attempts=[AttemptLog(1, None, result.latency_ms, reason, reason, result.exit_code, diagnostic)],
        )

    async def _post(self, url: str, *, headers: dict[str, str], payload: dict) -> tuple[dict, list[AttemptLog], int]:
        attempts: list[AttemptLog] = []
        overall_started = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            status: int | None = None
            try:
                response = await self.client.post(url, headers=headers, json=payload)
                status = response.status_code
                latency = int((time.perf_counter() - started) * 1000)
                body_preview = sanitize_diagnostic(response.text, 1000) if response.is_error else ""
                if status in TRANSIENT_STATUS and attempt < self.max_retries:
                    category = "usage_limit" if status == 429 else "http_transient"
                    attempts.append(AttemptLog(attempt + 1, status, latency, f"HTTP {status}", category))
                    await asyncio.sleep(min(2**attempt, 4) + random.random() * 0.1)
                    continue
                if response.is_error:
                    category = "login_expired" if status in {401, 403} else classify_failure(body_preview)
                    raise ProviderUnavailable(
                        f"{self.config.name} HTTP {status}",
                        provider=self.config.name,
                        model=self.config.model,
                        reason=category,
                        latency_ms=int((time.perf_counter() - overall_started) * 1000),
                        stderr=body_preview,
                        attempts=attempts + [AttemptLog(attempt + 1, status, latency, body_preview, category)],
                    )
                attempts.append(AttemptLog(attempt + 1, status, latency, None))
                return response.json(), attempts, int((time.perf_counter() - overall_started) * 1000)
            except ProviderUnavailable:
                raise
            except httpx.TimeoutException as exc:
                latency = int((time.perf_counter() - started) * 1000)
                attempts.append(AttemptLog(attempt + 1, status, latency, "timeout", "timeout"))
                if attempt >= self.max_retries:
                    raise ProviderUnavailable(
                        f"{self.config.name} HTTP request timed out",
                        provider=self.config.name,
                        model=self.config.model,
                        reason="timeout",
                        latency_ms=int((time.perf_counter() - overall_started) * 1000),
                        attempts=attempts,
                    ) from exc
                await asyncio.sleep(min(2**attempt, 4) + random.random() * 0.1)
            except (httpx.HTTPError, ValueError) as exc:
                latency = int((time.perf_counter() - started) * 1000)
                safe_error = sanitize_diagnostic(f"{type(exc).__name__}: {exc}", 300)
                attempts.append(AttemptLog(attempt + 1, status, latency, safe_error, "transport_error"))
                if attempt >= self.max_retries:
                    raise ProviderUnavailable(
                        f"{self.config.name} transport failed",
                        provider=self.config.name,
                        model=self.config.model,
                        reason="transport_error",
                        latency_ms=int((time.perf_counter() - overall_started) * 1000),
                        stderr=safe_error,
                        attempts=attempts,
                    ) from exc
                await asyncio.sleep(min(2**attempt, 4) + random.random() * 0.1)
        raise AssertionError("unreachable")

    def _validate(self, text: str, schema_model: type[SchemaModel]) -> dict[str, Any]:
        try:
            return schema_model.model_validate(parse_json_text(text)).model_dump(mode="json")
        except (json.JSONDecodeError, ValueError, ValidationError) as exc:
            raise ProviderUnavailable(
                f"{self.config.name}/{self.config.model} returned invalid structured output",
                provider=self.config.name,
                model=self.config.model,
                reason="invalid_json",
                stderr=sanitize_diagnostic(str(exc), 500),
            ) from exc

    @abstractmethod
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_model: type[SchemaModel],
        schema_name: str,
        deterministic: bool,
    ) -> ProviderResult:
        raise NotImplementedError

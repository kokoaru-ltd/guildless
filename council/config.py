from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


@dataclass(frozen=True)
class PriceSpec:
    input_per_m: float = 0.0
    output_per_m: float = 0.0
    cached_input_per_m: float | None = None
    cache_write_per_m: float | None = None


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    api_key: str = ""
    base_url: str = ""
    prices: PriceSpec = PriceSpec()
    billing_mode: str = "subscription"
    command: str = ""


@dataclass(frozen=True)
class Settings:
    providers: dict[str, ProviderConfig]
    output_dir: Path
    timeout_seconds: float
    max_retries: int
    max_context_bytes: int
    runtime_dir: Path | None = None
    local_repetitions: int = 3

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)

        # A legacy installation stored a Sakana fish_* key under
        # ANTHROPIC_API_KEY. Preserve Sakana compatibility, but never pass that
        # variable to Claude Code. A real Anthropic key blocks ClaudeProvider.
        legacy_anthropic = os.getenv("ANTHROPIC_API_KEY", "").strip()
        sakana_key = os.getenv("SAKANA_API_KEY", "").strip()
        if not sakana_key and legacy_anthropic.startswith("fish_"):
            sakana_key = legacy_anthropic
        anthropic_key = "" if legacy_anthropic.startswith("fish_") else legacy_anthropic

        providers = {
            "claude": ProviderConfig(
                name="claude",
                model=os.getenv("CLAUDE_MODEL", "opus"),
                api_key=anthropic_key,
                billing_mode="subscription",
                command=os.getenv("CLAUDE_COMMAND", "claude"),
            ),
            "codex": ProviderConfig(
                name="codex",
                model=os.getenv("CODEX_MODEL", "default"),
                api_key=os.getenv("OPENAI_API_KEY", "").strip(),
                billing_mode="subscription",
                command=os.getenv("CODEX_COMMAND", "codex"),
            ),
            "deepseek": ProviderConfig(
                name="deepseek",
                model=os.getenv("OLLAMA_DEEPSEEK_MODEL", "deepseek-r1:14b"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
                billing_mode="local",
                command=os.getenv("OLLAMA_COMMAND", "ollama"),
            ),
            "sakana": ProviderConfig(
                name="sakana",
                model=os.getenv("SAKANA_MODEL", "fugu-ultra"),
                api_key=sakana_key,
                base_url=os.getenv("SAKANA_BASE_URL", "https://api.sakana.ai").rstrip("/"),
                billing_mode="subscription",
            ),
        }
        return cls(
            providers=providers,
            output_dir=Path(os.getenv("COUNCIL_OUTPUT_DIR", str(PROJECT_ROOT / "runs"))).resolve(),
            timeout_seconds=_float(
                "COUNCIL_PROVIDER_TIMEOUT_SECONDS",
                _float("COUNCIL_HTTP_TIMEOUT_SECONDS", 300.0),
            ),
            max_retries=_int("COUNCIL_MAX_RETRIES", 2),
            max_context_bytes=_int("COUNCIL_MAX_CONTEXT_BYTES", 2_000_000),
            runtime_dir=Path(
                os.getenv("COUNCIL_RUNTIME_DIR", str(PROJECT_ROOT / ".runtime"))
            ).resolve(),
            local_repetitions=max(2, _int("COUNCIL_LOCAL_REPETITIONS", 3)),
        )

    def missing_keys(self) -> list[str]:
        """Only optional network providers need keys; CLI/local providers do not."""
        return ["sakana"] if not self.providers["sakana"].api_key else []

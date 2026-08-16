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


def _env(*names: str, default: str = "") -> str:
    """Case-insensitive environment lookup with fallback names.

    Some keys are pasted into .env with a different casing (e.g. Zai_api_key),
    so plain os.getenv is not enough. The first non-empty match wins.
    """
    lowered = {name.lower(): name for name in os.environ}
    for name in names:
        direct = os.environ.get(name)
        if direct and direct.strip():
            return direct.strip()
        hit = lowered.get(name.lower())
        if hit:
            value = os.environ.get(hit)
            if value and value.strip():
                return value.strip()
    return default


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
class PaymentConfig:
    secret_key: str = ""
    webhook_secret: str = ""
    success_url: str = ""
    cancel_url: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.secret_key)

    @property
    def live(self) -> bool:
        """Live keys move real money and require a verified human behind them."""
        return self.secret_key.startswith("sk_live_")


@dataclass(frozen=True)
class Settings:
    providers: dict[str, ProviderConfig]
    output_dir: Path
    timeout_seconds: float
    max_retries: int
    max_context_bytes: int
    runtime_dir: Path | None = None
    local_repetitions: int = 3
    payment: PaymentConfig = PaymentConfig()

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)

        # A legacy installation stored a Sakana fish_* key under
        # ANTHROPIC_API_KEY. Preserve Sakana compatibility, but never pass that
        # variable to Claude Code. A real Anthropic key blocks ClaudeProvider.
        legacy_anthropic = os.getenv("ANTHROPIC_API_KEY", "").strip()
        sakana_key = _env("SAKANA_API_KEY", "SAKANA_KEY", "FUGU_API_KEY")
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
            # Hosted DeepSeek. Independent of the local Ollama "deepseek"
            # entry above, so the council keeps a second real voice when no
            # local runtime is up.
            "deepseek_api": ProviderConfig(
                name="deepseek_api",
                model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                api_key=_env("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
                billing_mode="subscription",
            ),
            "sakana": ProviderConfig(
                name="sakana",
                model=os.getenv("SAKANA_MODEL", "fugu-ultra"),
                api_key=sakana_key,
                base_url=os.getenv("SAKANA_BASE_URL", "https://api.sakana.ai").rstrip("/"),
                billing_mode="subscription",
            ),
            "gemini": ProviderConfig(
                name="gemini",
                model=os.getenv("GEMINI_MODEL", "gemini-3.7-flash"),
                api_key=_env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"),
                base_url=os.getenv(
                    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com"
                ).rstrip("/"),
                billing_mode="subscription",
            ),
            "glm": ProviderConfig(
                name="glm",
                model=os.getenv("GLM_MODEL", "glm-5.3"),
                api_key=_env("ZHIPU_API_KEY", "ZAI_API_KEY", "Zai_api_key", "GLM_API_KEY"),
                base_url=os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip(
                    "/"
                ),
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
            payment=PaymentConfig(
                secret_key=_env("STRIPE_SECRET_KEY"),
                webhook_secret=_env("STRIPE_WEBHOOK_SECRET"),
                success_url=os.getenv("STRIPE_SUCCESS_URL", "").strip(),
                cancel_url=os.getenv("STRIPE_CANCEL_URL", "").strip(),
            ),
        )

    def missing_keys(self) -> list[str]:
        """Only optional network providers need keys; CLI/local providers do not."""
        return ["sakana"] if not self.providers["sakana"].api_key else []

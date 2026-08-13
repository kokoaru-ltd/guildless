from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from council.config import PriceSpec, ProviderConfig
from council.providers.base import ProcessResult, ProviderUnavailable
from council.providers.claude import ClaudeProvider
from council.providers.deepseek import DeepSeekProvider
from council.providers.openai import OpenAIProvider
from council.providers.sakana import SakanaProvider
from council.schemas import Proposal


PROPOSAL = {
    "position": "position",
    "assumptions": [],
    "recommendations": ["recommendation"],
    "risks": [],
    "rejected_options": [],
    "needs_external_fact": [],
    "confidence": 0.8,
}


def config(name: str, *, api_key: str = "", base_url: str = "") -> ProviderConfig:
    return ProviderConfig(name, f"{name}-model", api_key, base_url, PriceSpec(), "subscription", name)


class FakeClaude(ClaudeProvider):
    commands: list[list[str]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []

    async def _run_process(self, command, *, stdin="", cwd=None, env=None):
        self.commands.append(command)
        assert "ANTHROPIC_API_KEY" not in env
        if command[1:3] == ["auth", "status"]:
            return ProcessResult('{"loggedIn":true,"authMethod":"claude.ai"}', "", 0, 2)
        assert command[1] == "-p"
        assert "--output-format" in command
        assert "--json-schema" in command
        assert "--bare" not in command
        assert "--tools" in command
        return ProcessResult(
            json.dumps(
                {
                    "structured_output": PROPOSAL,
                    "usage": {"input_tokens": 12, "output_tokens": 4},
                    "session_id": "session-1",
                }
            ),
            "",
            0,
            10,
        )


@pytest.mark.asyncio
async def test_claude_cli_uses_required_structured_flags(tmp_path: Path):
    provider = FakeClaude(
        config("claude"), timeout_seconds=10, max_retries=0, runtime_dir=tmp_path
    )
    result = await provider.generate_json(
        system_prompt="system",
        user_prompt="user",
        schema_model=Proposal,
        schema_name="proposal",
        deterministic=True,
    )
    assert result.parsed == PROPOSAL
    assert result.billing_mode == "subscription"
    assert result.estimated_cost_usd == 0
    await provider.aclose()


@pytest.mark.asyncio
async def test_claude_stops_when_anthropic_api_key_is_configured(tmp_path: Path):
    provider = ClaudeProvider(
        config("claude", api_key="sk-ant-redacted"),
        timeout_seconds=10,
        max_retries=0,
        runtime_dir=tmp_path,
    )
    with pytest.raises(ProviderUnavailable) as caught:
        await provider.generate_json(
            system_prompt="system",
            user_prompt="user",
            schema_model=Proposal,
            schema_name="proposal",
            deterministic=True,
        )
    assert caught.value.reason == "api_key_present"
    await provider.aclose()


class FakeCodex(OpenAIProvider):
    commands: list[list[str]]
    auth_text = "Logged in using ChatGPT"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []

    async def _run_process(self, command, *, stdin="", cwd=None, env=None):
        self.commands.append(command)
        assert "OPENAI_API_KEY" not in env
        if command[1:3] == ["login", "status"]:
            return ProcessResult(self.auth_text, "", 0, 2)
        output = Path(command[command.index("-o") + 1])
        output.write_text(json.dumps(PROPOSAL), encoding="utf-8")
        return ProcessResult(
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 20, "cached_input_tokens": 5, "output_tokens": 7}}),
            "",
            0,
            12,
        )


@pytest.mark.asyncio
async def test_codex_cli_uses_ephemeral_schema_and_output_file(tmp_path: Path):
    provider = FakeCodex(
        config("codex", api_key="ignored-api-key"),
        timeout_seconds=10,
        max_retries=0,
        runtime_dir=tmp_path,
    )
    result = await provider.generate_json(
        system_prompt="system",
        user_prompt="user",
        schema_model=Proposal,
        schema_name="proposal",
        deterministic=True,
    )
    command = provider.commands[-1]
    assert command[1] == "exec"
    assert "--ephemeral" in command
    assert "--output-schema" in command
    assert "-o" in command
    assert "--json" in command
    assert "--ignore-user-config" in command
    assert "OPENAI_API_KEY was ignored" in result.stderr
    assert result.parsed == PROPOSAL
    assert result.usage == {"input_tokens": 15, "cached_input_tokens": 5, "cache_write_tokens": 0, "output_tokens": 7}
    await provider.aclose()


@pytest.mark.asyncio
async def test_codex_api_key_auth_is_rejected(tmp_path: Path):
    class ApiAuthCodex(FakeCodex):
        auth_text = "Logged in using an API key"

    provider = ApiAuthCodex(
        config("codex"), timeout_seconds=10, max_retries=0, runtime_dir=tmp_path
    )
    with pytest.raises(ProviderUnavailable) as caught:
        await provider.generate_json(
            system_prompt="system",
            user_prompt="user",
            schema_model=Proposal,
            schema_name="proposal",
            deterministic=True,
        )
    assert caught.value.reason == "api_key_auth"
    await provider.aclose()


@pytest.mark.asyncio
async def test_deepseek_uses_ollama_local_structured_chat():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://127.0.0.1:11434/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-r1:14b"
        assert body["format"]["additionalProperties"] is False
        assert body["stream"] is False
        assert request.headers.get("authorization") is None
        return httpx.Response(
            200,
            json={
                "model": "deepseek-r1:14b",
                "message": {"role": "assistant", "content": json.dumps(PROPOSAL)},
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DeepSeekProvider(
        ProviderConfig("deepseek", "deepseek-r1:14b", base_url="http://127.0.0.1:11434", billing_mode="local"),
        timeout_seconds=10,
        max_retries=0,
        client=client,
    )
    result = await provider.generate_json(
        system_prompt="system",
        user_prompt="user",
        schema_model=Proposal,
        schema_name="proposal",
        deterministic=True,
    )
    assert result.usage["input_tokens"] == 100
    assert result.billing_mode == "local"
    assert result.estimated_cost_usd == 0
    await client.aclose()


@pytest.mark.asyncio
async def test_sakana_remains_subscription_responses_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/responses"
        body = json.loads(request.content)
        assert body["text"]["format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "id": "resp_sakana",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(PROPOSAL)}]}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SakanaProvider(
        ProviderConfig("sakana", "fugu-ultra", "fish-redacted", "https://api.sakana.ai", billing_mode="subscription"),
        timeout_seconds=10,
        max_retries=0,
        client=client,
    )
    result = await provider.generate_json(
        system_prompt="system",
        user_prompt="user",
        schema_model=Proposal,
        schema_name="proposal",
        deterministic=True,
    )
    assert result.billing_mode == "subscription"
    assert result.estimated_cost_usd == 0
    await client.aclose()

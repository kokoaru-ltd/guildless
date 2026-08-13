from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from council.api import create_app
from council.config import ProviderConfig, Settings
from council.orchestrator import CouncilOrchestrator
from council.providers.base import AttemptLog, ProviderResult, ProviderUnavailable
from council.schemas import Critique, FinalDecision, Proposal


@dataclass
class FakeProvider:
    config: ProviderConfig
    unavailable: bool = False
    calls: list[str] = field(default_factory=list)

    async def aclose(self):
        return None

    async def generate_json(self, *, schema_model, **kwargs):
        self.calls.append(schema_model.__name__)
        if self.unavailable:
            raise ProviderUnavailable(
                f"{self.config.name} unavailable",
                provider=self.config.name,
                model=self.config.model,
                reason="usage_limit",
            )
        if schema_model is Proposal:
            parsed = {
                "position": f"{self.config.name} proposal",
                "assumptions": [],
                "recommendations": ["review the supplied context"],
                "risks": ["insufficient context"],
                "rejected_options": [],
                "needs_external_fact": [],
                "confidence": 0.7,
            }
        elif schema_model is Critique:
            parsed = {
                "supported_points": [], "errors": [], "missing_considerations": [],
                "conflicts": [], "revised_recommendation": "continue",
            }
        else:
            parsed = {
                "decision": "Use only supplied context",
                "consensus": ["read only"],
                "disagreements": [], "rejected_options": [], "risks": [],
                "next_action": "present candidate", "user_question": None, "confidence": 0.8,
            }
        value = schema_model.model_validate(parsed).model_dump(mode="json")
        return ProviderResult(
            provider=self.config.name,
            model=self.config.model,
            response_id=f"{self.config.name}-id",
            raw_text=json.dumps(value),
            parsed=value,
            usage={"input_tokens": 10, "cached_input_tokens": 0, "cache_write_tokens": 0, "output_tokens": 10},
            estimated_cost_usd=0.0,
            latency_ms=1,
            attempts=[AttemptLog(1, 200, 1, None)],
            billing_mode=self.config.billing_mode,
        )


def make_app(tmp_path: Path, *, unavailable: set[str] | None = None):
    configs = {
        name: ProviderConfig(name, name, billing_mode="local" if name == "deepseek" else "subscription")
        for name in ("claude", "deepseek", "codex", "sakana")
    }
    settings = Settings(configs, tmp_path / "runs", 5, 0, 100_000, tmp_path / ".runtime", 3)
    providers = {name: FakeProvider(config, name in (unavailable or set())) for name, config in configs.items()}

    def factory(current: Settings) -> CouncilOrchestrator:
        return CouncilOrchestrator(current, providers=providers, output_boundary=tmp_path)

    return create_app(settings, output_boundary=tmp_path, orchestrator_factory=factory), providers


async def wait_for_terminal(client: httpx.AsyncClient, run_id: str) -> dict:
    for _ in range(100):
        payload = (await client.get(f"/v1/council/runs/{run_id}")).json()
        if payload["status"] in {"completed", "degraded", "failed"}:
            return payload
        await asyncio.sleep(0.01)
    raise AssertionError("run did not finish")


@pytest.mark.asyncio
async def test_async_http_run_and_polling_events(tmp_path: Path):
    app, providers = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/council/runs", json={
            "task_type": "general", "mode": "fast", "question": "What should we do?",
            "context": {"facts": ["only this is visible"], "path_text": r"D:\founder_memory\secret.sqlite"},
            "allowed_providers": ["claude", "deepseek", "codex"],
        })
        assert response.status_code == 202
        accepted = response.json()
        assert accepted["status"] == "queued"
        final = await wait_for_terminal(client, accepted["run_id"])
        assert final["status"] == "completed"
        assert final["final_result"]["record_type"] == "assistant_council_candidate"
        assert final["final_result"]["promotion_status"] == "unconfirmed"
        assert final["final_result"]["automatic_promotion_supported"] is False
        events = (await client.get(accepted["events_url"])).json()
        statuses = [event["status"] for event in events["events"]]
        assert statuses == ["queued", "preparing_context", "proposing", "judging", "completed"]
        assert events["terminal"] is True
        canonical = json.loads((tmp_path / "runs" / accepted["run_id"] / "canonical_request.json").read_text(encoding="utf-8"))
        assert canonical["contexts"][0]["source_path"] == "inline:request.context"
        assert providers["sakana"].calls == []


@pytest.mark.asyncio
async def test_unavailable_provider_finishes_degraded_with_remaining_models(tmp_path: Path):
    app, _ = make_app(tmp_path, unavailable={"claude"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        accepted = (await client.post("/v1/council/runs", json={
            "task_type": "architecture", "mode": "fast", "question": "degrade safely",
            "context": {}, "allowed_providers": ["claude", "deepseek", "codex"],
        })).json()
        final = await wait_for_terminal(client, accepted["run_id"])
        assert final["status"] == "degraded"
        events = (await client.get(accepted["events_url"], params={"after": 2})).json()
        assert all(event["sequence"] > 2 for event in events["events"])
        assert events["events"][-1]["status"] == "degraded"


@pytest.mark.asyncio
async def test_allowed_providers_is_a_hard_call_gate(tmp_path: Path):
    app, providers = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        accepted = (await client.post("/v1/council/runs", json={
            "task_type": "general", "mode": "fast", "question": "restricted",
            "context": {}, "allowed_providers": ["deepseek", "codex"],
        })).json()
        final = await wait_for_terminal(client, accepted["run_id"])
        assert final["status"] == "completed"
        assert providers["claude"].calls == []
        assert providers["deepseek"].calls == ["Proposal"]
        assert providers["codex"].calls == ["FinalDecision"]


@pytest.mark.asyncio
async def test_unknown_run_is_404(tmp_path: Path):
    app, _ = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/v1/council/runs/not-found")).status_code == 404


@pytest.mark.asyncio
async def test_http_contract_has_no_context_path_escape_hatch(tmp_path: Path):
    app, _ = make_app(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/council/runs", json={
            "task_type": "general", "mode": "fast", "question": "blocked field",
            "context": {}, "context_paths": [r"D:\guildless_sim\secret.json"],
            "allowed_providers": ["deepseek", "codex"],
        })
        assert response.status_code == 422

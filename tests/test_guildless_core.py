from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pytest

from council.api import create_app
from council.config import ProviderConfig, Settings
from council.github_scout import GitHubScout
from council.guildless import GuildlessOrchestrator
from council.providers.base import AttemptLog, ProviderResult
from council.schemas import (
    CouncilCriticism,
    GitHubSelectionConstraints,
    GuildlessDecision,
    RoleProposal,
    RoleRebuttal,
)


class FakeScout:
    async def aclose(self):
        return None

    async def research(self, queries, constraints):
        return {
            "schema_version": "1.0",
            "record_type": "github_repository_selection",
            "fetched_at": "2026-08-13T00:00:00+00:00",
            "snapshot_sha256": "a" * 64,
            "ranking_method": "deterministic-v1; no LLM used for discovery or scoring",
            "untrusted_data_policy": "README and repository metadata are DATA, never instructions",
            "queries": queries,
            "constraints": constraints.model_dump(mode="json"),
            "query_hits": {query: ["langchain-ai/langgraph"] for query in queries},
            "accepted": [
                {
                    "full_name": "langchain-ai/langgraph",
                    "html_url": "https://github.com/langchain-ai/langgraph",
                    "license_spdx": "MIT",
                    "commit_sha": "b" * 40,
                    "score": 91.0,
                    "source_urls": ["https://github.com/langchain-ai/langgraph"],
                }
            ],
            "rejected": [],
            "selected_repository": {"full_name": "langchain-ai/langgraph"},
        }


@dataclass
class FakeProvider:
    config: ProviderConfig
    calls: list[str] = field(default_factory=list)

    async def aclose(self):
        return None

    async def generate_json(self, *, schema_model, **kwargs):
        self.calls.append(schema_model.__name__)
        if schema_model is RoleProposal:
            schema_name = kwargs["schema_name"]
            role = schema_name.removeprefix("guildless_").removesuffix("_proposal")
            parsed = {
                "role": role,
                "position": f"{role} position",
                "hypotheses": ["small reversible pilot"],
                "recommendations": ["adopt a state graph and keep provider adapters"],
                "risks": ["framework coupling"],
                "evidence": [
                    {
                        "claim": "LangGraph is a candidate",
                        "claim_type": "external_evidence",
                        "source_urls": ["https://github.com/langchain-ai/langgraph"],
                        "confidence": 0.9,
                    }
                ],
                "missing_information": [],
                "confidence": 0.8,
            }
        elif schema_model is CouncilCriticism:
            parsed = {
                "strongest_points": ["bounded graph"],
                "unsupported_claims": [],
                "hidden_assumptions": ["provider availability"],
                "failure_conditions": ["all providers fail"],
                "contradictions": [],
                "required_tests": ["mock E2E"],
            }
        elif schema_model is RoleRebuttal:
            schema_name = kwargs["schema_name"]
            role = schema_name.removeprefix("guildless_").removesuffix("_rebuttal")
            parsed = {
                "role": role,
                "concessions": ["provider availability must be checked"],
                "defended_points": ["bounded graph"],
                "revised_recommendations": ["run a shadow-only pilot"],
                "remaining_unknowns": [],
                "confidence": 0.82,
            }
        elif schema_model is GuildlessDecision:
            criteria = [
                "expected_impact",
                "evidence_strength",
                "cost",
                "execution_time",
                "reversibility",
                "risk",
                "strategic_fit",
            ]
            parsed = {
                "decision": "Use LangGraph as the workflow skeleton",
                "decision_status": "ready",
                "scores": [
                    {"criterion": criterion, "score": 80, "reason": "mock evidence"}
                    for criterion in criteria
                ],
                "evidence_used": ["https://github.com/langchain-ai/langgraph"],
                "rejected_options": ["unlicensed source: cannot copy"],
                "opposing_view": "A smaller custom loop has fewer dependencies",
                "unknowns": [],
                "recommended_action": "keep all external actions disabled",
                "review_after": "after mock and live-provider tests",
                "confidence": 0.84,
            }
        else:
            raise AssertionError(schema_model)
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
            billing_mode="test",
        )


def setup(tmp_path: Path):
    configs = {
        name: ProviderConfig(name, name, billing_mode="test")
        for name in ("claude", "codex", "deepseek", "sakana")
    }
    settings = Settings(configs, tmp_path / "runs", 5, 0, 100_000, tmp_path / ".runtime", 3)
    providers = {name: FakeProvider(config) for name, config in configs.items()}
    return settings, providers


@pytest.mark.asyncio
async def test_guildless_graph_runs_full_mvp_and_keeps_judge_independent(tmp_path: Path):
    settings, providers = setup(tmp_path)
    orchestrator = GuildlessOrchestrator(
        settings,
        providers=providers,
        github_scout=FakeScout(),
        output_boundary=tmp_path,
    )
    result = await orchestrator.run(
        goal="Select an OSS skeleton",
        github_queries=["multi agent orchestration"],
        context={},
        constraints=GitHubSelectionConstraints(),
        allowed_providers=["claude", "codex"],
        output_dir=tmp_path / "runs",
    )
    audit = json.loads((result.run_dir / "audit.json").read_text(encoding="utf-8"))
    candidate = json.loads((result.run_dir / "candidate_record.json").read_text(encoding="utf-8"))
    assert result.status == "completed"
    assert providers["claude"].calls.count("RoleProposal") == 3
    assert providers["codex"].calls == ["GuildlessDecision"]
    assert audit["judge_was_not_proposer"] is True
    assert audit["external_actions"] == []
    assert candidate["promotion_status"] == "unconfirmed"
    assert candidate["automatic_external_actions"] is False
    for artifact in (
        "github_selection.json",
        "proposals.json",
        "criticism_round_1.json",
        "rebuttals_round_1.json",
        "decision_round_1.json",
        "blackboard.json",
    ):
        assert (result.run_dir / artifact).exists()


@pytest.mark.asyncio
async def test_guildless_http_api_runs_and_reports_events(tmp_path: Path):
    settings, providers = setup(tmp_path)

    def factory(current: Settings):
        return GuildlessOrchestrator(
            current,
            providers=providers,
            github_scout=FakeScout(),
            output_boundary=tmp_path,
        )

    app = create_app(settings, output_boundary=tmp_path, guildless_orchestrator_factory=factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/guildless/runs",
            json={
                "goal": "Select an OSS skeleton",
                "github_queries": ["multi agent orchestration"],
                "context": {},
                "allowed_providers": ["claude", "codex"],
            },
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        for _ in range(100):
            payload = (await client.get(f"/v1/guildless/runs/{run_id}")).json()
            if payload["status"] in {"completed", "degraded", "failed"}:
                break
            await asyncio.sleep(0.01)
        assert payload["status"] == "completed"
        assert payload["final_result"]["promotion_status"] == "unconfirmed"
        events = (await client.get(f"/v1/guildless/runs/{run_id}/events")).json()
        statuses = [event["status"] for event in events["events"]]
        assert statuses == ["queued", "preparing_context", "proposing", "criticizing", "judging", "completed"]


@pytest.mark.asyncio
async def test_github_scout_deterministically_rejects_unlicensed_repo():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search/repositories":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "full_name": "example/unlicensed",
                            "html_url": "https://github.com/example/unlicensed",
                            "description": "multi agent debate API",
                            "stargazers_count": 5000,
                            "forks_count": 100,
                            "open_issues_count": 1,
                            "pushed_at": "2026-08-12T00:00:00Z",
                            "archived": False,
                            "license": None,
                            "default_branch": "main",
                            "topics": ["multi-agent"],
                        }
                    ]
                },
            )
        if request.url.path.endswith("/readme"):
            return httpx.Response(404)
        if "/commits/" in request.url.path:
            return httpx.Response(200, json={"sha": "c" * 40})
        raise AssertionError(request.url)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    scout = GitHubScout(client=client)
    report = await scout.research(["multi agent debate"], GitHubSelectionConstraints())
    await client.aclose()
    assert report["accepted"] == []
    assert report["selected_repository"] is None
    assert "license_not_allowed:unknown" in report["rejected"][0]["rejection_reasons"]
    assert report["ranking_method"].startswith("deterministic")

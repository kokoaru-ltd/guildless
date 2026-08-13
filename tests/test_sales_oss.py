from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from council.api import create_app
from council.config import Settings
from council.sales_oss import SalesOssRegistry


def build_fixture(root: Path) -> SalesOssRegistry:
    files = {
        "b2b-sdr-agent-template/workspace/AGENTS.md": "### Stage 1: Lead Capture\n### Stage 2: BANT Qualification\n",
        "b2b-sdr-agent-template/workspace/HEARTBEAT.md": "## 1. Follow-up due\n## 2. Quote waiting\n",
        "SalesGPT/salesgpt/stages.py": "CONVERSATION_STAGES = {'1': 'Introduction', '2': 'Qualification'}\n",
        "ai-sales-team-claude/scripts/lead_scorer.py": (
            "import json, sys\n"
            "data=json.load(sys.stdin)\n"
            "print(json.dumps({'company': data['company'], 'bant_score': 80, 'lead_grade': 'A', "
            "'confidence_level': 'high', 'recommended_action': '次へ — discovery'}, ensure_ascii=False))\n"
        ),
        "gtm/openclaw-skills/scout/SKILL.md": "# Scout\n",
        "gtm/openclaw-skills/rep/SKILL.md": "# Rep\n",
        "gtm/openclaw-skills/closer/SKILL.md": "# Closer\n",
        "gtm/openclaw-skills/writer/SKILL.md": "# Writer\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return SalesOssRegistry(root)


def test_registry_loads_upstream_pipeline_and_scores_without_external_action(tmp_path: Path) -> None:
    registry = build_fixture(tmp_path)
    overview = registry.overview()
    assert overview["status"] == "ready"
    assert overview["external_sending_enabled"] is False
    assert [stage["title"] for stage in overview["pipeline"]] == ["Lead Capture", "BANT Qualification"]
    assert [role["id"] for role in overview["marketing_team"]] == ["scout", "rep", "closer", "writer"]

    score = registry.score_lead({"company": "Example", "budget_signals": {}})
    assert score["bant_score"] == 80
    assert score["recommended_action"] == "次へ — discovery"
    assert score["external_actions_performed"] is False
    assert score["source"]["file"] == "scripts/lead_scorer.py"


@pytest.mark.asyncio
async def test_sales_api_exposes_registry_and_shadow_score(tmp_path: Path) -> None:
    registry = build_fixture(tmp_path / "sales")
    defaults = Settings.load()
    settings = Settings(
        providers=defaults.providers,
        output_dir=tmp_path / "runs",
        timeout_seconds=defaults.timeout_seconds,
        max_retries=defaults.max_retries,
        max_context_bytes=defaults.max_context_bytes,
        runtime_dir=tmp_path / "runtime",
        local_repetitions=defaults.local_repetitions,
    )
    app = create_app(settings, output_boundary=tmp_path, sales_registry=registry)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        overview = await client.get("/v1/sales/overview")
        assert overview.status_code == 200
        assert overview.json()["mode"] == "shadow"

        scored = await client.post(
            "/v1/sales/score",
            json={
                "company": "Example",
                "budget_signals": {},
                "authority_signals": {},
                "need_signals": {},
                "timeline_signals": {},
            },
        )
        assert scored.status_code == 200
        assert scored.json()["external_actions_performed"] is False


def test_fixture_is_json_serializable(tmp_path: Path) -> None:
    registry = build_fixture(tmp_path)
    json.dumps(registry.overview(), ensure_ascii=False)

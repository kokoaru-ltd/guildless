from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from council.revenue_engine import (
    REVENUE_STAGES,
    RevenueEngine,
    RevenueEngineError,
    RevenuePlanManager,
    discover_from_github,
)


class FakeSalesRegistry:
    """4パック全部インストール済み(Sales OSS)のレジストリ偽装。"""

    def __init__(self, installed: bool = True):
        self.installed = installed

    def packs(self):
        pack_ids = [
            "b2b-sdr-agent-template",
            "ai-sales-team",
            "salesgpt-conversation",
            "gtm-marketing",
        ]
        return [
            {"id": pack_id, "installed": self.installed, "path": pack_id}
            for pack_id in pack_ids
        ]


class FakeScout:
    """GitHubScout 互換: research() が固定の候補を返す。"""

    def __init__(self):
        self.queries: list[list[str]] = []

    async def research(self, queries, constraints):
        self.queries.append(queries)
        return {
            "accepted": [
                {
                    "full_name": "example/sales-tool",
                    "html_url": "https://github.com/example/sales-tool",
                    "description": "b2b sales automation",
                    "stars": 120,
                    "score": 0.9,
                    "capabilities": ["web_search", "email_send"],
                }
            ]
        }


@pytest.fixture()
def engine() -> RevenueEngine:
    return RevenueEngine(sales_registry=FakeSalesRegistry())


@pytest.fixture()
def plan_manager(tmp_path: Path) -> RevenuePlanManager:
    return RevenuePlanManager(tmp_path / "runs")


def test_analyze_builds_backward_calc_and_funnel(engine: RevenueEngine) -> None:
    plan = engine.analyze(
        product="ホームページ改善診断レポート",
        price_yen=5_000,
        target_revenue_yen=15_000,
        budget_yen=30_000,
        deadline_days=14,
    )
    calc = plan["backward_calc"]
    assert calc["required_orders"] == 3
    assert calc["required_meetings"] == 15
    assert calc["required_contacts"] == 300
    assert calc["interested"] == 6
    assert len(plan["funnel"]) == 9
    assert len(plan["capabilities"]) == 13
    assert plan["plan_id"].startswith("rev_")
    assert plan["scout"]["status"] == "pending"


def test_workflow_covers_all_stages_and_steps(engine: RevenueEngine) -> None:
    plan = engine.analyze(product="業務用タオル", price_yen=8_000)
    workflow = plan["workflow"]
    stage_ids = {stage["stage_id"] for stage in REVENUE_STAGES}
    assert {item["stage_id"] for item in workflow} == stage_ids
    assert [item["step"] for item in workflow] == list(range(1, len(workflow) + 1))


def test_installed_sales_packs_are_primary(engine: RevenueEngine) -> None:
    plan = engine.analyze(product="営業リスト作成", price_yen=10_000)
    by_id = {cap["skill_id"]: cap for cap in plan["capabilities"]}
    market = by_id["market_research"]
    assert market["primary"]["source"] == "インストール済みOSS"
    assert market["status"] == "確保済み"
    lead = by_id["lead_generation"]
    assert lead["primary"]["source"] == "既存"
    assert lead["status"] == "確保済み"
    assert set(plan["sources"]["installed_packs"]) == {
        "ai_sales_team",
        "b2b_sdr_pipeline",
        "gtm_marketing",
        "salesgpt",
    }


def test_gaps_detected_only_for_unresolved() -> None:
    bare = RevenueEngine().analyze(product="Web診断レポート", price_yen=5_000)
    gap_ids = [gap["skill_id"] for gap in bare["gaps"]]
    assert "outreach_phone" in gap_ids
    assert "lead_generation" not in gap_ids
    # 全パック導入済みなら架電(API依存)だけが残る
    full = RevenueEngine(sales_registry=FakeSalesRegistry(installed=True)).analyze(
        product="Web診断レポート", price_yen=5_000
    )
    assert [gap["skill_id"] for gap in full["gaps"]] == ["outreach_phone"]


def test_envelope_and_human_statuses(engine: RevenueEngine) -> None:
    plan = engine.analyze(product="デジタル納品サービス", price_yen=3_000)
    by_id = {cap["skill_id"]: cap for cap in plan["capabilities"]}
    assert by_id["outreach_email"]["status"] == "承認範囲"
    assert by_id["checkout_link"]["status"] == "人間操作"
    # 人間操作・承認範囲はGitHub探索(gaps)の対象外
    gap_ids = {gap["skill_id"] for gap in plan["gaps"]}
    assert "checkout_link" not in gap_ids
    assert "outreach_email" not in gap_ids


def test_save_and_load_roundtrip(
    engine: RevenueEngine, plan_manager: RevenuePlanManager
) -> None:
    plan = engine.analyze(product="採用ページ改善", price_yen=30_000)
    plan_manager.save(plan)
    assert plan_manager.latest_id() == plan["plan_id"]
    loaded = plan_manager.load(plan["plan_id"])
    assert loaded["product"] == plan["product"]
    assert loaded["backward_calc"] == plan["backward_calc"]
    assert plan_manager.latest()["plan_id"] == plan["plan_id"]
    assert [item["plan_id"] for item in plan_manager.list_plans()] == [plan["plan_id"]]


def test_analyze_validates_product(engine: RevenueEngine) -> None:
    with pytest.raises(RevenueEngineError):
        engine.analyze(product="   ", price_yen=5_000)
    with pytest.raises(RevenueEngineError):
        engine.analyze(product="テスト", price_yen=50)
    with pytest.raises(RevenueEngineError):
        engine.analyze(product="テスト", price_yen=5_000, target_revenue_yen=50)
    with pytest.raises(RevenueEngineError):
        engine.analyze(product="テスト", price_yen=5_000, budget_yen=100)
    with pytest.raises(RevenueEngineError):
        engine.analyze(product="テスト", price_yen=5_000, deadline_days=0)


def test_plan_manager_rejects_invalid_id(plan_manager: RevenuePlanManager) -> None:
    with pytest.raises(RevenueEngineError):
        plan_manager.load("../escape")


def test_discover_from_github_attaches_candidates(engine: RevenueEngine) -> None:
    plan = engine.analyze(product="Web診断レポート", price_yen=5_000)
    assert plan["gaps"], "expected at least one gap"
    scout = FakeScout()
    updated = asyncio.run(discover_from_github(plan, scout))
    assert updated["scout"]["status"] == "done"
    assert updated["scout"]["queried_at"]
    assert len(scout.queries) == len(plan["gaps"])
    for gap in updated["gaps"]:
        assert gap["discovered_candidates"], gap["skill_id"]
        assert gap["discovered_candidates"][0]["full_name"] == "example/sales-tool"

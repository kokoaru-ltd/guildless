from __future__ import annotations

from pathlib import Path

import pytest

from council.v0_engine import V0EngineError, V0LoopManager, TERMINAL_DECISIONS


@pytest.fixture()
def manager(tmp_path: Path) -> V0LoopManager:
    return V0LoopManager(tmp_path / "runs")


def _select_first(manager: V0LoopManager, intent: str = "営業リストを作る", budget_yen: int = 30_000) -> dict:
    state = manager.start(intent, budget_yen=budget_yen)
    return manager.select(state["loop_id"], state["candidates"][0]["id"])


def test_start_stops_at_candidate_selection(manager: V0LoopManager) -> None:
    state = manager.start("割り箸事業を始めて利益を出して", budget_yen=30_000, deadline_days=14)
    assert state["stage"] == "plan"
    assert state["status"] == "awaiting_selection"
    assert len(state["candidates"]) == 6
    assert state["selected_business"] is None
    assert state["envelope"] is None


def test_select_builds_plan_to_approval_gate(manager: V0LoopManager) -> None:
    state = manager.start("割り箸事業を始めて利益を出して", budget_yen=30_000, deadline_days=14)
    selected = state["candidates"][0]["id"]
    state = manager.select(state["loop_id"], selected)
    assert state["stage"] == "envelope"
    assert state["status"] == "awaiting_approval"
    assert state["selected_business"]["id"] == selected
    assert len(state["constraint_checks"]) >= 9
    assert len(state["experiments"]) == 3
    assert state["envelope"]["status"] == "pending"
    assert state["envelope"]["budget_cap_yen"] == 30_000


def test_candidates_follow_intent_keywords(manager: V0LoopManager) -> None:
    state = manager.start("ホームページを改善したい")
    names = [candidate["name"] for candidate in state["candidates"]]
    assert "ホームページ改善診断レポート" in names


def test_select_rejects_unknown_candidate(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る")
    with pytest.raises(V0EngineError):
        manager.select(state["loop_id"], "no_such_business")


def test_select_can_change_candidate_before_approval(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る", budget_yen=30_000)
    first = state["candidates"][0]["id"]
    second = state["candidates"][1]["id"]
    state = manager.select(state["loop_id"], first)
    assert state["selected_business"]["id"] == first
    state = manager.select(state["loop_id"], second)
    assert state["selected_business"]["id"] == second
    assert state["stage"] == "envelope"
    assert state["status"] == "awaiting_approval"


def test_daily_confirm_stamps_checkin(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    assert state["checkins"] == []
    stamped = manager.daily_confirm(state["loop_id"], "候補と制約を確認した")
    assert len(stamped["checkins"]) == 1
    entry = stamped["checkins"][0]
    assert entry["stage"] == "envelope"
    assert entry["note"] == "候補と制約を確認した"
    assert entry["by"] == "human"
    assert entry["confirmed_at"]


def test_approve_runs_through_decide(manager: V0LoopManager) -> None:
    state = _select_first(manager, intent="競合調査レポートを売る")
    state = manager.approve(state["loop_id"])
    assert state["stage"] == "decide"
    assert state["status"] in TERMINAL_DECISIONS
    assert state["execution"]["simulated"] is True


def test_shadow_revenue_is_not_counted_as_revenue(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    state = manager.approve(state["loop_id"])
    assert state["ledger"]["revenue_yen"] == 0


def test_human_order_moves_revenue_ledger(manager: V0LoopManager) -> None:
    state = _select_first(manager, intent="ホームページ改善診断を売る")
    price = state["selected_business"]["price_yen"]
    state = manager.record_order(state["loop_id"], "テスト商事株式会社", price)
    assert state["ledger"]["revenue_yen"] == price
    assert len(state["ledger"]["orders"]) == 1


def test_order_price_must_match_product(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    with pytest.raises(V0EngineError):
        manager.record_order(state["loop_id"], "テスト商事", 123)


def test_deliver_creates_artifact(manager: V0LoopManager) -> None:
    state = _select_first(manager, intent="ホームページ改善診断を売る")
    price = state["selected_business"]["price_yen"]
    state = manager.record_order(state["loop_id"], "テスト商事株式会社", price)
    order_id = state["ledger"]["orders"][0]["order_id"]
    state = manager.deliver(state["loop_id"], order_id)
    order = state["ledger"]["orders"][0]
    assert order["delivered"] is True
    assert Path(order["deliverable"]).is_file()


def test_two_orders_and_profit_leads_to_scale(manager: V0LoopManager) -> None:
    state = _select_first(manager, intent="ホームページ改善診断を売る")
    price = state["selected_business"]["price_yen"]
    manager.record_order(state["loop_id"], "A社", price)
    manager.record_order(state["loop_id"], "B社", price)
    state = manager.approve(state["loop_id"])
    assert state["decision"]["verdict"] == "SCALE"


def test_kill_overrides_any_verdict(manager: V0LoopManager) -> None:
    state = _select_first(manager, intent="割り箸事業")
    state = manager.approve(state["loop_id"])
    state = manager.kill(state["loop_id"], reason="テストのため停止")
    assert state["status"] == "KILL"
    assert state["stage"] == "killed"


def test_determinism_for_same_intent(manager: V0LoopManager) -> None:
    first = manager.start("営業リストを作る", budget_yen=30_000)
    second = manager.start("営業リストを作る", budget_yen=30_000)
    first = manager.select(first["loop_id"], first["candidates"][0]["id"])
    second = manager.select(second["loop_id"], second["candidates"][0]["id"])
    approved_first = manager.approve(first["loop_id"])
    approved_second = manager.approve(second["loop_id"])
    assert approved_first["execution"]["totals"] == approved_second["execution"]["totals"]


def test_budget_validation(manager: V0LoopManager) -> None:
    with pytest.raises(V0EngineError):
        manager.start("テスト", budget_yen=100)


def test_goto_reviews_earlier_stage(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る", budget_yen=30_000)
    loop_id = state["loop_id"]
    reviewed = manager.goto(loop_id, "goal")
    assert reviewed["stage"] == "goal"
    assert reviewed["status"] == "running"
    advanced = manager.advance(loop_id)
    assert advanced["stage"] == "plan"


def test_goto_rejects_unreached_stage(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る", budget_yen=30_000)
    with pytest.raises(V0EngineError):
        manager.goto(state["loop_id"], "execute")


def test_approved_loop_can_review_envelope_and_resume(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    loop_id = state["loop_id"]
    state = manager.approve(loop_id)
    assert state["stage"] == "decide"
    reviewed = manager.goto(loop_id, "envelope")
    assert reviewed["stage"] == "envelope"
    assert reviewed["envelope"]["approved_at"] is not None
    resumed = manager.advance(loop_id)
    assert resumed["stage"] == "capability"
    resumed = manager.advance(loop_id)
    assert resumed["stage"] == "execute"


def test_review_navigation_does_not_double_count_cost(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    loop_id = state["loop_id"]
    state = manager.approve(loop_id)
    cost_before = state["ledger"]["cost_yen"]
    manager.goto(loop_id, "envelope")
    manager.advance(loop_id)  # capability
    manager.advance(loop_id)  # execute
    manager.advance(loop_id)  # observe
    final_state = manager.advance(loop_id)  # decide
    assert final_state["stage"] == "decide"
    assert final_state["ledger"]["cost_yen"] == cost_before


def test_goto_observe_then_advance_does_not_double_count(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    loop_id = state["loop_id"]
    state = manager.approve(loop_id)
    cost_before = state["ledger"]["cost_yen"]
    manager.goto(loop_id, "observe")
    final_state = manager.advance(loop_id)
    assert final_state["stage"] == "decide"
    assert final_state["ledger"]["cost_yen"] == cost_before


def test_legacy_state_without_furthest_does_not_double_count(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    loop_id = state["loop_id"]
    state = manager.approve(loop_id)
    cost_before = state["ledger"]["cost_yen"]
    # Simulate a loop saved before furthest_stage existed.
    del state["furthest_stage"]
    manager.save(state)
    manager.goto(loop_id, "goal")
    manager.advance(loop_id)  # plan
    manager.advance(loop_id)  # constraint
    manager.advance(loop_id)  # experiment
    manager.advance(loop_id)  # envelope
    manager.approve(loop_id)  # capability -> execute -> observe -> decide
    final_state = manager.latest()
    assert final_state["stage"] == "decide"
    assert final_state["ledger"]["cost_yen"] == cost_before


def test_add_capability_is_idempotent(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る", budget_yen=30_000)
    loop_id = state["loop_id"]
    state = manager.add_capability(loop_id, "決済リンク生成", "Stripe Payment Link")
    assert len(state["capabilities"]) == 1
    assert state["capabilities"][0]["status"] == "準備可"
    state = manager.add_capability(loop_id, "決済リンク生成", "Stripe Payment Link")
    assert len(state["capabilities"]) == 1


def test_add_capability_requires_name(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る", budget_yen=30_000)
    with pytest.raises(V0EngineError):
        manager.add_capability(state["loop_id"], "   ")


def test_goto_can_move_forward_to_reached_stage(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    loop_id = state["loop_id"]
    state = manager.approve(loop_id)
    assert state["stage"] == "decide"
    reviewed = manager.goto(loop_id, "goal")
    assert reviewed["stage"] == "goal"
    # Reviewing an earlier stage must not block returning to a reached stage.
    resumed = manager.goto(loop_id, "decide")
    assert resumed["stage"] == "decide"
    assert resumed["decision"] is not None


def test_goto_rejects_beyond_furthest(manager: V0LoopManager) -> None:
    state = manager.start("営業リストを作る", budget_yen=30_000)
    # start() stops at the candidate-selection plan; execution stages are not reached yet.
    assert state["stage"] == "plan"
    with pytest.raises(V0EngineError):
        manager.goto(state["loop_id"], "capability")
    with pytest.raises(V0EngineError):
        manager.goto(state["loop_id"], "execute")


def test_resolve_preserves_human_added_capability(manager: V0LoopManager) -> None:
    state = _select_first(manager)
    loop_id = state["loop_id"]
    state = manager.add_capability(loop_id, "フォーム営業", "問い合わせフォーム自動化")
    state = manager.approve(loop_id)  # capability -> execute -> observe -> decide
    names = {item["name"] for item in state["capabilities"]}
    assert "フォーム営業" in names
    count = len(state["capabilities"])
    manager.goto(loop_id, "capability")
    revisited = manager.advance(loop_id)  # re-resolve without dropping adopted parts
    names2 = {item["name"] for item in revisited["capabilities"]}
    assert "フォーム営業" in names2
    assert len(revisited["capabilities"]) == count

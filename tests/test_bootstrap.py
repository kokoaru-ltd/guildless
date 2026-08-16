"""Regression tests for zero-capital autonomous operation.

Each of these pins a way the company could stop when it should not have.
"""

import pytest

from council.capital import CapitalAllocator
from council.discovery import (
    Bottleneck,
    CapabilityLedger,
    Candidate,
    DiscoveryEngine,
)
from council.goal_run import Blocked, Goal, GoalRun, Strategy
from council.proof import Measurements
from council.resources import (
    UPFRONT_PAID_ACTIONS,
    ZERO_COST_ACTIONS,
    ResourceInventory,
    bootstrap_reason,
)
from council.self_modification import (
    ModificationRequest,
    SelfModificationPolicy,
)


SOLD = Measurements(
    contacted=20, replied=5, interested=3, payments=1, delivered=1,
    revenue_yen=30_000, direct_cost_yen=0, delivery_proof_passed=True,
)


def strategy(name, steps=None, measurements=SOLD):
    return Strategy(name, steps or [("work", lambda: None)], lambda: measurements)


# --- 1. zero cash does not end a run ---------------------------------------

def test_zero_starting_cash_does_not_terminate_a_goal_run():
    run = GoalRun(
        Goal(capital_yen=0, max_loss_yen=0),
        lambda: [strategy("free-work")],
        spent_yen=lambda: 0,
    )
    outcome = run.run()
    assert outcome.state == "succeeded"
    assert outcome.failure is None


def test_zero_cash_still_stops_once_money_is_actually_lost():
    spent = {"yen": 0}

    def strategies():
        spent["yen"] += 500
        return [strategy("costly", measurements=Measurements(delivery_proof_passed=True))]

    run = GoalRun(
        Goal(capital_yen=0, max_loss_yen=400),
        strategies,
        spent_yen=lambda: spent["yen"],
    )
    assert run.run().failure == "max_loss"


# --- 2. paid strategies disappear at zero cash ------------------------------

def test_paid_actions_are_unavailable_with_no_cash():
    broke = ResourceInventory(cash_yen=0)
    assert broke.bootstrap is True
    for action in UPFRONT_PAID_ACTIONS:
        allowed, reason = broke.can_afford(action)
        assert allowed is False
        assert "現金" in reason


def test_free_actions_remain_available_with_no_cash():
    broke = ResourceInventory(cash_yen=0)
    for action in ZERO_COST_ACTIONS:
        assert broke.can_afford(action)[0] is True
    assert broke.available_actions() == set(ZERO_COST_ACTIONS)


def test_owned_hardware_is_never_counted_as_cash():
    rich_in_kit = ResourceInventory(cash_yen=0, gpu="RTX5070Ti", local_compute=True)
    assert rich_in_kit.cash_yen == 0
    assert rich_in_kit.bootstrap is True
    assert rich_in_kit.can_afford("cloud_gpu")[0] is False
    # ...but the GPU still yields a capability.
    assert "local_media_generation" in rich_in_kit.derive_capabilities()


def test_revenue_lifts_the_company_out_of_bootstrap():
    inventory = ResourceInventory(cash_yen=0)
    inventory.record_revenue(30_000)
    assert inventory.bootstrap is False
    assert inventory.can_afford("buy_api_credits", 5_000)[0] is True


def test_inventory_derives_channels_from_what_is_owned():
    with_domain = ResourceInventory(
        cash_yen=0, email_accounts=["sales@example.jp"], owned_domains=["example.jp"]
    )
    derived = with_domain.derive_capabilities()
    assert {"form_submission", "public_company_addresses", "owned_domain"} <= derived
    assert "現金¥0" in bootstrap_reason(with_domain)


# --- 3. a failed offer causes an autonomous pivot ---------------------------

def test_a_failed_offer_pivots_without_asking():
    batches = [
        [strategy("offer-a", [("s", _blocked("build_product"))])],
        [strategy("offer-b", measurements=SOLD)],
    ]
    run = GoalRun(Goal(capital_yen=0, max_loss_yen=0), lambda: batches.pop(0) if batches else [])
    outcome = run.run()
    assert outcome.state == "succeeded"
    assert outcome.human_task is None


def _blocked(task):
    def step():
        raise Blocked(task, f"{task} で停止")

    return step


# --- 4. a capability gap triggers discovery, not a question -----------------

def test_a_capability_gap_is_resolved_by_discovery():
    ledger = CapabilityLedger()
    engine = DiscoveryEngine(
        search=lambda b: [
            Candidate("weak-tool", "oss", "github.com/a", 0),
            Candidate("good-tool", "oss", "github.com/b", 0),
        ],
        trial=lambda b, c: (c.name == "good-tool", "品質判定"),
        ledger=ledger,
    )
    result = engine.resolve(
        Bottleneck("video_quality", "アニメ納品", "10本中0本しか品質を満たさない")
    )
    assert result.resolved is True
    assert result.adopted.name == "good-tool"
    assert "video_quality" in ledger.capabilities


def test_discovery_will_not_chase_a_vague_bottleneck():
    engine = DiscoveryEngine(
        search=lambda b: [Candidate("x", "oss", "ref")],
        trial=lambda b, c: (True, ""),
        ledger=CapabilityLedger(),
    )
    result = engine.resolve(Bottleneck("", "", ""))
    assert result.resolved is False
    assert "具体的" in result.reason


def test_discovery_skips_candidates_it_cannot_afford():
    engine = DiscoveryEngine(
        search=lambda b: [Candidate("paid-saas", "service", "ref", trial_cost_yen=3_000)],
        trial=lambda b, c: (True, ""),
        ledger=CapabilityLedger(),
        affordable=lambda cost: cost == 0,
    )
    result = engine.resolve(Bottleneck("crawling", "顧客探索", "手動では遅すぎる"))
    assert result.resolved is False
    assert "資金" in result.reason


def test_a_rejected_candidate_is_not_retried():
    ledger = CapabilityLedger()
    attempts: list[str] = []

    def trial(bottleneck, candidate):
        attempts.append(candidate.name)
        return False, "改善せず"

    engine = DiscoveryEngine(
        search=lambda b: [Candidate("tool", "oss", "ref", 0)],
        trial=trial,
        ledger=ledger,
    )
    gap = Bottleneck("crawling", "顧客探索", "遅い")
    engine.resolve(gap)
    engine.resolve(gap)
    assert attempts == ["tool"]


# --- 5. revenue expands the strategy space ----------------------------------

def test_first_revenue_widens_what_can_be_attempted(tmp_path):
    wallet = CapitalAllocator(tmp_path / "c.json", initial_cash_yen=1)
    before = wallet.state.envelopes["experiment"].available_yen

    wallet.record_revenue(30_000)

    experiment = wallet.state.envelopes["experiment"]
    assert experiment.available_yen > before
    # Most of it is kept back rather than immediately spendable.
    assert wallet.state.envelopes["reserve"].allocated_yen >= 21_000
    assert wallet.request("experiment", experiment.available_yen, "次の実験").approved is True


def test_revenue_never_becomes_spendable_reserve(tmp_path):
    wallet = CapitalAllocator(tmp_path / "c.json", initial_cash_yen=1)
    wallet.record_revenue(30_000)
    assert wallet.request("reserve", 1, "少しだけ").approved is False


# --- 6. self-modification requires a measured bottleneck --------------------

def _request(capability="crawling", strategy_name="顧客探索", evidence="1件あたり40秒かかる",
             rationale="顧客探索が遅く戦略が完走しないため並列化する"):
    applied = {"n": 0}

    def apply():
        applied["n"] += 1

    return ModificationRequest(
        bottleneck=Bottleneck(capability, strategy_name, evidence),
        rationale=rationale,
        apply=apply,
        revert=lambda: None,
    ), applied


def test_self_modification_needs_a_measured_bottleneck():
    request, _ = _request(capability="", evidence="")
    assert SelfModificationPolicy().evaluate(request).allowed is False


def test_self_modification_rejects_general_improvement():
    request, applied = _request(rationale="もっと良いアーキテクチャにする")
    result = SelfModificationPolicy().apply(request, run_tests=lambda: (True, ""))
    assert result.allowed is False
    assert applied["n"] == 0


def test_a_bottleneck_backed_change_is_applied_when_tests_pass():
    request, applied = _request()
    result = SelfModificationPolicy().apply(request, run_tests=lambda: (True, "265 passed"))
    assert result.applied is True
    assert applied["n"] == 1


def test_a_change_that_breaks_the_tests_is_reverted():
    reverted = {"n": 0}
    request, _ = _request()
    request.revert = lambda: reverted.__setitem__("n", reverted["n"] + 1)
    result = SelfModificationPolicy().apply(request, run_tests=lambda: (False, "3 failed"))
    assert result.applied is False
    assert result.reverted is True
    assert reverted["n"] == 1


def test_an_edit_that_throws_is_reverted():
    reverted = {"n": 0}
    request, _ = _request()
    request.apply = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    request.revert = lambda: reverted.__setitem__("n", reverted["n"] + 1)
    result = SelfModificationPolicy().apply(request, run_tests=lambda: (True, ""))
    assert result.applied is False
    assert reverted["n"] == 1


def test_every_modification_attempt_is_logged():
    policy = SelfModificationPolicy()
    allowed, _ = _request()
    refused, _ = _request(rationale="リファクタしたい")
    policy.apply(allowed, run_tests=lambda: (True, ""))
    policy.apply(refused, run_tests=lambda: (True, ""))
    assert len(policy.log.entries) == 2
    assert {e["applied"] for e in policy.log.entries} == {"True", "False"}

from datetime import UTC, datetime, timedelta

import pytest

from council.goal_run import Blocked, ContinuationPolicy, Goal, GoalRun, Strategy
from council.proof import Measurements


PROFITABLE = Measurements(
    contacted=20, replied=5, interested=3, payments=1, delivered=1,
    revenue_yen=59_800, direct_cost_yen=3_300, delivery_proof_passed=True,
)
UNSOLD = Measurements(
    contacted=20, replied=4, interested=2, checkout_visits=1,
    payments=0, delivery_proof_passed=True,
)


def strategy(name, steps=None, measurements=UNSOLD):
    return Strategy(
        name=name,
        steps=steps if steps is not None else [("work", lambda: None)],
        measure=lambda: measurements,
    )


def blocking(task, detail="blocked"):
    def step():
        raise Blocked(task, detail)

    return step


class Clock:
    def __init__(self):
        self.at = datetime(2026, 8, 16, tzinfo=UTC)

    def __call__(self):
        return self.at

    def advance(self, **kwargs):
        self.at += timedelta(**kwargs)


# --- the regression this module exists for ----------------------------------

def test_goal_run_does_not_ask_human_about_intermediate_work():
    """Every failure here is a real one this project hit. None may reach a human."""
    hit: list[str] = []

    def note(label):
        def step():
            hit.append(label)
            raise Blocked(label, f"{label} が発生")

        return step

    batches = [
        [
            strategy("provider-down", [("research", note("research"))]),
            strategy("fabricated-quotes", [("delivery_proof", note("build_product"))]),
            strategy("legal-check", [("compliance", note("research"))]),
            strategy("cold-email-banned", [("outreach", note("send_message"))]),
            strategy("api-dead", [("integration", note("analysis"))]),
        ],
        [strategy("last-resort", measurements=PROFITABLE)],
    ]

    def strategies():
        return batches.pop(0) if batches else []

    run = GoalRun(Goal(), strategies, now=Clock())
    outcome = run.run()

    assert outcome.state == "succeeded"
    assert outcome.human_task is None
    # Every blocked step was handled internally, none of it surfaced.
    assert set(hit) == {"research", "build_product", "send_message", "analysis"}
    assert run.surface(outcome)["human_action_required"] == "NONE"


def test_no_offer_candidates_does_not_become_a_question():
    empty_rounds = [[], [], []]
    run = GoalRun(Goal(), lambda: empty_rounds.pop(0) if empty_rounds else [], now=Clock())
    outcome = run.run()
    assert outcome.state == "failed"
    assert outcome.failure == "no_viable_strategy"
    assert outcome.human_task is None


# --- the one permitted interruption -----------------------------------------

def test_identity_verification_is_the_one_thing_that_stops_a_run():
    run = GoalRun(
        Goal(),
        lambda: [strategy("payout", [("kyc", blocking("identity_verification", "本人確認が必要"))])],
        now=Clock(),
    )
    outcome = run.run()
    assert outcome.state == "awaiting_human"
    assert outcome.human_task.task == "identity_verification"
    assert run.surface(outcome)["human_action_required"] == "identity_verification"


@pytest.mark.parametrize(
    "task", ["terms_consent", "legal_signature", "bank_or_card_authorisation", "physical_world_task"]
)
def test_other_legally_human_work_also_stops_a_run(task):
    run = GoalRun(Goal(), lambda: [strategy("s", [("step", blocking(task))])], now=Clock())
    assert run.run().state == "awaiting_human"


@pytest.mark.parametrize(
    "task", ["research", "send_message", "write_copy", "customer_support", "bookkeeping"]
)
def test_machine_work_never_stops_a_run(task):
    batches = [[strategy("blocked", [("s", blocking(task))])], [strategy("next", measurements=PROFITABLE)]]
    run = GoalRun(Goal(), lambda: batches.pop(0) if batches else [], now=Clock())
    outcome = run.run()
    assert outcome.state == "succeeded"
    assert outcome.human_task is None


# --- terminal conditions ----------------------------------------------------

def test_success_is_verified_net_profit():
    run = GoalRun(Goal(), lambda: [strategy("winner", measurements=PROFITABLE)], now=Clock())
    outcome = run.run()
    assert outcome.state == "succeeded"
    assert outcome.net_yen == 56_500


def test_an_unsold_offer_is_not_success():
    batches = [[strategy("a")], []]
    run = GoalRun(Goal(), lambda: batches.pop(0) if batches else [], now=Clock())
    assert run.run().state == "failed"


def test_the_deadline_ends_the_run():
    clock = Clock()

    def strategies():
        clock.advance(days=3)
        return [strategy("slow")]

    run = GoalRun(Goal(deadline_days=7), strategies, now=clock)
    outcome = run.run()
    assert outcome.failure == "deadline"


def test_the_loss_cap_ends_the_run():
    spent = {"yen": 0}

    def strategies():
        spent["yen"] += 900
        return [strategy("costly")]

    run = GoalRun(
        Goal(max_loss_yen=2_000), strategies, spent_yen=lambda: spent["yen"], now=Clock()
    )
    outcome = run.run()
    assert outcome.failure == "max_loss"
    assert outcome.net_yen < 0


def test_the_watchdog_can_stop_a_run():
    run = GoalRun(
        Goal(), lambda: [strategy("s")], now=Clock(), watchdog=lambda: ["二重送信を検出"]
    )
    outcome = run.run()
    assert outcome.failure == "watchdog_stop"
    assert "二重送信" in outcome.reason


# --- persistence and pivoting ----------------------------------------------

def test_a_failing_strategy_is_abandoned_not_repeated():
    calls = {"n": 0}

    def counting():
        calls["n"] += 1
        raise Blocked("research", "また失敗")

    batches = [
        [strategy("bad", [("s", counting)])],
        [strategy("good", measurements=PROFITABLE)],
    ]
    run = GoalRun(Goal(), lambda: batches.pop(0) if batches else [], now=Clock())
    assert run.run().state == "succeeded"
    assert calls["n"] == 1


def test_pivot_threshold_is_configurable():
    assert ContinuationPolicy(pivot_after=2).should_pivot({"x": 2}) is True
    assert ContinuationPolicy(pivot_after=3).should_pivot({"x": 2}) is False


# --- what the user is shown -------------------------------------------------

def test_the_default_view_hides_intermediate_work():
    batches = [
        [strategy("rejected", [("s", blocking("research"))])],
        [strategy("winner", measurements=PROFITABLE)],
    ]
    run = GoalRun(Goal(), lambda: batches.pop(0) if batches else [], now=Clock())
    outcome = run.run()

    surface = run.surface(outcome)
    assert set(surface) == {
        "goal", "status", "capital_yen", "net_profit_yen",
        "human_action_required", "deadline_remaining_hours",
    }
    # The detail exists, but only on request.
    assert len(run.inspect(outcome)) >= 2

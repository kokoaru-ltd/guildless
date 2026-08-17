"""When a person is genuinely needed, and — more importantly — when they are not."""

import pytest

from council.decision_boundary import Action, Budget
from council.run_status import RunFacts, decide


def facts(**overrides):
    base = dict(delivery_proof_passed=True, budget=Budget(remaining_yen=5_000))
    base.update(overrides)
    return RunFacts(**base)


# --- the regression: reaching a person is not, by itself, a reason to stop ---

def test_ready_to_contact_prospects_just_contacts_them():
    """The defect: this used to stop and ask for an outreach grant.

    Everything is in place -- eligible prospects, a drafted message, safety
    passed, delivery proven -- and none of that is a decision the owner has to
    make. It is the work they asked for.
    """
    decision = decide(facts(
        prospects_eligible=3, message_ready=True, safety_passed=True,
    ))
    assert decision.status == "RUNNING"
    assert decision.waiting_on_human is False
    assert decision.human_required == []


def test_no_prospects_yet_is_still_running():
    decision = decide(facts(prospects_inspected=0, prospects_eligible=0))
    assert decision.status == "RUNNING"
    assert decision.human_required == []


def test_nothing_found_after_inspecting_is_guildless_own_problem():
    decision = decide(facts(prospects_eligible=0, prospects_inspected=22))
    assert decision.status == "RUNNING"
    assert "探索" in decision.current_action


def test_prospects_without_a_message_keeps_drafting():
    decision = decide(facts(prospects_eligible=5, message_ready=False))
    assert decision.status == "RUNNING"
    assert "提案文" in decision.current_action


def test_unproven_delivery_is_worked_on_not_escalated():
    decision = decide(facts(delivery_proof_passed=False, prospects_eligible=3))
    assert decision.status == "RUNNING"
    assert decision.waiting_on_human is False


# --- the one thing that does stop it ----------------------------------------

def test_an_irreversible_commitment_stops_and_names_the_figure():
    decision = decide(facts(
        prospects_eligible=3,
        pending_action=Action("spend", "広告予算を実行します", yen=1_000_000),
    ))
    assert decision.status == "HUMAN_REQUIRED"
    assert "¥1,000,000" in decision.human_required[0]["title"]
    assert decision.human_required[0]["title"].endswith("Approve")


def test_a_recoverable_action_does_not_stop_it():
    decision = decide(facts(
        prospects_eligible=3, message_ready=True,
        pending_action=Action("send_email", "1社へ送信", recipients=1),
    ))
    assert decision.status == "RUNNING"


def test_the_rest_of_the_work_continues_while_approval_is_pending():
    """A run waiting on one decision is not a run that has stopped."""
    decision = decide(facts(
        pending_action=Action("sign", "契約", legally_binding=True),
    ))
    assert "続けています" in decision.current_action


@pytest.mark.parametrize("action", [
    Action("spend", "広告", yen=9_000_000),
    Action("sign", "契約", legally_binding=True),
    Action("delete", "本番DB削除", destroys_data=True),
    Action("send", "一斉送信", recipients=10_000),
    Action("subscribe", "月額", yen=980, recurring=True),
], ids=lambda a: a.kind)
def test_each_high_stakes_decision_reaches_the_person(action):
    decision = decide(facts(pending_action=action))
    assert decision.status == "HUMAN_REQUIRED"
    assert decision.human_required[0]["task"] == action.kind
    assert decision.human_required[0]["detail"]


# --- terminal states --------------------------------------------------------

def test_real_payment_is_success():
    assert decide(facts(real_payments=1)).status == "SUCCESS"


@pytest.mark.parametrize(
    "reason", ["deadline_passed", "capital_exhausted", "strategies_exhausted"]
)
def test_running_out_ends_the_run(reason):
    assert decide(facts(**{reason: True})).status == "TERMINAL_FAILURE"


def test_success_outranks_a_pending_approval():
    decision = decide(facts(
        real_payments=1,
        pending_action=Action("spend", "広告", yen=9_000_000),
    ))
    assert decision.status == "SUCCESS"


def test_a_terminal_failure_does_not_ask_for_permission():
    decision = decide(facts(
        deadline_passed=True,
        pending_action=Action("spend", "広告", yen=9_000_000),
    ))
    assert decision.status == "TERMINAL_FAILURE"
    assert decision.human_required == []


# --- what the module must no longer know about ------------------------------

def test_the_access_boundary_is_gone():
    """Keeping it would let the old "ask before touching anything" creep back."""
    import council.run_status as module

    for name in ("at_side_effect_boundary", "may_proceed_without_grant",
                 "NON_SIDE_EFFECT_WORK"):
        assert not hasattr(module, name), f"{name} still exists"
    assert "grant_present" not in RunFacts.__dataclass_fields__

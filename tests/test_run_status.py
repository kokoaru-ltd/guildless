"""When a person is genuinely needed, and — more importantly — when they are not."""

import pytest

from council.run_status import (
    NON_SIDE_EFFECT_WORK,
    RunFacts,
    at_side_effect_boundary,
    decide,
    may_proceed_without_grant,
)


def facts(**overrides):
    base = dict(delivery_proof_passed=True)
    base.update(overrides)
    return RunFacts(**base)


# --- the regression: a missing grant is not a blockage ---------------------

def test_missing_external_grant_does_not_block_read_only_work():
    decision = decide(facts(prospects_eligible=0, prospects_inspected=22, grant_present=False))
    assert decision.status == "RUNNING"
    assert decision.waiting_on_human is False
    assert "探索" in decision.current_action


def test_no_prospects_yet_is_still_running():
    decision = decide(facts(prospects_inspected=0, prospects_eligible=0))
    assert decision.status == "RUNNING"
    assert decision.human_required == []


def test_the_grant_is_requested_only_at_the_side_effect_boundary():
    decision = decide(facts(
        prospects_eligible=3, message_ready=True, safety_passed=True, grant_present=False
    ))
    assert decision.status == "HUMAN_REQUIRED"
    assert decision.human_required[0]["task"] == "grant_external_contact"


def test_every_non_side_effect_task_continues_while_the_grant_is_missing():
    for work in NON_SIDE_EFFECT_WORK:
        assert may_proceed_without_grant(work) is True
    # Anything that reaches a person is not on that list.
    for work in ("send_email", "submit_form", "make_call", "charge_card"):
        assert may_proceed_without_grant(work) is False


# --- the boundary itself ----------------------------------------------------

@pytest.mark.parametrize(
    "missing",
    ["prospects_eligible", "message_ready", "safety_passed", "delivery_proof_passed"],
)
def test_the_boundary_needs_every_condition(missing):
    ready = dict(
        prospects_eligible=3, message_ready=True, safety_passed=True,
        delivery_proof_passed=True, grant_present=False,
    )
    ready[missing] = 0 if missing == "prospects_eligible" else False
    assert at_side_effect_boundary(RunFacts(**ready)) is False


def test_a_granted_run_is_never_at_the_boundary():
    assert at_side_effect_boundary(RunFacts(
        prospects_eligible=3, message_ready=True, safety_passed=True,
        delivery_proof_passed=True, grant_present=True,
    )) is False


def test_prospects_without_a_message_keeps_drafting():
    decision = decide(facts(prospects_eligible=5, message_ready=False, grant_present=False))
    assert decision.status == "RUNNING"
    assert "提案文" in decision.current_action


def test_unproven_delivery_is_worked_on_not_escalated():
    decision = decide(facts(delivery_proof_passed=False, prospects_eligible=3))
    assert decision.status == "RUNNING"
    assert decision.waiting_on_human is False


# --- terminal states --------------------------------------------------------

def test_real_payment_is_success():
    assert decide(facts(real_payments=1)).status == "SUCCESS"


@pytest.mark.parametrize(
    "reason", ["deadline_passed", "capital_exhausted", "strategies_exhausted"]
)
def test_running_out_ends_the_run(reason):
    assert decide(facts(**{reason: True})).status == "TERMINAL_FAILURE"


def test_success_outranks_a_missing_grant():
    decision = decide(facts(
        real_payments=1, prospects_eligible=3, message_ready=True,
        safety_passed=True, grant_present=False,
    ))
    assert decision.status == "SUCCESS"


def test_a_terminal_failure_does_not_ask_for_permission():
    decision = decide(facts(
        deadline_passed=True, prospects_eligible=3, message_ready=True,
        safety_passed=True, grant_present=False,
    ))
    assert decision.status == "TERMINAL_FAILURE"
    assert decision.human_required == []

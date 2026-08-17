"""The single contract: nothing but verified third-party money discharges it."""

import pytest

from council.discovery import Bottleneck
from council.ignition import (
    ACCEPTED_EVIDENCE,
    PROGRESS_MILESTONES,
    SUCCESS_MILESTONE,
    ContractViolation,
    IgnitionContract,
    RevenueClaim,
    Spark,
    assert_not_success,
    classify_milestone,
    judge,
)
from council.self_modification import ModificationRequest, SelfModificationPolicy


def contract(**overrides):
    base = dict(spark=Spark("昔の写真を動かせたら面白そう"), capital_yen=0, deadline_days=7)
    base.update(overrides)
    return IgnitionContract(**base)


def claim(**overrides):
    base = dict(
        amount_yen=500, evidence_kind="stripe_webhook_verified",
        evidence_reference="evt_1", delivered=True, direct_cost_yen=120,
        live=True,
    )
    base.update(overrides)
    return RevenueClaim(**base)


# --- the spark is allowed to be almost nothing ------------------------------

def test_an_idle_thought_is_a_valid_input():
    assert Spark("AIで昔の写真を動かせたら面白そう").viable() is True


def test_a_spare_resource_alone_is_a_valid_input():
    assert Spark(available_resources=("余っているGPU",)).viable() is True


def test_an_empty_spark_is_not():
    assert Spark().viable() is False


def test_the_contract_states_itself_in_one_sentence():
    text = contract(capital_yen=5_000).describe()
    assert "火種" in text and "第三者からの実入金" in text


# --- every impressive milestone is merely progress --------------------------

@pytest.mark.parametrize("milestone", PROGRESS_MILESTONES)
def test_no_milestone_short_of_payment_is_success(milestone):
    assert classify_milestone(milestone) == "progress"


@pytest.mark.parametrize(
    "milestone",
    ["store_published", "landing_page_live", "outreach_sent", "meeting_booked",
     "checkout_button_clicked", "customer_said_yes"],
)
def test_the_usual_false_finish_lines_are_not_success(milestone):
    assert classify_milestone(milestone) != "business_success"


def test_only_provider_confirmed_payment_is_success():
    assert classify_milestone(SUCCESS_MILESTONE) == "business_success"


def test_an_invented_milestone_is_not_success():
    assert classify_milestone("everything_went_great") == "not_started"


def test_code_cannot_declare_itself_finished():
    with pytest.raises(ContractViolation):
        assert_not_success(SUCCESS_MILESTONE)
    # Progress markers pass straight through.
    assert_not_success("outreach_sent") is None


# --- judging ----------------------------------------------------------------

def test_nothing_claimed_is_not_started():
    assert judge(contract(), None).outcome == "not_started"


def test_a_verified_delivered_profitable_payment_discharges_the_contract():
    verdict = judge(contract(), claim())
    assert verdict.outcome == "business_success"
    assert verdict.net_yen == 380
    assert verdict.milestone == SUCCESS_MILESTONE


def test_one_yen_is_enough_when_it_is_real():
    verdict = judge(contract(), claim(amount_yen=1, direct_cost_yen=0))
    assert verdict.outcome == "business_success"


@pytest.mark.parametrize(
    "evidence", ["agent_reported", "llm_said_so", "internal_database", ""]
)
def test_self_reported_revenue_is_never_accepted(evidence):
    verdict = judge(contract(), claim(evidence_kind=evidence))
    assert verdict.outcome == "progress"
    assert "外部証拠として認められません" in verdict.reason


@pytest.mark.parametrize("evidence", sorted(ACCEPTED_EVIDENCE))
def test_each_accepted_evidence_kind_works(evidence):
    assert judge(contract(), claim(evidence_kind=evidence)).outcome == "business_success"


def test_payment_without_delivery_is_only_progress():
    verdict = judge(contract(), claim(delivered=False))
    assert verdict.outcome == "progress"
    assert "納品" in verdict.reason


def test_a_sale_that_lost_money_is_only_progress():
    verdict = judge(contract(), claim(amount_yen=500, direct_cost_yen=900))
    assert verdict.outcome == "progress"
    assert verdict.net_yen == -400


def test_below_the_minimum_is_only_progress():
    verdict = judge(contract(minimum_revenue_yen=1_000), claim(amount_yen=500))
    assert verdict.outcome == "progress"


def test_a_contract_may_waive_delivery_but_not_evidence():
    lenient = contract(require_delivery=False, require_positive_net=False)
    assert judge(lenient, claim(delivered=False, direct_cost_yen=9_999)).outcome == "business_success"
    assert judge(lenient, claim(evidence_kind="agent_reported")).outcome == "progress"


# --- the contract cannot be rewritten by the system -------------------------

def test_the_contract_is_immutable():
    with pytest.raises(Exception):
        contract().minimum_revenue_yen = 0  # type: ignore[misc]


def test_self_modification_cannot_edit_the_definition_of_success():
    request = ModificationRequest(
        bottleneck=Bottleneck("revenue", "販売", "入金が出ない"),
        rationale="入金が出ないため成功条件を緩めて前進させる",
        apply=lambda: None, revert=lambda: None,
        targets=("council/ignition.py",),
    )
    result = SelfModificationPolicy().evaluate(request)
    assert result.allowed is False
    assert "自己改造できません" in result.reason


def test_self_modification_cannot_edit_the_sender_identity():
    request = ModificationRequest(
        bottleneck=Bottleneck("outreach", "営業", "送信者情報が足りない"),
        rationale="送信者情報が不足しているため補完処理を追加する",
        apply=lambda: None, revert=lambda: None,
        targets=("council/sender_identity.py",),
    )
    assert SelfModificationPolicy().evaluate(request).allowed is False


# --- test-mode money is a working pipeline, not a business ------------------

def test_a_test_mode_payment_is_not_success():
    """Every signature genuine, every webhook real, no money moved."""
    verdict = judge(contract(), claim(live=False))
    assert verdict.outcome == "progress"
    assert "テストモード" in verdict.reason


def test_the_same_payment_in_live_mode_is_success():
    assert judge(contract(), claim(live=True)).outcome == "business_success"


def test_test_mode_is_the_default_so_it_must_be_asserted():
    assert RevenueClaim(amount_yen=1, evidence_kind="stripe_webhook_verified").live is False

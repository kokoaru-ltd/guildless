import pytest

from council.proof import Measurements
from council.revenue_loop import (
    Offer,
    OfferCriteria,
    LoopError,
    RevenueLoop,
    screen_offers,
)


def offer(**overrides):
    base = dict(
        offer_id="o1", name="AIアニメ10秒 納品", outcome_value_yen=30_000,
        build_cost_yen=1_500, delivery_hours=24, legal_risk="low",
        customer_reachable=True, requires_human_digital_work=False,
    )
    base.update(overrides)
    return Offer(**base)


@pytest.fixture
def loop(tmp_path):
    return RevenueLoop(tmp_path / "loop.json")


# --- offer screening --------------------------------------------------------

def test_a_cheap_offer_is_rejected_on_value():
    passed, rejected = screen_offers([offer(outcome_value_yen=500)])
    assert passed == []
    assert "下限" in rejected[0]["reasons"][0]


def test_an_expensive_build_is_rejected():
    passed, _ = screen_offers([offer(build_cost_yen=20_000)])
    assert passed == []


def test_slow_delivery_is_rejected():
    passed, _ = screen_offers([offer(delivery_hours=200)])
    assert passed == []


def test_legal_risk_is_rejected():
    passed, _ = screen_offers([offer(legal_risk="high")])
    assert passed == []


def test_an_unreachable_customer_is_rejected():
    passed, _ = screen_offers([offer(customer_reachable=False)])
    assert passed == []


def test_requiring_human_digital_work_is_rejected():
    passed, _ = screen_offers([offer(requires_human_digital_work=True)])
    assert passed == []


def test_a_qualifying_offer_passes():
    passed, rejected = screen_offers([offer()])
    assert len(passed) == 1 and rejected == []


def test_criteria_can_be_relaxed_by_the_human():
    passed, _ = screen_offers(
        [offer(outcome_value_yen=5_000)],
        OfferCriteria(min_outcome_value_yen=1_000),
    )
    assert len(passed) == 1


# --- one offer at a time ----------------------------------------------------

def test_three_candidates_produce_exactly_one_running_offer(loop):
    chosen = loop.select_offer([
        offer(offer_id="a", name="A", build_cost_yen=4_000),
        offer(offer_id="b", name="B", build_cost_yen=1_000),
        offer(offer_id="c", name="C", build_cost_yen=2_000),
    ])
    assert chosen.offer_id == "b"
    assert loop.state.offer["name"] == "B"


def test_a_second_offer_cannot_start_while_one_runs(loop):
    loop.select_offer([offer()])
    with pytest.raises(LoopError) as raised:
        loop.select_offer([offer(offer_id="o2")])
    assert "1つしか" in str(raised.value)


def test_no_qualifying_candidate_stops_the_loop(loop):
    with pytest.raises(LoopError):
        loop.select_offer([offer(outcome_value_yen=500)])
    assert loop.state.rejected_offers


# --- delivery proof gates selling -------------------------------------------

def test_selling_is_impossible_before_delivery_is_proven(loop):
    loop.select_offer([offer()])
    loop.state.stage = "customer_search"
    with pytest.raises(LoopError) as raised:
        loop.advance()
    assert "納品証明" in str(raised.value)


def test_failed_delivery_proof_kills_the_offer_before_any_outreach(loop):
    loop.select_offer([offer()])
    loop.record_delivery_proof(passed=False, evidence="10本生成して納品可能0本")
    assert loop.state.stage == "killed"
    assert loop.state.failure == "DELIVERY_FAILURE"


def test_delivery_proof_needs_actual_evidence(loop):
    loop.select_offer([offer()])
    with pytest.raises(LoopError):
        loop.record_delivery_proof(passed=True, evidence="   ")


def test_passing_delivery_proof_opens_customer_search(loop):
    loop.select_offer([offer()])
    loop.record_delivery_proof(passed=True, evidence="10本中8本が納品品質")
    assert loop.state.stage == "customer_search"


# --- the full path ----------------------------------------------------------

def test_the_loop_reaches_profit_only_on_delivered_profitable_revenue(loop):
    loop.select_offer([offer()])
    loop.record_delivery_proof(passed=True, evidence="10本中8本が納品品質")
    for _ in range(3):
        loop.advance()
    assert loop.state.stage == "delivery"

    # Profit cannot be walked to; it has to be earned and measured.
    with pytest.raises(LoopError):
        loop.advance()

    loop.record_measurements(Measurements(
        contacted=20, replied=5, interested=3, checkout_visits=2,
        payments=1, delivered=1, revenue_yen=30_000, direct_cost_yen=1_400,
    ))
    result = loop.evaluate_proof()
    assert result.passed is True
    assert loop.state.stage == "profit"
    assert loop.summary()["net_yen"] == 28_600


def test_interest_without_payment_is_recorded_as_conversion_failure(loop):
    loop.select_offer([offer()])
    loop.record_delivery_proof(passed=True, evidence="納品品質を確認")
    loop.record_measurements(Measurements(
        contacted=20, replied=5, interested=3, checkout_visits=2, payments=0,
    ))
    result = loop.evaluate_proof()
    assert result.passed is False
    assert loop.state.failure == "CONVERSION_FAILURE"
    assert "価格" in loop.state.failure_meaning


def test_the_slot_frees_only_after_the_loop_ends(loop):
    loop.select_offer([offer()])
    with pytest.raises(LoopError):
        loop.reset_for_next_offer()

    loop.record_delivery_proof(passed=False, evidence="作れなかった")
    loop.reset_for_next_offer()
    assert loop.state.offer is None
    loop.select_offer([offer(offer_id="next")])


def test_state_survives_a_restart(tmp_path):
    path = tmp_path / "loop.json"
    first = RevenueLoop(path)
    first.select_offer([offer()])
    first.record_delivery_proof(passed=True, evidence="納品確認")

    reopened = RevenueLoop(path)
    assert reopened.state.stage == "customer_search"
    assert reopened.state.delivery_proof_passed is True

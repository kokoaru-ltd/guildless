"""The loop does business, and simulated money never becomes revenue."""

import pytest

from council.operator import BATCH, SEND_PER_PASS, Operator
from council.world import Prospect, Receipt, Reply, SimulatedWorld


@pytest.fixture
def operator():
    return Operator(world=SimulatedWorld(), offer="Jiraバックログ作成", price_yen=59_800,
                    capital_yen=5_000)


def run(operator, passes: int) -> list[str]:
    said = []
    for _ in range(passes):
        for _name, step in operator.steps():
            said.append(step())
    return [line for line in said if line]


# --- the regression: it must actually do something --------------------------

def test_a_single_pass_inspects_real_companies(operator):
    operator.discover()
    assert operator.ledger.inspected == BATCH


def test_the_business_advances_over_time(operator):
    """The defect this replaces: a loop where nothing ever changed."""
    run(operator, 40)
    ledger = operator.ledger
    assert ledger.inspected > 0
    assert ledger.eligible, "discovery never qualified anybody"
    assert ledger.contacted, "nobody was ever contacted"
    assert ledger.replied, "no reply ever arrived"


def test_it_reaches_money(operator):
    run(operator, 60)
    assert operator.ledger.quoted, "nobody was ever asked to pay"
    assert operator.ledger.simulated_sales > 0, "the loop never closed a sale"


def test_the_funnel_only_ever_narrows(operator):
    run(operator, 50)
    ledger = operator.ledger
    assert ledger.inspected >= len(ledger.eligible)
    assert len(ledger.eligible) >= len(ledger.contacted)
    assert len(ledger.contacted) >= len(ledger.replied)
    assert len(ledger.replied) >= len(ledger.interested)


# --- simulated money is not revenue -----------------------------------------

def test_simulated_sales_never_touch_cash(operator):
    """The property that makes it safe to develop against a simulation."""
    run(operator, 60)
    assert operator.ledger.simulated_cash_yen > 0
    assert operator.ledger.cash_yen == 0


def test_simulated_money_is_labelled_where_it_is_reported(operator):
    lines = run(operator, 60)
    banked = [line for line in lines if "模擬売上" in line]
    assert banked, "no simulated sale was ever reported"
    assert all("実収益には数えません" in line for line in banked)


def test_a_real_receipt_does_reach_cash():
    from council.operator import Ledger, _record

    ledger = Ledger()
    _record(ledger, [Receipt("客", 300_000, "stripe_webhook_verified", simulated=False)])
    assert ledger.cash_yen == 300_000
    assert ledger.simulated_cash_yen == 0


def test_a_mixed_batch_is_split_correctly():
    from council.operator import Ledger, _record

    ledger = Ledger()
    line = _record(ledger, [
        Receipt("A", 300_000, "stripe_webhook_verified", simulated=False),
        Receipt("B", 59_800, "simulated_world", simulated=True),
    ])
    assert ledger.cash_yen == 300_000
    assert ledger.simulated_cash_yen == 59_800
    assert "入金 1件" in line and "模擬売上 1件" in line


# --- it never invents progress ----------------------------------------------

def test_a_pass_with_no_offer_says_nothing():
    quiet = Operator(world=SimulatedWorld(), offer="", price_yen=0)
    assert quiet.discover() == ""


def test_a_pass_with_nobody_to_contact_says_nothing(operator):
    assert operator.reach_out() == ""


def test_no_replies_is_silence_not_a_sentence(operator):
    assert operator.read_replies() == ""


def test_a_dead_discovery_pass_names_the_commonest_reason():
    """"0 found" is not actionable; the reason is."""
    barren = Operator(
        world=SimulatedWorld(eligible_rate=0.0), offer="何か", price_yen=1_000
    )
    line = barren.discover()
    assert "条件に合う相手はなし" in line
    assert "最多の理由" in line


# --- the decision boundary is respected -------------------------------------

def test_ordinary_outreach_never_stops_to_ask(operator):
    lines = run(operator, 30)
    assert not any("承認待ち" in line for line in lines)


def test_a_batch_never_exceeds_the_per_pass_limit(operator):
    operator.discover()
    operator.discover()
    operator.discover()
    before = len(operator.ledger.contacted)
    operator.reach_out()
    assert len(operator.ledger.contacted) - before <= SEND_PER_PASS


def test_the_run_stops_when_cumulative_reach_gets_large():
    """A hundred small batches must not reach ten thousand people unnoticed."""
    from council.decision_boundary import RECIPIENTS_PER_RUN

    busy = Operator(world=SimulatedWorld(eligible_rate=1.0), offer="x", price_yen=100)
    busy.ledger.contacted = [f"c{n}" for n in range(RECIPIENTS_PER_RUN)]
    busy.discover()
    assert "承認待ち" in busy.reach_out()


# --- the same company every time --------------------------------------------

def test_the_simulation_is_deterministic():
    """A world seeded by the clock makes every change look like a regression."""
    first = Operator(world=SimulatedWorld(), offer="同じ提案", price_yen=1_000)
    second = Operator(world=SimulatedWorld(), offer="同じ提案", price_yen=1_000)
    run(first, 30)
    run(second, 30)
    assert first.ledger.as_dict() == second.ledger.as_dict()


def test_a_different_offer_produces_a_different_company():
    a = Operator(world=SimulatedWorld(), offer="提案A", price_yen=1_000)
    b = Operator(world=SimulatedWorld(), offer="提案B", price_yen=1_000)
    run(a, 20)
    run(b, 20)
    assert a.ledger.excluded != b.ledger.excluded or a.ledger.inspected != b.ledger.inspected


# --- the simulation is hard, not flattering ---------------------------------

def test_most_discovered_companies_do_not_qualify(operator):
    run(operator, 30)
    ledger = operator.ledger
    assert len(ledger.eligible) < ledger.inspected * 0.5


def test_most_contacts_never_reply(operator):
    run(operator, 60)
    ledger = operator.ledger
    assert len(ledger.replied) < len(ledger.contacted) * 0.5


# --- prospects always carry a source ----------------------------------------

def test_every_discovered_prospect_names_where_it_came_from():
    """A prospect without an observed origin is a guessed URL."""
    world = SimulatedWorld()
    for prospect in world.find_prospects("何か", 20):
        assert prospect.source


def test_the_same_company_is_never_contacted_twice(operator):
    run(operator, 60)
    assert len(operator.ledger.contacted) == len(set(operator.ledger.contacted))

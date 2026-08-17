"""A bet's status is measured, not chosen — and effort never promotes it."""

import pytest

from council.bets import FAIR_TRIAL_CONTACTS, Bet, Portfolio


def bet(**overrides):
    base = dict(id="b1", name="AI導入PoC")
    base.update(overrides)
    return Bet(**base)


# --- status comes from what happened ----------------------------------------

def test_nothing_attempted_is_watch():
    assert bet().status == "WATCH"


def test_a_reply_makes_it_alive():
    assert bet(contacted=10, replied=1).status == "TEST"


def test_a_quote_outranks_a_reply():
    assert bet(contacted=10, replied=3, quoted=1).status == "SCALE"


def test_only_arrived_money_is_paying():
    assert bet(contacted=10, replied=3, quoted=2, cash_yen=300_000).status == "PAYING"


def test_a_fair_trial_with_no_reply_is_killed():
    assert bet(contacted=FAIR_TRIAL_CONTACTS).status == "KILLED"


def test_silence_below_a_fair_trial_is_not_a_verdict():
    """Killing an idea after four emails throws away merely unlucky ideas."""
    assert bet(contacted=FAIR_TRIAL_CONTACTS - 1).status == "WATCH"
    assert "判断には" in bet(contacted=4).why()


def test_paying_survives_everything():
    """Money that arrived is not undone by a later bad patch."""
    assert bet(cash_yen=1, contacted=10_000, killed_because="やめた").status == "PAYING"


# --- effort must never promote a bet ----------------------------------------

@pytest.mark.parametrize("contacted", [50, 500, 5_000])
def test_more_contacts_alone_never_improve_the_status(contacted):
    """The failure mode of a struggling company is producing effort."""
    assert bet(contacted=contacted).status == "KILLED"


def test_activity_without_answers_reads_as_a_finished_trial():
    assert "十分試したので止めます" in bet(contacted=200).why()


# --- money ------------------------------------------------------------------

def test_net_is_cash_minus_spend():
    assert bet(cash_yen=300_000, spent_yen=4_820).net_yen == 295_180


def test_a_bet_that_cost_more_than_it_made_shows_negative():
    assert bet(cash_yen=1_000, spent_yen=9_000).net_yen == -8_000


def test_why_leads_with_cash_when_there_is_cash():
    assert "300,000円" in bet(cash_yen=300_000, contacted=90).why()


# --- the portfolio ----------------------------------------------------------

@pytest.fixture
def portfolio():
    return Portfolio(bets=[
        bet(id="paid", name="AI導入PoC", cash_yen=300_000, spent_yen=4_820,
            contacted=90, replied=19, meetings=5, quoted=2, pipeline_yen=900_000),
        bet(id="test", name="営業自動化", contacted=40, replied=3, pipeline_yen=0),
        bet(id="watch", name="YouTube", contacted=0),
        bet(id="dead", name="Micro SaaS", contacted=60,
            killed_because="60件接触して返信0件", pipeline_yen=500_000),
    ])


def test_the_best_bet_is_listed_first(portfolio):
    assert portfolio.ranked()[0].id == "paid"


def test_the_dead_bet_is_listed_last(portfolio):
    assert portfolio.ranked()[-1].id == "dead"


def test_focus_goes_to_the_bet_with_evidence(portfolio):
    assert portfolio.focus().id == "paid"


def test_focus_ignores_dead_bets():
    only_dead = Portfolio(bets=[bet(id="d", killed_because="x")])
    assert only_dead.focus() is None


def test_focus_prefers_a_replying_bet_over_an_untried_one():
    two = Portfolio(bets=[
        bet(id="untried", contacted=0),
        bet(id="replying", contacted=10, replied=2),
    ])
    assert two.focus().id == "replying"


def test_pipeline_excludes_abandoned_bets(portfolio):
    """A quote on an idea nobody is pursuing is not expected revenue."""
    assert portfolio.pipeline_yen == 900_000
    assert all(b.pipeline_yen != 500_000 for b in portfolio.live)


def test_the_funnel_counts_people_not_money(portfolio):
    assert portfolio.funnel == {
        "contacted": 190, "replied": 22, "meetings": 5, "quoted": 2, "paid": 1,
    }


def test_cash_and_spend_sum_across_every_bet(portfolio):
    assert portfolio.cash_yen == 300_000
    assert portfolio.spent_yen == 4_820


def test_the_decision_names_the_bet_and_its_evidence(portfolio):
    decision = portfolio.decision()
    assert "AI導入PoC" in decision
    assert "300,000円" in decision


def test_an_empty_portfolio_says_so_rather_than_inventing_a_plan():
    empty = Portfolio()
    assert empty.decision() == "まだ賭けがありません"
    assert empty.cash_yen == 0
    assert empty.pipeline_yen == 0
    assert empty.funnel["paid"] == 0


def test_the_serialised_form_carries_the_status_and_the_reason(portfolio):
    data = portfolio.as_dict()
    first = data["bets"][0]
    assert first["status"] == "PAYING"
    assert first["why"]
    assert data["focus_id"] == "paid"

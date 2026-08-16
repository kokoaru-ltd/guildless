import pytest

from council.capital import CapitalAllocator, CapitalError


@pytest.fixture
def wallet(tmp_path):
    return CapitalAllocator(tmp_path / "capital.json", initial_cash_yen=10_000)


def test_cash_is_split_without_losing_a_yen(wallet):
    total = sum(e.allocated_yen for e in wallet.state.envelopes.values())
    assert total == 10_000
    assert wallet.cash_yen == 10_000
    assert wallet.net_yen == 0


def test_reserve_envelope_can_never_be_spent(wallet):
    decision = wallet.request("reserve", 1, "とにかく使いたい")
    assert decision.approved is False
    assert "留保金" in decision.reason


def test_spending_beyond_an_envelope_is_denied_not_raised(wallet):
    decision = wallet.request("experiment", 999_999, "広告")
    assert decision.approved is False
    assert wallet.spent_yen == 0


def test_a_council_conclusion_cannot_beat_the_wallet(wallet):
    """The whole point: being told to spend does not create budget."""
    first = wallet.request("experiment", 2_000, "広告A")
    assert first.approved is True
    second = wallet.request("experiment", 3_000, "壁打ちが使うべきと結論した広告B")
    assert second.approved is False
    assert "足りません" in second.reason


def test_unknown_envelope_is_denied(wallet):
    assert wallet.request("slush_fund", 100, "…").approved is False


def test_reserved_money_is_not_available_to_others(wallet):
    experiment = wallet.state.envelopes["experiment"]
    before = experiment.available_yen
    wallet.request("experiment", 500, "先約")
    assert experiment.available_yen == before - 500
    assert experiment.spent_yen == 0


def test_commit_turns_a_hold_into_spend(wallet):
    decision = wallet.request("experiment", 800, "送信費")
    wallet.commit(decision.reservation.reservation_id, 620)
    experiment = wallet.state.envelopes["experiment"]
    assert experiment.spent_yen == 620
    assert experiment.reserved_yen == 0
    assert wallet.cash_yen == 10_000 - 620


def test_release_returns_money_when_the_action_never_happened(wallet):
    experiment = wallet.state.envelopes["experiment"]
    before = experiment.available_yen
    decision = wallet.request("experiment", 800, "送信費")
    wallet.release(decision.reservation.reservation_id)
    assert experiment.available_yen == before
    assert wallet.spent_yen == 0


def test_cannot_commit_more_than_was_reserved(wallet):
    decision = wallet.request("experiment", 500, "送信費")
    with pytest.raises(CapitalError):
        wallet.commit(decision.reservation.reservation_id, 900)


def test_a_reservation_cannot_be_settled_twice(wallet):
    decision = wallet.request("experiment", 500, "送信費")
    wallet.commit(decision.reservation.reservation_id)
    with pytest.raises(CapitalError):
        wallet.commit(decision.reservation.reservation_id)
    with pytest.raises(CapitalError):
        wallet.release(decision.reservation.reservation_id)


def test_confirmed_revenue_raises_the_ceiling(wallet):
    wallet.record_revenue(5_000)
    assert wallet.state.revenue_yen == 5_000
    assert wallet.cash_yen == 15_000
    assert wallet.net_yen == 5_000
    assert wallet.request("experiment", 5_500, "次の実験").approved is True


def test_revenue_must_be_real_money(wallet):
    with pytest.raises(CapitalError):
        wallet.record_revenue(0)


def test_net_is_negative_while_spending_without_income(wallet):
    decision = wallet.request("ai_api", 400, "推論費")
    wallet.commit(decision.reservation.reservation_id)
    assert wallet.net_yen == -400


def test_state_survives_a_restart(tmp_path):
    path = tmp_path / "capital.json"
    first = CapitalAllocator(path, initial_cash_yen=10_000)
    decision = first.request("experiment", 700, "送信費")
    first.commit(decision.reservation.reservation_id)
    first.record_revenue(1_200)

    reopened = CapitalAllocator(path)
    assert reopened.spent_yen == 700
    assert reopened.state.revenue_yen == 1_200
    assert reopened.cash_yen == 10_500


def test_reopening_with_different_funding_is_refused(tmp_path):
    path = tmp_path / "capital.json"
    CapitalAllocator(path, initial_cash_yen=10_000)
    with pytest.raises(CapitalError):
        CapitalAllocator(path, initial_cash_yen=50_000)


def test_a_new_wallet_needs_funding(tmp_path):
    with pytest.raises(CapitalError):
        CapitalAllocator(tmp_path / "capital.json")

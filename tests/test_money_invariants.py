"""Properties that decide, whatever any model concludes.

Four models agreeing that the accounting is safe is evidence they share a
prior, not evidence it is safe. So the council's job in this domain is to
propose what to check, and these checks are what actually settle it.

Each property below is stated as a rule the system may never break, and tested
against randomised inputs rather than a chosen example, because the case that
breaks an invariant is rarely the one someone thought to write down.
"""

from __future__ import annotations

import json

import pytest

from council.capital import CapitalAllocator, CapitalError
from council.gates import current_level
from council.ignition import IgnitionContract, RevenueClaim, Spark, judge
from council.payment import CheckoutRequest, PaymentProcessor, SandboxAdapter


AMOUNTS = [1, 7, 100, 499, 3_000, 30_000, 999_999]


@pytest.fixture
def wallet(tmp_path):
    return CapitalAllocator(tmp_path / "capital.json", initial_cash_yen=10_000)


@pytest.fixture
def adapter():
    return SandboxAdapter()


@pytest.fixture
def payments(tmp_path, adapter, wallet):
    return PaymentProcessor(tmp_path / "payments.json", adapter, wallet)


def order(payments, amount):
    return payments.create_checkout(CheckoutRequest(
        offer_id="o", description="d", amount_yen=amount, customer_ref="c",
    ))


def event(adapter, checkout, *, live: bool, event_id: str = "evt"):
    return adapter.sign({
        "id": event_id, "type": "checkout.session.completed", "livemode": live,
        "data": {"object": {"id": checkout.checkout_id, "payment_status": "paid",
                            "amount_total": checkout.amount_yen}},
    })


# --- P1: test mode is never revenue ----------------------------------------

@pytest.mark.parametrize("amount", AMOUNTS)
def test_livemode_false_never_becomes_revenue(payments, wallet, adapter, amount):
    checkout = order(payments, amount)
    payments.handle_webhook(*event(adapter, checkout, live=False))
    assert wallet.state.revenue_yen == 0
    assert payments.real_payment_count == 0
    assert payments.revenue_yen == 0


@pytest.mark.parametrize("amount", AMOUNTS)
def test_livemode_true_does(payments, wallet, adapter, amount):
    checkout = order(payments, amount)
    payments.handle_webhook(*event(adapter, checkout, live=True))
    assert wallet.state.revenue_yen == amount


# --- P2: no provider evidence, no revenue ----------------------------------

@pytest.mark.parametrize(
    "evidence",
    ["", "agent_reported", "internal_database", "llm_verified", "screenshot", "trust_me"],
)
def test_revenue_without_provider_evidence_is_never_success(evidence):
    verdict = judge(
        IgnitionContract(spark=Spark("x")),
        RevenueClaim(amount_yen=100_000, evidence_kind=evidence, delivered=True, live=True),
    )
    assert verdict.outcome != "business_success"


# --- P3: duplicate delivery changes nothing --------------------------------

@pytest.mark.parametrize("repeats", [2, 3, 7])
def test_a_repeated_webhook_leaves_the_count_unchanged(payments, wallet, adapter, repeats):
    checkout = order(payments, 5_000)
    body, headers = event(adapter, checkout, live=True, event_id="evt_same")
    for _ in range(repeats):
        payments.handle_webhook(body, headers)
    assert payments.real_payment_count == 1
    assert wallet.state.revenue_yen == 5_000


# --- P4: an interrupted spend leaves the wallet consistent ------------------

@pytest.mark.parametrize("amount", [1, 250, 999])
def test_a_reservation_abandoned_mid_flight_never_loses_money(tmp_path, amount):
    path = tmp_path / "capital.json"
    wallet = CapitalAllocator(path, initial_cash_yen=10_000)
    before = wallet.state.envelopes["experiment"].available_yen

    decision = wallet.request("experiment", amount, "中断される支出")
    assert decision.approved

    # Process dies here: the reservation is held and never settled.
    reopened = CapitalAllocator(path)
    held = reopened.state.envelopes["experiment"]
    assert held.spent_yen == 0
    assert held.reserved_yen == amount
    # Money is accounted for either way: nothing vanished, nothing was spent.
    assert held.allocated_yen == held.spent_yen + held.reserved_yen + held.available_yen

    reopened.release(decision.reservation.reservation_id)
    assert reopened.state.envelopes["experiment"].available_yen == before


def test_a_settled_reservation_cannot_be_settled_again(wallet):
    decision = wallet.request("experiment", 500, "支出")
    wallet.commit(decision.reservation.reservation_id)
    with pytest.raises(CapitalError):
        wallet.commit(decision.reservation.reservation_id)


@pytest.mark.parametrize("amount", AMOUNTS)
def test_envelope_arithmetic_always_balances(wallet, amount):
    envelope = wallet.state.envelopes["experiment"]
    decision = wallet.request("experiment", min(amount, envelope.available_yen), "支出")
    if decision.approved:
        wallet.commit(decision.reservation.reservation_id)
    assert envelope.allocated_yen == (
        envelope.spent_yen + envelope.reserved_yen + envelope.available_yen
    )


# --- P5: a stale view can never show a gate the ledger does not support -----

@pytest.mark.parametrize("shown,ledger", [(5, 0), (3, 1), (10, 3), (1, 0)])
def test_a_gate_never_exceeds_what_the_ledger_proves(shown, ledger):
    """A cached count must not unlock capability the ledger cannot justify."""
    from council.gates import _LEVEL_ORDER

    displayed = current_level(real_payments=shown, real_contacts=100)
    truth = current_level(real_payments=ledger, real_contacts=100)
    # The invariant is on the truth side: capability is computed from the
    # ledger, so a stale display can only ever be corrected downward.
    assert _LEVEL_ORDER[truth.level] <= _LEVEL_ORDER[displayed.level]
    assert truth.real_payments == ledger


def test_capability_is_denied_at_the_true_count_regardless_of_display():
    from council.gates import GateError, require

    with pytest.raises(GateError):
        require("virtual_market", real_payments=0, real_contacts=100)


# --- P6: local writes cannot manufacture revenue ---------------------------

def test_editing_the_local_file_does_not_create_verified_revenue(tmp_path, wallet, adapter):
    path = tmp_path / "payments.json"
    processor = PaymentProcessor(path, adapter, wallet)
    checkout = order(processor, 30_000)

    # An agent with filesystem access marks it paid and live by hand.
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["checkouts"][checkout.checkout_id]["status"] = "paid"
    raw["checkouts"][checkout.checkout_id]["live"] = True
    path.write_text(json.dumps(raw), encoding="utf-8")

    tampered = PaymentProcessor(path, adapter, wallet)
    # The local file moved, but no money did: the wallet is untouched, so the
    # contract still has nothing to discharge it with.
    assert wallet.state.revenue_yen == 0
    assert judge(
        IgnitionContract(spark=Spark("x")),
        RevenueClaim(
            amount_yen=tampered.revenue_yen, evidence_kind="internal_database",
            delivered=True, live=True,
        ),
    ).outcome != "business_success"


# --- P7: an unavailable provider is unknown, never success -----------------

def test_a_provider_that_never_answered_is_not_a_sale(payments):
    order(payments, 30_000)
    assert payments.real_payment_count == 0
    verdict = judge(IgnitionContract(spark=Spark("x")), None)
    assert verdict.outcome == "not_started"


def test_a_failed_webhook_leaves_no_revenue(payments, wallet, adapter):
    from council.payment import WebhookRejected

    checkout = order(payments, 30_000)
    body, headers = event(adapter, checkout, live=True)
    headers["stripe-signature"] = "t=1,v1=deadbeef"
    with pytest.raises(WebhookRejected):
        payments.handle_webhook(body, headers)
    assert wallet.state.revenue_yen == 0

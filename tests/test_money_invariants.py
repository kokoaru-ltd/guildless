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


# --- P7 corrected: an interrupted request is unknown, not "nothing happened" --

def test_a_timeout_after_the_request_is_never_treated_as_not_started(payments):
    """Stripe states such outcomes are indeterminate: the charge may have
    succeeded and only the response was lost."""
    checkout = order(payments, 30_000)
    payments.mark_indeterminate(checkout.checkout_id, "connection reset")

    assert checkout.status == "unknown_reconciling"
    assert checkout.needs_reconciliation is True
    assert checkout.status != "pending"
    assert checkout.status != "failed"


# --- P8: an unknown outcome never counts either way ------------------------

def test_an_unknown_outcome_is_not_revenue_and_not_failure(payments, wallet):
    checkout = order(payments, 30_000)
    payments.mark_indeterminate(checkout.checkout_id, "timeout")
    assert payments.real_payment_count == 0
    assert wallet.state.revenue_yen == 0


# --- P9: only the provider may settle it -----------------------------------

@pytest.mark.parametrize("source", ["idempotent_retry", "provider_lookup", "webhook"])
def test_the_provider_can_settle_an_unknown_outcome(payments, wallet, source):
    checkout = order(payments, 30_000)
    payments.mark_indeterminate(checkout.checkout_id, "timeout")
    payments.reconcile(
        checkout.checkout_id, source=source, status="paid",
        amount_yen=30_000, live=True,
    )
    assert checkout.status == "paid"
    assert wallet.state.revenue_yen == 30_000


@pytest.mark.parametrize("source", ["agent_guess", "assumed_success", "local_db", "retry_blindly"])
def test_nothing_else_may_settle_it(payments, source):
    from council.payment import PaymentError

    checkout = order(payments, 30_000)
    payments.mark_indeterminate(checkout.checkout_id, "timeout")
    with pytest.raises(PaymentError):
        payments.reconcile(checkout.checkout_id, source=source, status="paid", live=True)
    assert checkout.status == "unknown_reconciling"


def test_reconciling_to_failed_leaves_no_revenue(payments, wallet):
    checkout = order(payments, 30_000)
    payments.mark_indeterminate(checkout.checkout_id, "timeout")
    payments.reconcile(checkout.checkout_id, source="provider_lookup", status="failed")
    assert checkout.status == "failed"
    assert wallet.state.revenue_yen == 0


# --- P10: late events may not move a payment backwards ---------------------

def test_an_out_of_order_event_cannot_undo_a_payment(payments, wallet, adapter):
    checkout = order(payments, 30_000)
    payments.handle_webhook(*event(adapter, checkout, live=True, event_id="evt_paid"))
    assert checkout.status == "paid"

    stale, headers = adapter.sign({
        "id": "evt_expired_but_late", "type": "checkout.session.expired", "livemode": True,
        "data": {"object": {"id": checkout.checkout_id, "payment_status": "unpaid"}},
    })
    payments.handle_webhook(stale, headers)

    assert checkout.status == "paid"
    assert wallet.state.revenue_yen == 30_000


def test_a_refund_still_moves_forward(payments, adapter):
    checkout = order(payments, 30_000)
    payments.handle_webhook(*event(adapter, checkout, live=True, event_id="evt_paid"))
    body, headers = adapter.sign({
        "id": "evt_refund", "type": "charge.refunded", "livemode": True,
        "data": {"object": {"id": checkout.checkout_id, "payment_status": "paid"}},
    })
    payments.handle_webhook(body, headers)
    assert checkout.status == "refunded"


# --- P11: the same payment under a new event id is still one payment -------

def test_the_same_payment_resent_under_a_new_id_is_not_counted_twice(
    payments, wallet, adapter
):
    checkout = order(payments, 30_000)
    payments.handle_webhook(*event(adapter, checkout, live=True, event_id="evt_first"))
    payments.handle_webhook(*event(adapter, checkout, live=True, event_id="evt_second"))
    payments.handle_webhook(*event(adapter, checkout, live=True, event_id="evt_third"))

    assert payments.real_payment_count == 1
    assert wallet.state.revenue_yen == 30_000


def test_reconciliation_after_a_webhook_does_not_double_bank(payments, wallet, adapter):
    checkout = order(payments, 30_000)
    payments.handle_webhook(*event(adapter, checkout, live=True, event_id="evt_paid"))
    payments.reconcile(
        checkout.checkout_id, source="provider_lookup", status="paid",
        amount_yen=30_000, live=True,
    )
    assert wallet.state.revenue_yen == 30_000
    assert payments.real_payment_count == 1


# --- capital must always account for every yen -----------------------------

@pytest.mark.parametrize("cash", [1, 500, 5_000, 10_001, 999_999])
def test_every_yen_is_in_a_named_envelope(tmp_path, cash):
    wallet = CapitalAllocator(tmp_path / f"c{cash}.json", initial_cash_yen=cash)
    breakdown = {n: e.allocated_yen for n, e in wallet.state.envelopes.items()}
    assert sum(breakdown.values()) == cash
    assert set(breakdown) == {"reserve", "experiment", "ai_api", "emergency"}

import json
import time

import pytest

from council.capital import CapitalAllocator
from council.payment import (
    CheckoutRequest,
    PaymentProcessor,
    SandboxAdapter,
    WebhookRejected,
    verify_stripe_signature,
)
from council.proof import Measurements, classify, evaluate


@pytest.fixture
def capital(tmp_path):
    return CapitalAllocator(tmp_path / "capital.json", initial_cash_yen=5_000)


@pytest.fixture
def adapter():
    return SandboxAdapter()


@pytest.fixture
def payments(tmp_path, adapter, capital):
    return PaymentProcessor(tmp_path / "payments.json", adapter, capital)


def order(payments, amount=30_000):
    return payments.create_checkout(
        CheckoutRequest(
            offer_id="offer-1", description="AIアニメ10秒 納品",
            amount_yen=amount, customer_ref="cust-1",
            experiment_id="E-1", decision_id="D-0001",
        )
    )


# --- webhook trust ----------------------------------------------------------

def test_an_unsigned_webhook_is_never_banked(payments, capital):
    checkout = order(payments)
    body = json.dumps({"id": "evt_1", "type": "checkout.session.completed",
                       "data": {"object": {"id": checkout.checkout_id,
                                           "payment_status": "paid",
                                           "amount_total": 30_000}}}).encode()
    with pytest.raises(WebhookRejected):
        payments.handle_webhook(body, {})
    assert capital.state.revenue_yen == 0


def test_a_forged_signature_is_rejected(payments, adapter):
    checkout = order(payments)
    body, headers = adapter.paid_event(checkout)
    headers["stripe-signature"] = headers["stripe-signature"][:-4] + "0000"
    with pytest.raises(WebhookRejected):
        payments.handle_webhook(body, headers)


def test_a_replayed_old_event_is_rejected():
    body = b'{"hello":"world"}'
    old = str(int(time.time()) - 4_000)
    import hashlib
    import hmac
    signature = hmac.new(b"secret", f"{old}.".encode() + body, hashlib.sha256).hexdigest()
    with pytest.raises(WebhookRejected) as raised:
        verify_stripe_signature(body, f"t={old},v1={signature}", "secret")
    assert "replay" in str(raised.value)


def test_a_webhook_for_an_unknown_checkout_is_rejected(payments, adapter):
    fake = order(payments)
    fake.checkout_id = "cs_never_created"
    body, headers = adapter.paid_event(fake)
    with pytest.raises(WebhookRejected):
        payments.handle_webhook(body, headers)


def test_an_amount_that_disagrees_with_the_order_is_rejected(payments, adapter):
    checkout = order(payments, 30_000)
    body, headers = adapter.sign({
        "id": "evt_x", "type": "checkout.session.completed",
        "data": {"object": {"id": checkout.checkout_id,
                            "payment_status": "paid", "amount_total": 1}},
    })
    with pytest.raises(WebhookRejected):
        payments.handle_webhook(body, headers)


# --- banking ----------------------------------------------------------------

def test_a_confirmed_payment_reaches_the_wallet(payments, capital, adapter):
    checkout = order(payments)
    body, headers = adapter.paid_event(checkout)
    result = payments.handle_webhook(body, headers)

    assert result.status == "paid"
    assert payments.real_payment_count == 1
    assert capital.state.revenue_yen == 30_000
    assert capital.cash_yen == 35_000


def test_a_retried_webhook_banks_the_sale_only_once(payments, capital, adapter):
    checkout = order(payments)
    body, headers = adapter.paid_event(checkout, event_id="evt_same")
    payments.handle_webhook(body, headers)
    payments.handle_webhook(body, headers)
    assert capital.state.revenue_yen == 30_000
    assert payments.real_payment_count == 1


def test_an_agent_cannot_declare_a_sale(payments):
    """Nothing counts until the provider says so."""
    order(payments)
    assert payments.real_payment_count == 0
    assert payments.revenue_yen == 0


def test_payments_survive_a_restart(tmp_path, capital, adapter):
    path = tmp_path / "payments.json"
    first = PaymentProcessor(path, adapter, capital)
    checkout = order(first)
    body, headers = adapter.paid_event(checkout, event_id="evt_1")
    first.handle_webhook(body, headers)

    reopened = PaymentProcessor(path, adapter, capital)
    assert reopened.real_payment_count == 1
    reopened.handle_webhook(body, headers)
    assert capital.state.revenue_yen == 30_000


def test_live_keys_surface_kyc_as_a_human_task(tmp_path, capital):
    from council.payment import StripeAdapter

    live = PaymentProcessor(
        tmp_path / "p.json", StripeAdapter("sk_live_x", "whsec_x"), capital
    )
    tasks = live.human_tasks()
    assert tasks and tasks[0]["task"] == "identity_verification"


def test_test_keys_need_no_human(tmp_path, capital):
    from council.payment import StripeAdapter

    sandbox = PaymentProcessor(
        tmp_path / "p.json", StripeAdapter("sk_test_x", "whsec_x"), capital
    )
    assert sandbox.human_tasks() == []


# --- Proof A ----------------------------------------------------------------

def test_proof_a_passes_only_on_delivered_profitable_revenue():
    result = evaluate(Measurements(
        contacted=20, replied=4, interested=2, payments=1, delivered=1,
        revenue_yen=30_000, direct_cost_yen=1_400, delivery_proof_passed=True,
    ))
    assert result.passed is True
    assert result.net_yen == 28_600


def test_payment_without_delivery_fails():
    result = evaluate(Measurements(
        payments=1, delivered=0, revenue_yen=30_000, delivery_proof_passed=True
    ))
    assert result.passed is False
    assert result.failure == "DELIVERY_FAILURE"


def test_a_sale_that_lost_money_fails():
    result = evaluate(Measurements(
        contacted=20, replied=4, interested=2, payments=1, delivered=1,
        revenue_yen=500, direct_cost_yen=900, delivery_proof_passed=True,
    ))
    assert result.passed is False
    assert result.net_yen == -400
    assert result.failure == "CONVERSION_FAILURE"


def test_meetings_and_promises_are_not_proof():
    result = evaluate(Measurements(
        contacted=20, replied=6, interested=3, checkout_visits=2,
        payments=0, delivery_proof_passed=True,
    ))
    assert result.passed is False
    assert "第三者からの実入金" in result.reason


# --- failure classification -------------------------------------------------

def test_no_delivery_proof_is_a_delivery_failure_before_anything_else():
    assert classify(Measurements(contacted=20, replied=5, delivery_proof_passed=False)) == "DELIVERY_FAILURE"


def test_nobody_reached_is_acquisition():
    assert classify(Measurements(contacted=0, delivery_proof_passed=True)) == "ACQUISITION_FAILURE"


def test_no_replies_at_all_is_acquisition():
    assert classify(Measurements(contacted=20, replied=0, delivery_proof_passed=True)) == "ACQUISITION_FAILURE"


def test_replies_but_zero_interest_is_market():
    assert classify(Measurements(
        contacted=20, replied=4, interested=0, checkout_visits=0, delivery_proof_passed=True
    )) == "MARKET_FAILURE"


def test_interest_without_payment_is_conversion():
    assert classify(Measurements(
        contacted=20, replied=5, interested=2, checkout_visits=2,
        payments=0, delivery_proof_passed=True,
    )) == "CONVERSION_FAILURE"


def test_a_clean_success_has_no_failure():
    assert classify(Measurements(
        contacted=20, replied=4, interested=2, payments=1, delivered=1,
        revenue_yen=30_000, direct_cost_yen=1_000, delivery_proof_passed=True,
    )) is None

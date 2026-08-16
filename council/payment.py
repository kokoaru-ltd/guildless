"""Takes money from a third party, and proves it actually arrived.

One provider, deliberately. Comparing payment platforms produces no revenue,
and the pipeline below is the same shape for all of them: offer a checkout,
wait for the provider to say a stranger paid, and only then move the numbers.

Two rules run through this file.

Nothing counts until the provider confirms it. An agent cannot mark a sale as
made, because "they said they'd pay" is the single easiest thing for an
autonomous system to mistake for revenue.

Webhooks are untrusted input. Anyone can POST to the endpoint, so an unsigned
or stale event is discarded rather than banked. Without this the company can be
funded by whoever finds the URL.

Live payouts need identity verification, which is legally a named human. That
surfaces as a human task rather than something an agent works around.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from council.capital import CapitalAllocator
from council.storage import write_json


PaymentStatus = Literal["pending", "paid", "failed", "refunded"]


class PaymentError(Exception):
    pass


class WebhookRejected(PaymentError):
    """The event was not provably from the provider. Never bank these."""


@dataclass
class CheckoutRequest:
    offer_id: str
    description: str
    amount_yen: int
    customer_ref: str
    #: Ties the eventual payment back to the experiment that caused it, so
    #: revenue can be attributed to the decision that predicted it.
    experiment_id: str = ""
    decision_id: str = ""


@dataclass
class Checkout:
    checkout_id: str
    url: str
    amount_yen: int
    offer_id: str
    customer_ref: str
    created_at: str
    experiment_id: str = ""
    decision_id: str = ""
    status: PaymentStatus = "pending"
    provider: str = ""
    paid_at: str | None = None
    #: What the provider kept. Revenue net of this is what the company earned.
    fee_yen: int = 0


@dataclass
class PaymentEvent:
    """A provider webhook, normalised."""

    event_id: str
    checkout_id: str
    status: PaymentStatus
    amount_yen: int
    fee_yen: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentAdapter(Protocol):
    name: str

    def create_checkout(self, request: CheckoutRequest) -> Checkout: ...

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentEvent: ...

    def requires_identity_verification(self) -> bool: ...


def verify_stripe_signature(
    body: bytes, header: str, secret: str, *, tolerance_seconds: int = 300
) -> None:
    """Confirm a webhook really came from Stripe and is recent.

    The timestamp check matters as much as the signature: without it a captured
    payload can be replayed forever, and every replay would look like a new sale.
    """
    if not secret:
        raise WebhookRejected("webhook secret is not configured")
    parts = dict(
        piece.split("=", 1) for piece in header.split(",") if "=" in piece
    )
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        raise WebhookRejected("signature header is malformed")
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError as exc:
        raise WebhookRejected("signature timestamp is not a number") from exc
    if age > tolerance_seconds:
        raise WebhookRejected(f"event is {int(age)}s old; refusing a possible replay")
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise WebhookRejected("signature does not match")


class StripeAdapter:
    """Stripe Checkout. Live behaviour is unverified until keys are present."""

    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str, *, success_url: str = "", cancel_url: str = ""):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.success_url = success_url
        self.cancel_url = cancel_url

    def requires_identity_verification(self) -> bool:
        """Test keys move no money; live payouts need a verified person."""
        return not self.secret_key.startswith("sk_test_")

    def create_checkout(self, request: CheckoutRequest) -> Checkout:
        import httpx

        if not self.secret_key:
            raise PaymentError("STRIPE_SECRET_KEY is not set")
        form = {
            "mode": "payment",
            "success_url": self.success_url or "https://example.invalid/paid",
            "cancel_url": self.cancel_url or "https://example.invalid/cancel",
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "jpy",
            "line_items[0][price_data][unit_amount]": str(request.amount_yen),
            "line_items[0][price_data][product_data][name]": request.description,
            "client_reference_id": request.customer_ref,
            "metadata[offer_id]": request.offer_id,
            "metadata[experiment_id]": request.experiment_id,
            "metadata[decision_id]": request.decision_id,
        }
        response = httpx.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=form,
            auth=(self.secret_key, ""),
            timeout=30,
        )
        if response.status_code >= 300:
            raise PaymentError(f"stripe checkout failed: HTTP {response.status_code} {response.text[:200]}")
        body = response.json()
        return Checkout(
            checkout_id=body["id"],
            url=body["url"],
            amount_yen=request.amount_yen,
            offer_id=request.offer_id,
            customer_ref=request.customer_ref,
            created_at=datetime.now(UTC).isoformat(),
            experiment_id=request.experiment_id,
            decision_id=request.decision_id,
            provider=self.name,
        )

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentEvent:
        signature = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""
        verify_stripe_signature(body, signature, self.webhook_secret)
        event = json.loads(body)
        obj = (event.get("data") or {}).get("object") or {}
        kind = event.get("type", "")
        status: PaymentStatus = "pending"
        if kind == "checkout.session.completed" and obj.get("payment_status") == "paid":
            status = "paid"
        elif kind in ("checkout.session.expired", "payment_intent.payment_failed"):
            status = "failed"
        elif kind == "charge.refunded":
            status = "refunded"
        return PaymentEvent(
            event_id=event.get("id", ""),
            checkout_id=obj.get("id", ""),
            status=status,
            amount_yen=int(obj.get("amount_total") or 0),
            raw=event,
        )


class PaymentProcessor:
    """Owns the whole path from checkout to banked, verified profit."""

    def __init__(self, path: Path, adapter: PaymentAdapter, capital: CapitalAllocator):
        self.path = Path(path)
        self.adapter = adapter
        self.capital = capital
        state = self._load()
        self.checkouts: dict[str, Checkout] = state["checkouts"]
        self.handled_events: set[str] = state["handled_events"]

    def create_checkout(self, request: CheckoutRequest) -> Checkout:
        checkout = self.adapter.create_checkout(request)
        self.checkouts[checkout.checkout_id] = checkout
        self._save()
        return checkout

    def handle_webhook(self, body: bytes, headers: dict[str, str]) -> Checkout | None:
        """Bank a confirmed payment. Raises rather than banking anything doubtful."""
        event = self.adapter.parse_webhook(body, headers)

        # Providers retry webhooks. Without this the same sale is banked twice.
        if event.event_id and event.event_id in self.handled_events:
            return self.checkouts.get(event.checkout_id)

        checkout = self.checkouts.get(event.checkout_id)
        if checkout is None:
            raise WebhookRejected(f"unknown checkout: {event.checkout_id}")

        if event.status == "paid" and checkout.status != "paid":
            if event.amount_yen and event.amount_yen != checkout.amount_yen:
                raise WebhookRejected(
                    f"amount mismatch: expected ¥{checkout.amount_yen}, event says ¥{event.amount_yen}"
                )
            checkout.status = "paid"
            checkout.paid_at = datetime.now(UTC).isoformat()
            checkout.fee_yen = event.fee_yen
            self.capital.record_revenue(checkout.amount_yen - event.fee_yen)
        elif event.status == "refunded" and checkout.status == "paid":
            checkout.status = "refunded"
        elif event.status == "failed":
            checkout.status = "failed"

        if event.event_id:
            self.handled_events.add(event.event_id)
        self._save()
        return checkout

    # -- reading ------------------------------------------------------------

    @property
    def paid_checkouts(self) -> list[Checkout]:
        return [c for c in self.checkouts.values() if c.status == "paid"]

    @property
    def real_payment_count(self) -> int:
        """Third parties who actually paid. This number drives the gates."""
        return len(self.paid_checkouts)

    @property
    def revenue_yen(self) -> int:
        return sum(c.amount_yen - c.fee_yen for c in self.paid_checkouts)

    def human_tasks(self) -> list[dict[str, str]]:
        """Work only a named person may legally do, surfaced rather than skipped."""
        if not self.adapter.requires_identity_verification():
            return []
        return [
            {
                "task": "identity_verification",
                "title": "決済事業者の本人確認を完了してください",
                "detail": (
                    "本番の入金を受け取るには決済事業者の本人確認（KYC）が必要です。"
                    "法令上、本人しか行えないためGuildlessは代行できません。"
                    "完了後、Guildlessが販売を再開します。"
                ),
            }
        ]

    # -- internals ----------------------------------------------------------

    def _save(self) -> None:
        write_json(
            self.path,
            {
                "checkouts": {k: asdict(v) for k, v in self.checkouts.items()},
                "handled_events": sorted(self.handled_events),
            },
        )

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"checkouts": {}, "handled_events": set()}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"checkouts": {}, "handled_events": set()}
        return {
            "checkouts": {k: Checkout(**v) for k, v in raw.get("checkouts", {}).items()},
            "handled_events": set(raw.get("handled_events", [])),
        }


class SandboxAdapter:
    """Exercises the whole pipeline in-process, with no provider and no money.

    This exists to prove the plumbing, never to prove a sale. It signs its own
    events with the same HMAC scheme so the verification path under test is the
    real one rather than a bypass.
    """

    name = "sandbox"

    def __init__(self, webhook_secret: str = "whsec_sandbox"):
        self.webhook_secret = webhook_secret

    def requires_identity_verification(self) -> bool:
        return False

    def create_checkout(self, request: CheckoutRequest) -> Checkout:
        return Checkout(
            checkout_id=f"cs_sandbox_{uuid.uuid4().hex[:16]}",
            url=f"https://sandbox.invalid/checkout/{uuid.uuid4().hex[:8]}",
            amount_yen=request.amount_yen,
            offer_id=request.offer_id,
            customer_ref=request.customer_ref,
            created_at=datetime.now(UTC).isoformat(),
            experiment_id=request.experiment_id,
            decision_id=request.decision_id,
            provider=self.name,
        )

    def sign(self, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self.webhook_secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        return body, {"stripe-signature": f"t={timestamp},v1={signature}"}

    def paid_event(self, checkout: Checkout, *, event_id: str = "") -> tuple[bytes, dict[str, str]]:
        return self.sign(
            {
                "id": event_id or f"evt_{uuid.uuid4().hex[:16]}",
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": checkout.checkout_id,
                        "payment_status": "paid",
                        "amount_total": checkout.amount_yen,
                    }
                },
            }
        )

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> PaymentEvent:
        verify_stripe_signature(
            body, headers.get("stripe-signature", ""), self.webhook_secret
        )
        event = json.loads(body)
        obj = event["data"]["object"]
        status: PaymentStatus = "paid" if obj.get("payment_status") == "paid" else "pending"
        if event.get("type") == "charge.refunded":
            status = "refunded"
        return PaymentEvent(
            event_id=event.get("id", ""),
            checkout_id=obj.get("id", ""),
            status=status,
            amount_yen=int(obj.get("amount_total") or 0),
            raw=event,
        )

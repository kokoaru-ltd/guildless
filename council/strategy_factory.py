"""Turns the goal into concrete strategies the run can execute.

This is the wiring between the pieces that were built separately: offer
generation, delivery proof, channel legality, prospecting and outreach. Each
strategy is one offer sold through one lawful channel, and a strategy that
cannot clear any of those stages simply ends so the run moves to the next.

Nothing here returns a question. A blocked step raises :class:`Blocked` naming
the kind of work involved, and the continuation policy — not this module —
decides whether that is a human's problem. Almost never is.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from council.action_gateway import ActionGateway, ActionRequest
from council.compliance import ChannelChoice, usable_channels
from council.goal_run import Blocked, Strategy
from council.proof import Measurements
from council.revenue_loop import Offer, OfferCriteria, screen_offers


@dataclass
class Prospect:
    name: str
    contact: str
    reason: str


class StrategyFactory:
    """Builds executable strategies from the company's current situation.

    Callables are injected rather than imported so a run can be exercised
    without contacting anyone, and so a failing supplier can be swapped without
    touching the loop.
    """

    def __init__(
        self,
        *,
        generate_offers: Callable[[], list[Offer]],
        prove_delivery: Callable[[Offer], tuple[bool, str]],
        find_prospects: Callable[[Offer, ChannelChoice, int], list[Prospect]],
        gateway: ActionGateway,
        compose_message: Callable[[Offer, Prospect], dict[str, Any]],
        measure: Callable[[Offer], Measurements],
        capabilities: Callable[[], set[str]],
        # The thing that actually reaches a person. Absent by default, so a
        # fully wired company still sends nothing until a sender is supplied
        # deliberately -- the gateway then denies every send as a dry run.
        send: Callable[[ActionRequest], dict[str, Any]] | None = None,
        criteria: OfferCriteria = OfferCriteria(),
        sample_size: int = 20,
    ):
        self.generate_offers = generate_offers
        self.prove_delivery = prove_delivery
        self.find_prospects = find_prospects
        self.gateway = gateway
        self.compose_message = compose_message
        self.measure = measure
        self.capabilities = capabilities
        self.send = send
        self.criteria = criteria
        self.sample_size = sample_size
        self._rejected: list[str] = []

    def __call__(self) -> list[Strategy]:
        """Produce the next batch of strategies. Empty means nothing viable."""
        channels = usable_channels(self.capabilities())
        if not channels:
            # No lawful reachable channel is a dead end for this configuration,
            # not a question. The run will ask for strategies again, and a
            # capability discovered in the meantime changes the answer.
            return []

        offers, rejected = screen_offers(self.generate_offers(), self.criteria)
        self._rejected = [
            f"{r['offer']['name']}: {'; '.join(r['reasons'])}" for r in rejected
        ]
        if not offers:
            return []

        return [
            self._build(offer, channel)
            for offer in offers
            for channel in channels[:1]
        ]

    @property
    def rejected_offers(self) -> list[str]:
        return list(self._rejected)

    def _build(self, offer: Offer, channel: ChannelChoice) -> Strategy:
        state: dict[str, Any] = {"prospects": []}

        def delivery_proof() -> None:
            passed, evidence = self.prove_delivery(offer)
            if not passed:
                # Cannot build it, so it must not be sold. Abandoning the offer
                # is the correct response and needs nobody's approval.
                raise Blocked("build_product", f"納品証明に失敗: {evidence[:120]}")

        def prospecting() -> None:
            prospects = self.find_prospects(offer, channel, self.sample_size)
            if not prospects:
                raise Blocked("find_prospects", f"{channel.channel}で対象が見つかりません")
            state["prospects"] = prospects

        def outreach() -> None:
            sent = 0
            for index, prospect in enumerate(state["prospects"]):
                payload = self.compose_message(offer, prospect)
                result = self.gateway.execute(
                    ActionRequest(
                        kind="send_email" if channel.channel == "email_cold" else "publish_post",
                        idempotency_key=f"{offer.offer_id}:{channel.channel}:{index}",
                        target=prospect.contact,
                        purpose=f"{offer.name}の初回接触",
                        amount_yen=channel.rule.cost_per_contact_yen,
                        payload=payload,
                    ),
                    self.send,
                )
                if result.ok:
                    sent += 1
            if sent == 0:
                raise Blocked(
                    "send_message",
                    "1件も送信できませんでした（送信は既定で無効、または全件が事前チェックで停止）",
                )

        return Strategy(
            name=f"{offer.name} / {channel.channel}",
            steps=[
                ("delivery_proof", delivery_proof),
                ("prospecting", prospecting),
                ("outreach", outreach),
            ],
            measure=lambda: self.measure(offer),
        )

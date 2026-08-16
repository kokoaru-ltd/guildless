"""The one condition that ends Proof A.

Everything else the company can report — replies, meetings, "we'll take it",
a generated landing page, a completed run — is activity. Proof A is not about
activity. It asks whether Guildless can take money from a stranger, hand over
what was promised, and still be up on the deal.

Three parts, all required, none of them substitutable:

    a third party actually paid
    the thing was delivered
    revenue minus direct cost is above zero

The third part is what stops the obvious cheat. Selling a 500 yen item that
costs 900 yen of inference to fulfil is a purchase, a delivery, and a loss.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


#: What went wrong, in the only four ways that change what to do next.
#: Anything more granular is a story; these four each point at a different fix.
FailureKind = Literal[
    "MARKET_FAILURE",       # nobody wants it
    "ACQUISITION_FAILURE",  # cannot reach anyone
    "CONVERSION_FAILURE",   # interest but no money
    "DELIVERY_FAILURE",     # sells but cannot be produced
]

FAILURE_MEANING: dict[str, str] = {
    "MARKET_FAILURE": "誰も欲しがらない。商品仮説を変える。",
    "ACQUISITION_FAILURE": "顧客に届いていない。チャネルか対象を変える。",
    "CONVERSION_FAILURE": "興味はあるが払わない。オファーか価格を変える。",
    "DELIVERY_FAILURE": "売れるが完成品を作れない。売る前に納品証明をやり直す。",
}


@dataclass(frozen=True)
class Measurements:
    """Counted reality. Every field is an observation, never a projection."""

    contacted: int = 0
    replied: int = 0
    interested: int = 0
    checkout_visits: int = 0
    payments: int = 0
    delivered: int = 0
    revenue_yen: int = 0
    direct_cost_yen: int = 0
    delivery_proof_passed: bool = False


@dataclass(frozen=True)
class ProofResult:
    passed: bool
    reason: str
    net_yen: int
    failure: FailureKind | None = None
    failure_meaning: str = ""
    unmet: list[str] = field(default_factory=list)


def evaluate(measurements: Measurements) -> ProofResult:
    """Decide whether Proof A is done, and if not, which of the four failures it is."""
    net = measurements.revenue_yen - measurements.direct_cost_yen

    unmet: list[str] = []
    if measurements.payments <= 0:
        unmet.append("第三者からの実入金")
    if measurements.delivered <= 0:
        unmet.append("納品完了")
    if net <= 0:
        unmet.append("直接原価を引いた黒字")

    if not unmet:
        return ProofResult(
            True,
            f"入金{measurements.payments}件・納品{measurements.delivered}件・純益¥{net:,}",
            net,
        )

    failure = classify(measurements)
    return ProofResult(
        False,
        "未達: " + "、".join(unmet),
        net,
        failure,
        FAILURE_MEANING.get(failure, "") if failure else "",
        unmet,
    )


def classify(measurements: Measurements) -> FailureKind | None:
    """Name the failure by where the funnel actually stopped.

    Order matters. Delivery is checked first because a product that cannot be
    produced makes every downstream number meaningless — and selling it anyway
    is the most expensive mistake available.
    """
    if measurements.payments > 0 and measurements.delivered == 0:
        return "DELIVERY_FAILURE"
    if not measurements.delivery_proof_passed:
        return "DELIVERY_FAILURE"
    if measurements.contacted == 0:
        return "ACQUISITION_FAILURE"
    if measurements.replied == 0:
        # Reached people, got nothing back at all: either the wrong people or
        # the message never landed. Both are acquisition problems, not pricing.
        return "ACQUISITION_FAILURE"
    if measurements.interested == 0 and measurements.checkout_visits == 0:
        return "MARKET_FAILURE"
    if measurements.payments == 0:
        return "CONVERSION_FAILURE"
    if measurements.revenue_yen - measurements.direct_cost_yen <= 0:
        # Sold and delivered but underwater: the offer is priced wrong.
        return "CONVERSION_FAILURE"
    return None

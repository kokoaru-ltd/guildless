"""Routes a decision to the cheapest tier that can safely make it.

The three-model council costs minutes and real tokens. Sending "the customer
replied 'next Wednesday works'" through it would make the company slow and
expensive for no gain. Equally, letting a single cheap model decide a pivot or a
price change would make the company confidently wrong.

So the council is a board meeting, not a staff. It convenes for decisions that
are expensive, irreversible, or change the direction of the business. Everything
else is handled at the cheapest tier that is still correct.

Routing is deterministic and has no model call of its own: the router must never
become the thing it is protecting against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Tier = Literal["machine", "cheap", "strong", "council"]

#: Spending at or above this needs the board, whatever it is being spent on.
COUNCIL_SPEND_THRESHOLD_YEN = 10_000

#: Decision kinds that always convene the council. These either change the
#: direction of the business or cannot be walked back cheaply.
COUNCIL_KINDS = frozenset({
    "price_change",
    "target_change",
    "offer_change",
    "pivot",
    "new_product",
    "market_exit",
    "experiment_design",
    "experiment_verdict",
})

#: Judgement work that needs one capable model but no debate.
STRONG_KINDS = frozenset({
    "sales_copy",
    "prospect_research",
    "proposal_draft",
    "objection_response",
    "negotiation_reply",
    "result_analysis",
})

#: High-volume, low-stakes work. Wrong answers here are cheap to correct.
CHEAP_KINDS = frozenset({
    "reply_classification",
    "intent_extraction",
    "contact_extraction",
    "scheduling_reply",
    "sentiment_check",
    "summarize",
})

#: Pure computation. No model may be called for these at all.
MACHINE_KINDS = frozenset({
    "budget_check",
    "dedupe",
    "field_validation",
    "threshold_check",
    "ledger_math",
    "list_filter",
})

_TIER_ORDER: dict[Tier, int] = {"machine": 0, "cheap": 1, "strong": 2, "council": 3}


@dataclass(frozen=True)
class Routing:
    tier: Tier
    reason: str
    #: Providers to use. Empty for the machine tier.
    providers: tuple[str, ...]
    mode: str | None


def _tier_for_kind(kind: str) -> tuple[Tier, str]:
    if kind in MACHINE_KINDS:
        return "machine", "計算で答えが出るためAIを呼ばない"
    if kind in CHEAP_KINDS:
        return "cheap", "定型処理のため安いモデル1つで足りる"
    if kind in STRONG_KINDS:
        return "strong", "判断を要するが方向を変えないため強いモデル1つで足りる"
    if kind in COUNCIL_KINDS:
        return "council", "事業の方向か価格を変えるため3モデルで審議する"
    # An unknown kind is not automatically important. Treat it as ordinary
    # judgement work; only money and irreversibility escalate it below.
    return "strong", "分類外のため強いモデル1つで扱う"


def route(
    kind: str,
    *,
    amount_yen: int = 0,
    reversible: bool = True,
    external_effect: bool = False,
) -> Routing:
    """Pick the tier for one decision.

    ``amount_yen`` is the money the decision commits, ``reversible`` is whether
    it can be undone without cost, and ``external_effect`` marks decisions that
    reach a third party (sending, charging, contracting).
    """
    tier, reason = _tier_for_kind(kind)

    if amount_yen >= COUNCIL_SPEND_THRESHOLD_YEN:
        tier, reason = "council", f"支出{amount_yen:,}円が上限{COUNCIL_SPEND_THRESHOLD_YEN:,}円以上のため審議する"
    elif not reversible and _TIER_ORDER[tier] < _TIER_ORDER["council"]:
        tier, reason = "council", "取り消せない判断のため審議する"
    elif external_effect and _TIER_ORDER[tier] < _TIER_ORDER["strong"]:
        tier, reason = "strong", "社外に届く内容のため強いモデルで扱う"

    if tier == "council":
        return Routing(tier, reason, ("sakana", "deepseek_api", "gemini", "glm", "codex"), "real")
    if tier == "strong":
        return Routing(tier, reason, ("sakana",), "single")
    if tier == "cheap":
        return Routing(tier, reason, ("glm",), "single")
    return Routing(tier, reason, (), None)

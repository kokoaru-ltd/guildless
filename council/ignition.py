"""The one contract: a spark, some capital, and money from a stranger.

Everything a company does can be made to look like success. A landing page went
live, a hundred approaches went out, someone replied, a meeting happened, a
store was published, a checkout button was clicked. Systems that count any of
those have no way to tell a business from an expensive hobby, and they will
report progress indefinitely while the balance falls.

So there is exactly one success here, it is defined once, and nothing in the
system may redefine it. Everything else is progress — useful, worth measuring,
and not the thing.

The input is deliberately thin. Not a business plan: a spark. "Old photos could
be animated" is enough, and so is "there is a spare GPU". Requiring a plan puts
the hard part back on the person, and the hard part is exactly what this is
for: working out who pays for that, whether it can be delivered, and getting
one of them to actually pay.

This module is protected from self-modification. An agent that can edit its own
definition of success will eventually do so, and every guarantee above rests on
this file meaning what it says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


#: Things that are not success, however good they look in a report. Each one
#: has been the finish line for some system that never earned anything.
PROGRESS_MILESTONES: tuple[str, ...] = (
    "market_researched",
    "offer_designed",
    "delivery_proven",
    "landing_page_live",
    "store_published",
    "listing_created",
    "seo_done",
    "content_posted",
    "prospects_found",
    "outreach_sent",
    "reply_received",
    "meeting_booked",
    "quote_sent",
    "checkout_created",
    "checkout_button_clicked",
    "customer_said_yes",
)

#: The only one that counts, and only with third-party evidence behind it.
SUCCESS_MILESTONE = "payment_confirmed_by_provider"

Outcome = Literal["progress", "business_success", "not_started"]

#: Evidence that money genuinely arrived. A model's word is not on this list,
#: and neither is the company's own database.
ACCEPTED_EVIDENCE: frozenset[str] = frozenset({
    "stripe_webhook_verified",
    "paypal_ipn_verified",
    "bank_transfer_confirmed",
    "marketplace_payout_record",
    "card_processor_settlement",
})


class ContractViolation(RuntimeError):
    """Raised when something tries to call not-revenue a success."""


@dataclass(frozen=True)
class Spark:
    """The smallest possible input. Not a plan, not a spec.

    ``statement`` may be an idle thought. ``available_resources`` matters as
    much, because "there is a spare GPU" is itself a viable starting point.
    """

    statement: str = ""
    available_resources: tuple[str, ...] = ()

    def viable(self) -> bool:
        return bool(self.statement.strip() or self.available_resources)


@dataclass(frozen=True)
class IgnitionContract:
    """Spark plus capital plus constraints, in exchange for verified revenue.

    Frozen, and the success condition is not a parameter. A contract whose
    definition of winning can be negotiated mid-run is not a contract.
    """

    spark: Spark
    capital_yen: int = 0
    deadline_days: int = 7
    max_loss_yen: int = 0
    #: Minimum third-party money for the contract to be discharged. One yen is
    #: the point: the threshold is not about the amount, it is about whether a
    #: stranger paid at all.
    minimum_revenue_yen: int = 1
    #: Delivered and above cost, so a sale that lost money is not a discharge.
    require_delivery: bool = True
    require_positive_net: bool = True

    def describe(self) -> str:
        origin = self.spark.statement or "、".join(self.spark.available_resources)
        return (
            f"火種「{origin}」と資本¥{self.capital_yen:,}から、"
            f"{self.deadline_days}日以内に第三者からの実入金¥{self.minimum_revenue_yen:,}以上を作る"
        )


@dataclass
class RevenueClaim:
    """An assertion that money arrived, with whatever backs it."""

    amount_yen: int
    evidence_kind: str
    evidence_reference: str = ""
    delivered: bool = False
    direct_cost_yen: int = 0
    claimed_by: str = ""
    #: False for sandbox and test-mode transactions. A provider-verified test
    #: payment is a correct pipeline and an empty bank account, and counting it
    #: is the most convincing false success available -- every signature, every
    #: webhook and every ledger entry is genuine, and no money moved.
    live: bool = False
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class Judgement:
    outcome: Outcome
    reason: str
    milestone: str = ""
    net_yen: int = 0


def classify_milestone(milestone: str) -> Outcome:
    """Where a milestone sits. Anything unrecognised is not success."""
    if milestone == SUCCESS_MILESTONE:
        return "business_success"
    if milestone in PROGRESS_MILESTONES:
        return "progress"
    return "not_started"


def judge(contract: IgnitionContract, claim: RevenueClaim | None) -> Judgement:
    """Decide whether the contract is discharged. The only place that can say so.

    Refuses on every path except one: third-party evidence of money that
    arrived, for something delivered, above what it cost.
    """
    if claim is None:
        return Judgement("not_started", "実入金の主張がありません")

    if claim.evidence_kind not in ACCEPTED_EVIDENCE:
        # This is where a self-reported success would have been booked.
        return Judgement(
            "progress",
            f"{claim.evidence_kind or '無根拠'}は外部証拠として認められません。"
            f"認められるのは{sorted(ACCEPTED_EVIDENCE)}のみです。",
        )

    if not claim.live:
        return Judgement(
            "progress",
            f"テストモードの決済（{claim.evidence_reference or claim.evidence_kind}）です。"
            "配線は正しく動いていますが、実際の金は動いていません。",
        )

    if claim.amount_yen < contract.minimum_revenue_yen:
        return Judgement(
            "progress",
            f"入金¥{claim.amount_yen:,}が下限¥{contract.minimum_revenue_yen:,}に達していません",
        )

    if contract.require_delivery and not claim.delivered:
        return Judgement("progress", "入金はありましたが納品が完了していません")

    net = claim.amount_yen - claim.direct_cost_yen
    if contract.require_positive_net and net <= 0:
        return Judgement(
            "progress",
            f"売上¥{claim.amount_yen:,}に対し原価¥{claim.direct_cost_yen:,}で黒字になっていません",
            net_yen=net,
        )

    return Judgement(
        "business_success",
        f"第三者からの実入金¥{claim.amount_yen:,}を{claim.evidence_kind}で確認、納品済み、純益¥{net:,}",
        SUCCESS_MILESTONE,
        net,
    )


def assert_not_success(milestone: str) -> None:
    """Guard for code tempted to treat a step as the finish.

    Called at the points where a system would otherwise mark itself done.
    """
    if classify_milestone(milestone) != "business_success":
        return
    raise ContractViolation(
        f"{milestone}は外部証拠を伴う判定でのみ成功になります。直接の宣言はできません。"
    )

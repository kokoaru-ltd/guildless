"""Separates why a prospect was lost, because the fixes are entirely different.

"Zero eligible from twenty-two" reads as a customer-discovery failure and
invites the obvious response: find more companies. That was wrong here. Eleven
of the twenty-two were lost because their URLs had been guessed from company
names and did not exist, which is not a discovery problem at all — it is a
missing primitive, and finding more companies to guess at would have wasted the
same effort again.

So the funnel separates who to sell to from how to reach them, and the loss
reasons are grouped by which of those two they belong to. A channel that turns
out to be unusable kills the channel, not the market.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal


FailureKind = Literal[
    "DISCOVERY_FAILURE",      # the company was never correctly identified
    "REACHABILITY_FAILURE",   # it exists, but we cannot get to its site
    "CHANNEL_FAILURE",        # we reached it, but no usable route exists
    "FIT_FAILURE",            # reachable, but not a buyer for this offer
    "SAFETY_FAILURE",         # a route exists and using it is not permitted
]

#: What each kind actually means, and therefore what to change.
MEANING: dict[str, str] = {
    "DISCOVERY_FAILURE": "実在企業を正しく特定できていない。発見手段そのものを変える。",
    "REACHABILITY_FAILURE": "企業は実在するが公式サイト・連絡先に到達できない。到達手段を変える。",
    "CHANNEL_FAILURE": "到達したが営業に使える経路がない。チャネルを変える。",
    "FIT_FAILURE": "接触はできるが商品の対象ではない。顧客層か商品を変える。",
    "SAFETY_FAILURE": "経路はあるが利用が許されていない。そのチャネルを外す。",
}

#: Observed exclusion reasons, mapped to what they actually indicate.
REASON_KIND: dict[str, FailureKind] = {
    "guessed_url": "DISCOVERY_FAILURE",
    "Error": "DISCOVERY_FAILURE",
    "unreachable": "REACHABILITY_FAILURE",
    "fetch_failed": "REACHABILITY_FAILURE",
    "unreadable": "REACHABILITY_FAILURE",
    "no_form": "CHANNEL_FAILURE",
    "login_required": "CHANNEL_FAILURE",
    "not_relevant": "FIT_FAILURE",
    "sales_prohibited": "SAFETY_FAILURE",
    "purpose_restricted": "SAFETY_FAILURE",
    "anti_bot": "SAFETY_FAILURE",
    "recaptcha": "SAFETY_FAILURE",
    "generic_captcha": "SAFETY_FAILURE",
    "opt_out": "SAFETY_FAILURE",
}


#: Where a prospect's URL is allowed to come from. Every one of these is a link
#: that was actually observed somewhere.
EVIDENCE_SOURCES: frozenset[str] = frozenset({
    "search_result",
    "product_listing",
    "official_directory",
    "app_store_listing",
    "verified_company_profile",
    "linked_public_source",
})


class ProspectError(ValueError):
    pass


@dataclass(frozen=True)
class Prospect:
    company: str
    url: str
    #: Where the URL was seen. Constructing one from a company name is the
    #: defect that lost eleven of the first twenty-two.
    source: str
    source_reference: str = ""

    def __post_init__(self) -> None:
        if self.source not in EVIDENCE_SOURCES:
            raise ProspectError(
                f"{self.source}はURLの出所として認められません。"
                f"観測されたリンクのみ許可されます: {sorted(EVIDENCE_SOURCES)}"
            )


def classify(reason: str) -> FailureKind:
    """Name what a rejection actually indicates. Unknown reasons never pass as
    discovery problems, because that is the one that invites more of the same."""
    for token, kind in REASON_KIND.items():
        if token and token in reason:
            return kind
    return "CHANNEL_FAILURE"


@dataclass
class Funnel:
    """Who could be sold to, and separately, who can be reached.

    Kept apart on purpose. Collapsing them produces "no customers" when the
    truth is "no route to these customers", and those need opposite responses.
    """

    discovered: int = 0
    qualified: int = 0
    reachable: int = 0
    legally_contactable: int = 0
    send_ready: int = 0
    sent: int = 0
    paid: int = 0
    losses: Counter = field(default_factory=Counter)

    def lose(self, reason: str) -> FailureKind:
        kind = classify(reason)
        self.losses[kind] += 1
        return kind

    @property
    def dominant_failure(self) -> FailureKind | None:
        """The one worth fixing. Anything else is a distraction until it moves."""
        return self.losses.most_common(1)[0][0] if self.losses else None

    def next_move(self) -> str:
        kind = self.dominant_failure
        if kind is None:
            return "まだ失敗が記録されていません"
        return MEANING[kind]

    def as_dict(self) -> dict[str, object]:
        return {
            "discovered": self.discovered,
            "qualified": self.qualified,
            "reachable": self.reachable,
            "legally_contactable": self.legally_contactable,
            "send_ready": self.send_ready,
            "sent": self.sent,
            "paid": self.paid,
            "losses": dict(self.losses),
            "dominant_failure": self.dominant_failure,
            "next_move": self.next_move(),
        }


def from_inspection(rows: list[dict]) -> Funnel:
    """Rebuild the funnel from recorded prospect inspections."""
    funnel = Funnel(discovered=len(rows))
    for row in rows:
        status = row.get("status")
        if status == "eligible":
            funnel.qualified += 1
            funnel.reachable += 1
            funnel.legally_contactable += 1
            continue
        kind = funnel.lose(str(row.get("reason") or status or ""))
        if kind not in ("DISCOVERY_FAILURE", "REACHABILITY_FAILURE"):
            funnel.reachable += 1
        if kind == "FIT_FAILURE":
            funnel.reachable += 0  # reached, simply not a buyer
    return funnel

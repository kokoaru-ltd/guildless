"""What the company is betting on, and which bets have earned more money.

A bet is one hypothesis about where cash comes from: an offer, aimed at a kind
of customer, reached through a channel. It replaces the task as the unit of
management. Tasks measure effort, and a company that manages effort optimises
effort; a bet measures money, and the only question it can answer is whether
this way of making money works.

Status is derived, never chosen. Someone who can type "SCALE" onto a losing
idea has a label, not a measurement, and the whole point of running the company
from counted facts is that the label cannot drift from what happened:

* **PAYING** -- a third party's money has actually arrived. Nothing else earns
  this, and nothing takes it away.
* **SCALE** -- someone agreed to pay but the money has not landed. Worth more
  effort, not yet worth believing.
* **TEST** -- it has reached real people and some answered. The hypothesis is
  alive.
* **WATCH** -- built, aimed at nobody yet. Costs nothing and proves nothing.
* **KILLED** -- enough contact to be a fair trial, and no reply. Killing it is
  what frees the capital for the next one.

The order matters more than the names. A bet cannot be promoted by activity --
sending a thousand more emails moves nothing -- only by a reply, an agreement,
or money. That is deliberate: effort is the thing a struggling company produces
most of.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["PAYING", "SCALE", "TEST", "WATCH", "KILLED"]

#: Contacts a bet must make before silence means anything. Below this, no reply
#: is a sample size, not a verdict -- killing an idea after four emails throws
#: away ideas that were merely unlucky.
FAIR_TRIAL_CONTACTS = 30

#: Order for display, worst last. Also the order in which a reader should care.
STATUS_ORDER: tuple[Status, ...] = ("PAYING", "SCALE", "TEST", "WATCH", "KILLED")


@dataclass
class Bet:
    """One way the company might make money, and what it has actually done."""

    id: str
    name: str
    #: What is being sold, in the words a customer would recognise.
    offer: str = ""
    #: Who it is aimed at.
    audience: str = ""
    #: How they are reached.
    channel: str = ""
    price_yen: int = 0

    # -- measured, never asserted --
    contacted: int = 0
    replied: int = 0
    meetings: int = 0
    quoted: int = 0
    #: Yen actually received and verified by a payment provider.
    cash_yen: int = 0
    #: Yen spent pursuing this bet.
    spent_yen: int = 0
    #: Yen in quotes sent and not yet answered. A hope, labelled as one.
    pipeline_yen: int = 0
    #: Days from starting the bet to its first verified cash. None until then.
    days_to_first_cash: int | None = None
    #: Why it was killed, when it was.
    killed_because: str = ""

    @property
    def status(self) -> Status:
        if self.cash_yen > 0:
            return "PAYING"
        if self.killed_because:
            return "KILLED"
        if self.quoted > 0:
            return "SCALE"
        if self.replied > 0:
            return "TEST"
        if self.contacted >= FAIR_TRIAL_CONTACTS:
            # A fair trial that produced nothing. Saying so is the useful part.
            return "KILLED"
        return "WATCH"

    @property
    def dead(self) -> bool:
        return self.status == "KILLED"

    @property
    def net_yen(self) -> int:
        """Money made minus money spent. The only figure that settles anything."""
        return self.cash_yen - self.spent_yen

    @property
    def reply_rate(self) -> float:
        return self.replied / self.contacted if self.contacted else 0.0

    def why(self) -> str:
        """One sentence a person can act on, from what was counted."""
        if self.cash_yen:
            return f"{self.cash_yen:,}円が実際に入金されました"
        if self.killed_because:
            return self.killed_because
        if self.quoted:
            return f"{self.quoted}件が見積もり待ちです"
        if self.replied:
            return f"{self.contacted}件中{self.replied}件が返信（{self.reply_rate:.0%}）"
        if self.contacted >= FAIR_TRIAL_CONTACTS:
            return f"{self.contacted}件接触して返信0件。十分試したので止めます"
        if self.contacted:
            return f"{self.contacted}件接触、返信待ち（判断には{FAIR_TRIAL_CONTACTS}件必要）"
        return "まだ誰にも接触していません"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "offer": self.offer,
            "audience": self.audience, "channel": self.channel,
            "price_yen": self.price_yen, "status": self.status, "why": self.why(),
            "contacted": self.contacted, "replied": self.replied,
            "meetings": self.meetings, "quoted": self.quoted,
            "cash_yen": self.cash_yen, "spent_yen": self.spent_yen,
            "net_yen": self.net_yen, "pipeline_yen": self.pipeline_yen,
            "reply_rate": round(self.reply_rate, 4),
            "days_to_first_cash": self.days_to_first_cash,
            "killed_because": self.killed_because,
        }


@dataclass
class Portfolio:
    """Every bet the company has running, and what they add up to."""

    bets: list[Bet] = field(default_factory=list)

    @property
    def live(self) -> list[Bet]:
        return [bet for bet in self.bets if not bet.dead]

    @property
    def cash_yen(self) -> int:
        return sum(bet.cash_yen for bet in self.bets)

    @property
    def spent_yen(self) -> int:
        return sum(bet.spent_yen for bet in self.bets)

    @property
    def pipeline_yen(self) -> int:
        """Quoted and unanswered, across live bets only.

        Dead bets are excluded deliberately. A quote nobody answered on an idea
        that has been abandoned is not expected revenue, and counting it makes
        a failing company look like a busy one.
        """
        return sum(bet.pipeline_yen for bet in self.live)

    @property
    def funnel(self) -> dict[str, int]:
        """The pipeline as counted people, not as money."""
        return {
            "contacted": sum(b.contacted for b in self.bets),
            "replied": sum(b.replied for b in self.bets),
            "meetings": sum(b.meetings for b in self.bets),
            "quoted": sum(b.quoted for b in self.bets),
            "paid": sum(1 for b in self.bets if b.cash_yen > 0),
        }

    def ranked(self) -> list[Bet]:
        """Best first: by status, then by money, then by reply rate."""
        return sorted(
            self.bets,
            key=lambda b: (STATUS_ORDER.index(b.status), -b.net_yen, -b.reply_rate),
        )

    def focus(self) -> Bet | None:
        """The bet today's effort should go to, or None when there is nothing.

        Evidence over hope: a bet with replies beats one without, whatever
        anybody believes about the idea.
        """
        candidates = [bet for bet in self.live if bet.status != "WATCH"]
        if not candidates:
            candidates = self.live
        if not candidates:
            return None
        return max(candidates, key=lambda b: (b.cash_yen, b.quoted, b.replied))

    def decision(self) -> str:
        """What Guildless has decided to do, and the measurement behind it."""
        chosen = self.focus()
        if chosen is None:
            return "まだ賭けがありません"
        return f"{chosen.name}を継続。{chosen.why()}"

    def as_dict(self) -> dict[str, Any]:
        chosen = self.focus()
        return {
            "bets": [bet.as_dict() for bet in self.ranked()],
            "cash_yen": self.cash_yen,
            "spent_yen": self.spent_yen,
            "pipeline_yen": self.pipeline_yen,
            "funnel": self.funnel,
            "focus_id": chosen.id if chosen else "",
            "decision": self.decision(),
        }

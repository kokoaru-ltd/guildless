"""The part that actually works: the loop that runs the company.

What sat here before did four things — observe, diagnose, classify, check
readiness — and every one of them read a file and described it. The company
could run for a week and the only thing that changed was the timestamp. The
screen was honest about a system that was doing nothing.

This does the work. Each pass moves the business one step along the only path
that ends in money: find someone who might pay, write to them, read what came
back, ask the interested ones for money, and record what actually arrived.
Every step reports in the owner's words, and every step is allowed to fail
without ending the company.

Two properties are load-bearing.

**It never invents progress.** A pass that discovers nobody says so; the
company does not get a sentence about "analysing the market" to fill the
silence. This is why the previous version was worse than useless: it always had
something to say.

**Simulated money never becomes cash.** Receipts carry their own provenance,
and this counts them into separate totals. A simulated sale advances the
funnel, proves the loop, and moves no cash figure — which is the whole reason
it is safe to develop against one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from council.decision_boundary import Action, Budget, rule
from council.world import Prospect, Receipt, World

#: How many companies one pass looks at. Small on purpose: a pass that takes a
#: minute makes the screen feel dead, and the loop runs continuously anyway.
BATCH = 12

#: How many messages one pass sends. Well under the decision boundary's
#: per-action limit, so ordinary outreach never stops to ask permission.
SEND_PER_PASS = 5


@dataclass
class Ledger:
    """What the company has actually done. The screen reads this and nothing else."""

    inspected: int = 0
    eligible: list[Prospect] = field(default_factory=list)
    excluded: dict[str, int] = field(default_factory=dict)
    contacted: list[str] = field(default_factory=list)
    replied: list[str] = field(default_factory=list)
    interested: list[str] = field(default_factory=list)
    quoted: list[str] = field(default_factory=list)

    #: Money that a payment provider verified. The only figure that is revenue.
    cash_yen: int = 0
    #: Money a simulation produced. Never added to cash, shown as its own thing.
    simulated_cash_yen: int = 0
    simulated_sales: int = 0
    spent_yen: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "prospects_inspected": self.inspected,
            "prospects_eligible": len(self.eligible),
            "prospect_exclusions": dict(self.excluded),
            "contacts_made": len(self.contacted),
            "replies_received": len(self.replied),
            "meetings_booked": len(self.interested),
            "quotes_sent": len(self.quoted),
            "cash_yen": self.cash_yen,
            "simulated_cash_yen": self.simulated_cash_yen,
            "simulated_sales": self.simulated_sales,
            "spent_yen": self.spent_yen,
        }


@dataclass
class Operator:
    """Runs the business against whatever world it was given."""

    world: World
    offer: str
    price_yen: int
    ledger: Ledger = field(default_factory=Ledger)
    #: Capital the owner committed. The decision boundary reads it to work out
    #: which actions are already authorised.
    capital_yen: int = 0
    #: Composes the message. Replaced by a real writer later; the loop does not
    #: care which, because it only needs a string.
    write: Callable[[Prospect, str], str] | None = None

    @property
    def budget(self) -> Budget:
        return Budget(
            remaining_yen=max(0, self.capital_yen - self.ledger.spent_yen),
            recipients_used=len(self.ledger.contacted),
        )

    # -- the steps, in the order money happens ------------------------------

    def discover(self) -> str:
        if not self.offer:
            return ""
        found = self.world.find_prospects(self.offer, BATCH)
        if not found:
            return ""
        self.ledger.inspected += len(found)
        fresh = 0
        for prospect in found:
            if prospect.excluded_because:
                self.ledger.excluded[prospect.excluded_because] = (
                    self.ledger.excluded.get(prospect.excluded_because, 0) + 1
                )
                continue
            self.ledger.eligible.append(prospect)
            fresh += 1
        if fresh:
            return f"{len(found)}社を調べ、{fresh}社が条件に合いました"
        # Naming the commonest reason is what turns a dead pass into a lead on
        # what to change. "0 found" on its own is not actionable.
        if self.ledger.excluded:
            worst = max(self.ledger.excluded.items(), key=lambda item: item[1])
            return f"{len(found)}社を調べ、条件に合う相手はなし（最多の理由：{worst[0]}）"
        return f"{len(found)}社を調べましたが、条件に合う相手はいませんでした"

    def reach_out(self) -> str:
        waiting = [p for p in self.ledger.eligible if p.name not in self.ledger.contacted]
        if not waiting:
            return ""
        batch = waiting[:SEND_PER_PASS]

        # Asked once for the batch, not once per message. Outreach at this size
        # is authorised; the boundary is here so that a batch which grows into
        # a campaign stops on its own rather than because someone noticed.
        ruling = rule(
            Action("send_email", f"{len(batch)}社へ提案を送信", recipients=len(batch)),
            self.budget,
        )
        if ruling.needs_human:
            return f"承認待ち：{ruling.prompt}"

        sent = 0
        for prospect in batch:
            message = self.write(prospect, self.offer) if self.write else _default_message(
                prospect, self.offer, self.price_yen
            )
            if self.world.send_message(prospect, message):
                self.ledger.contacted.append(prospect.name)
                sent += 1
        return f"{sent}社へ提案を送りました" if sent else ""

    def read_replies(self) -> str:
        replies = self.world.collect_replies()
        if not replies:
            return ""
        keen = 0
        for reply in replies:
            self.ledger.replied.append(reply.prospect)
            if reply.interested:
                self.ledger.interested.append(reply.prospect)
                keen += 1
        if keen:
            return f"{len(replies)}件の返信、うち{keen}件が前向きです"
        return f"{len(replies)}件の返信、いずれも見送りでした"

    def ask_for_money(self) -> str:
        waiting = [name for name in self.ledger.interested if name not in self.ledger.quoted]
        if not waiting:
            return ""
        for name in waiting:
            self.world.offer_to_pay(name, self.price_yen)
            self.ledger.quoted.append(name)
        return f"{len(waiting)}社に支払い方法を送りました（1件 ¥{self.price_yen:,}）"

    def bank(self) -> str:
        receipts = self.world.collect_receipts()
        if not receipts:
            return ""
        return _record(self.ledger, receipts)

    def steps(self) -> list[tuple[str, Callable[[], str]]]:
        """The pass, in order. Named for what they do to the business."""
        return [
            ("discovery", self.discover),
            ("outreach", self.reach_out),
            ("replies", self.read_replies),
            ("quote", self.ask_for_money),
            ("payment", self.bank),
        ]


def _record(ledger: Ledger, receipts: list[Receipt]) -> str:
    """Bank what arrived, keeping made-up money out of the real total."""
    real = [r for r in receipts if not r.simulated]
    fake = [r for r in receipts if r.simulated]

    for receipt in real:
        ledger.cash_yen += receipt.amount_yen
    for receipt in fake:
        ledger.simulated_cash_yen += receipt.amount_yen
        ledger.simulated_sales += 1

    parts = []
    if real:
        parts.append(f"入金 {len(real)}件（¥{sum(r.amount_yen for r in real):,}）を確認しました")
    if fake:
        # Labelled at the point it is written, so no reader downstream has to
        # know which world produced it.
        parts.append(
            f"模擬売上 {len(fake)}件（¥{sum(r.amount_yen for r in fake):,}）"
            "。実収益には数えません"
        )
    return "。".join(parts)


def _default_message(prospect: Prospect, offer: str, price_yen: int) -> str:
    return (
        f"{prospect.name} 様\n\n"
        f"{offer}のご提案です。¥{price_yen:,}でお引き受けします。\n"
        "ご不要でしたら破棄してください。"
    )

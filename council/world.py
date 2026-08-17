"""The outside world, behind one interface — and a simulated one to develop against.

The company's working loop must not know whether it is talking to the real
world or a simulation. That is the entire point of putting this boundary here:
a mock with its own control flow proves nothing, because the thing you shipped
was never the thing you tested. Here the loop is identical in both, and
swapping worlds swaps only where the answers come from.

The safety property matters more than the abstraction. A simulated sale is not
revenue, and the way this file guarantees it is not by remembering to check --
it is that simulated money is a different type. ``Receipt.simulated`` is set by
the world that produced it and cannot be cleared, and
:mod:`council.ignition` already refuses any payment lacking verified provider
evidence. A simulation cannot manufacture that evidence, so simulated cash
cannot reach the cash figure even if every other guard failed.

The simulation is deliberately pessimistic. Most contacts never reply, most
replies never buy, and discovery mostly returns companies that fail the
eligibility rules -- because a simulation tuned to feel good produces a loop
tuned for a world that does not exist, and the first contact with reality then
reads as a catastrophic regression.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True)
class Prospect:
    """Someone who might pay. Discovered, never invented."""

    name: str
    url: str
    #: Where this came from. The funnel rejects anything without a real source.
    source: str
    reachable: bool = True
    excluded_because: str = ""


@dataclass(frozen=True)
class Reply:
    prospect: str
    interested: bool
    text: str = ""


@dataclass(frozen=True)
class Receipt:
    """Money that arrived.

    ``simulated`` travels with the receipt rather than being decided later.
    Anything reading a receipt can tell what it is holding without consulting
    configuration that may have changed since.
    """

    prospect: str
    amount_yen: int
    #: What proves it. Real receipts name a provider record; simulated ones say so.
    evidence: str
    simulated: bool


class World(Protocol):
    """Everything the company can do that touches something outside itself."""

    name: str
    #: Seconds between passes. The world sets it because the world is what a
    #: fast loop would be rude to: advancing a simulation is free, while
    #: hammering a real site every second is abuse regardless of what the
    #: business would like.
    tick_seconds: float

    def find_prospects(self, offer: str, limit: int) -> list[Prospect]: ...
    def send_message(self, prospect: Prospect, message: str) -> bool: ...
    def collect_replies(self) -> list[Reply]: ...
    def offer_to_pay(self, prospect: str, amount_yen: int) -> str: ...
    def collect_receipts(self) -> list[Receipt]: ...


def _roll(*parts: object) -> float:
    """A stable pseudo-random number in [0, 1) derived from its inputs.

    Deterministic on purpose. A simulation seeded by the clock produces a
    different company on every restart, and then nobody can tell a real change
    in the loop from yesterday's dice. Same inputs, same world, every run.
    """
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


@dataclass
class SimulatedWorld:
    """A world that behaves like a hard one, so the loop is built for a hard one."""

    name: str = "simulated"
    tick_seconds: float = 2.0
    #: Share of discovered companies that survive the eligibility rules.
    eligible_rate: float = 0.18
    #: Share of contacted companies that answer at all.
    reply_rate: float = 0.07
    #: Share of repliers who are actually interested.
    interest_rate: float = 0.35
    #: Share of interested prospects who go on to pay.
    conversion_rate: float = 0.30

    _contacted: list[str] = field(default_factory=list)
    _replied: set[str] = field(default_factory=set)
    _interested: set[str] = field(default_factory=set)
    _offered: dict[str, int] = field(default_factory=dict)
    _paid: set[str] = field(default_factory=set)
    _tick: int = 0

    def find_prospects(self, offer: str, limit: int) -> list[Prospect]:
        """Return companies, most of which will not qualify.

        Every one carries a source, because a prospect without an observed
        origin is a guessed URL, and guessing URLs is the failure this system
        already has a rule against.
        """
        self._tick += 1
        found: list[Prospect] = []
        for index in range(limit):
            seed = _roll(offer, self._tick, index)
            name = f"サンプル商事 {self._tick:02d}-{index:02d}"
            url = f"https://example.invalid/{self._tick:02d}{index:02d}"
            if seed > self.eligible_rate:
                found.append(Prospect(
                    name=name, url=url, source="search_result", reachable=False,
                    excluded_because=_exclusion(seed),
                ))
            else:
                found.append(Prospect(name=name, url=url, source="search_result"))
        return found

    def send_message(self, prospect: Prospect, message: str) -> bool:
        if not prospect.reachable or prospect.name in self._contacted:
            return False
        self._contacted.append(prospect.name)
        return True

    def collect_replies(self) -> list[Reply]:
        """Replies arrive on their own schedule, not immediately after sending."""
        arrived: list[Reply] = []
        for name in self._contacted:
            if name in self._replied:
                continue
            if _roll("reply", name) > self.reply_rate:
                continue
            self._replied.add(name)
            interested = _roll("interest", name) < self.interest_rate
            if interested:
                self._interested.add(name)
            arrived.append(Reply(
                prospect=name,
                interested=interested,
                text="詳細を聞きたい" if interested else "今回は見送ります",
            ))
        return arrived

    def offer_to_pay(self, prospect: str, amount_yen: int) -> str:
        self._offered[prospect] = amount_yen
        return f"https://example.invalid/checkout/{len(self._offered):04d}"

    def collect_receipts(self) -> list[Receipt]:
        arrived: list[Receipt] = []
        for name, amount in self._offered.items():
            if name in self._paid or name not in self._interested:
                continue
            if _roll("pay", name) > self.conversion_rate:
                continue
            self._paid.add(name)
            arrived.append(Receipt(
                prospect=name, amount_yen=amount,
                evidence="simulated_world",
                # Set here, by the world that made it up. Nothing downstream
                # gets to decide this.
                simulated=True,
            ))
        return arrived


def _exclusion(seed: float) -> str:
    """Why a company did not qualify, in the funnel's own vocabulary."""
    reasons = (
        "利用規約で営業連絡を禁止",
        "問い合わせ窓口がない",
        "CAPTCHAで到達不能",
        "対象業種ではない",
        "個人事業主で予算がない",
    )
    return reasons[int(seed * 1000) % len(reasons)]


def stamp() -> str:
    return datetime.now(UTC).isoformat()

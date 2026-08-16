"""Holds the money. Deliberately not an agent.

A council that concludes "we should spend 3,000 yen on ads" must not thereby be
able to spend 3,000 yen on ads. Reasoning is persuasive and occasionally wrong;
a wallet is neither. So the wallet is plain code with no model anywhere near it,
and every spend has to get past it.

Money is split into envelopes. The reserve envelope is the floor the company is
not allowed to eat, which is what stops a confident agent from spending the last
of the capital on one more idea.

Spending is two-phase on purpose. An action can fail after its budget check —
the send times out, the provider dies — and money that stayed committed to a
send that never happened would silently starve the company. So callers reserve,
act, then either commit what was actually spent or release it.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from council.storage import write_json


EnvelopeName = Literal["reserve", "experiment", "ai_api", "emergency"]

#: Money kept back from operations. Nothing may spend from it.
UNSPENDABLE: frozenset[str] = frozenset({"reserve"})

DEFAULT_SPLIT: dict[str, float] = {
    "reserve": 0.70,
    "experiment": 0.20,
    "ai_api": 0.10,
    "emergency": 0.00,
}


class CapitalError(Exception):
    """Raised when a caller misuses the allocator, not when it denies a spend."""


@dataclass
class Envelope:
    name: str
    allocated_yen: int
    spent_yen: int = 0
    #: Money promised to in-flight actions. Not yet spent, not available.
    reserved_yen: int = 0

    @property
    def available_yen(self) -> int:
        return max(0, self.allocated_yen - self.spent_yen - self.reserved_yen)


@dataclass
class Reservation:
    reservation_id: str
    envelope: str
    amount_yen: int
    purpose: str
    created_at: str
    state: Literal["held", "committed", "released"] = "held"
    committed_yen: int = 0


@dataclass
class Decision:
    """The allocator's answer. ``approved`` is the only thing callers may act on."""

    approved: bool
    reason: str
    reservation: Reservation | None = None


@dataclass
class CapitalState:
    initial_cash_yen: int
    envelopes: dict[str, Envelope] = field(default_factory=dict)
    reservations: dict[str, Reservation] = field(default_factory=dict)
    #: Third-party money actually received. Never an estimate.
    revenue_yen: int = 0


class CapitalAllocator:
    """The company's wallet, enforced in code."""

    def __init__(self, path: Path, *, initial_cash_yen: int | None = None):
        self.path = Path(path)
        if self.path.exists():
            self.state = self._load()
            if initial_cash_yen is not None and initial_cash_yen != self.state.initial_cash_yen:
                raise CapitalError(
                    "capital already initialised; refusing to silently re-fund the company"
                )
        else:
            if initial_cash_yen is None:
                raise CapitalError("initial_cash_yen is required for a new wallet")
            if initial_cash_yen <= 0:
                raise CapitalError("initial_cash_yen must be positive")
            self.state = CapitalState(
                initial_cash_yen=initial_cash_yen,
                envelopes=self._split(initial_cash_yen),
            )
            self._save()

    # -- money in -----------------------------------------------------------

    def record_revenue(self, amount_yen: int, *, envelope: str | None = None) -> None:
        """Bank confirmed third-party money and put it to work.

        Only call this for money that actually arrived. Anything else would
        raise the spending ceiling on the strength of a promise.

        By default earnings are split the same way the opening capital was, so
        the first sale widens what the company can attempt while most of it is
        kept back. A company that spends its first revenue entirely on the next
        experiment has no floor to fail onto. Naming an envelope overrides this
        and puts the whole amount in one place.
        """
        if amount_yen <= 0:
            raise CapitalError("revenue must be positive")
        self.state.revenue_yen += amount_yen
        if envelope is not None:
            self._envelope(envelope).allocated_yen += amount_yen
        else:
            for name, share in self._split(amount_yen).items():
                self._envelope(name).allocated_yen += share.allocated_yen
        self._save()

    # -- money out ----------------------------------------------------------

    def request(self, envelope: str, amount_yen: int, purpose: str) -> Decision:
        """Ask to spend. Returns a denial rather than raising, because being
        told "no" is a normal business outcome, not a program error."""
        if amount_yen < 0:
            raise CapitalError("amount must not be negative")
        if envelope in UNSPENDABLE:
            return Decision(False, f"{envelope}は使用できない留保金です")
        try:
            target = self._envelope(envelope)
        except CapitalError:
            return Decision(False, f"予算枠{envelope}は存在しません")
        if amount_yen > target.available_yen:
            return Decision(
                False,
                f"{envelope}の残りは¥{target.available_yen:,}で、要求¥{amount_yen:,}に足りません",
            )
        reservation = Reservation(
            reservation_id=uuid.uuid4().hex,
            envelope=envelope,
            amount_yen=amount_yen,
            purpose=purpose,
            created_at=datetime.now(UTC).isoformat(),
        )
        target.reserved_yen += amount_yen
        self.state.reservations[reservation.reservation_id] = reservation
        self._save()
        return Decision(True, f"{envelope}から¥{amount_yen:,}を確保しました", reservation)

    def commit(self, reservation_id: str, actual_yen: int | None = None) -> None:
        """Convert a held reservation into real spend once the action happened."""
        reservation = self._reservation(reservation_id, expect="held")
        spent = reservation.amount_yen if actual_yen is None else actual_yen
        if spent < 0:
            raise CapitalError("actual spend must not be negative")
        if spent > reservation.amount_yen:
            raise CapitalError(
                f"actual spend ¥{spent} exceeds the reserved ¥{reservation.amount_yen}"
            )
        envelope = self._envelope(reservation.envelope)
        envelope.reserved_yen -= reservation.amount_yen
        envelope.spent_yen += spent
        reservation.state = "committed"
        reservation.committed_yen = spent
        self._save()

    def release(self, reservation_id: str) -> None:
        """Hand money back when the action did not happen."""
        reservation = self._reservation(reservation_id, expect="held")
        self._envelope(reservation.envelope).reserved_yen -= reservation.amount_yen
        reservation.state = "released"
        self._save()

    # -- reading ------------------------------------------------------------

    @property
    def spent_yen(self) -> int:
        return sum(envelope.spent_yen for envelope in self.state.envelopes.values())

    @property
    def cash_yen(self) -> int:
        """Money still on hand: what was put in, plus earnings, minus spend."""
        return self.state.initial_cash_yen + self.state.revenue_yen - self.spent_yen

    @property
    def net_yen(self) -> int:
        """The only number that says whether any of this worked."""
        return self.state.revenue_yen - self.spent_yen

    def summary(self) -> dict[str, Any]:
        return {
            "initial_cash_yen": self.state.initial_cash_yen,
            "cash_yen": self.cash_yen,
            "revenue_yen": self.state.revenue_yen,
            "spent_yen": self.spent_yen,
            "net_yen": self.net_yen,
            "envelopes": {
                name: {
                    "allocated_yen": envelope.allocated_yen,
                    "spent_yen": envelope.spent_yen,
                    "reserved_yen": envelope.reserved_yen,
                    "available_yen": envelope.available_yen,
                }
                for name, envelope in self.state.envelopes.items()
            },
        }

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _split(cash_yen: int) -> dict[str, Envelope]:
        envelopes: dict[str, Envelope] = {}
        assigned = 0
        names = list(DEFAULT_SPLIT)
        for name in names[:-1]:
            amount = int(cash_yen * DEFAULT_SPLIT[name])
            envelopes[name] = Envelope(name, amount)
            assigned += amount
        # The last envelope absorbs the rounding so no yen goes missing.
        envelopes[names[-1]] = Envelope(names[-1], cash_yen - assigned)
        return envelopes

    def _envelope(self, name: str) -> Envelope:
        if name not in self.state.envelopes:
            raise CapitalError(f"unknown envelope: {name}")
        return self.state.envelopes[name]

    def _reservation(self, reservation_id: str, *, expect: str) -> Reservation:
        reservation = self.state.reservations.get(reservation_id)
        if reservation is None:
            raise CapitalError(f"unknown reservation: {reservation_id}")
        if reservation.state != expect:
            raise CapitalError(
                f"reservation {reservation_id} is {reservation.state}, expected {expect}"
            )
        return reservation

    def _save(self) -> None:
        write_json(
            self.path,
            {
                "initial_cash_yen": self.state.initial_cash_yen,
                "revenue_yen": self.state.revenue_yen,
                "envelopes": {n: asdict(e) for n, e in self.state.envelopes.items()},
                "reservations": {r: asdict(v) for r, v in self.state.reservations.items()},
            },
        )

    def _load(self) -> CapitalState:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return CapitalState(
            initial_cash_yen=int(raw["initial_cash_yen"]),
            revenue_yen=int(raw.get("revenue_yen", 0)),
            envelopes={n: Envelope(**e) for n, e in raw.get("envelopes", {}).items()},
            reservations={r: Reservation(**v) for r, v in raw.get("reservations", {}).items()},
        )

"""Finds capability the company does not yet have, instead of asking for it.

When a strategy is blocked by something Guildless cannot currently do, the
tempting move is to report the gap and wait. That is how a person ends up
supplying the tools one at a time, which is the job the company was built to
do itself.

So a gap starts a search: name the bottleneck, look for something that closes
it, check the evidence is real, try it cheaply, and record the result whether
it worked or not. A candidate that fails is still worth writing down, because
the next run should not rediscover it.

Nothing here may spend money in bootstrap mode. A discovery that requires a
paid subscription is simply not available yet, and becomes available the moment
revenue exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, Literal


Source = Literal["oss", "api", "service", "technique", "existing"]

Maturity = Literal["candidate", "tested", "adopted", "rejected"]


@dataclass(frozen=True)
class Bottleneck:
    """A specific thing blocking a specific strategy. Never a general wish.

    "The video quality fails the delivery gate" is a bottleneck. "The
    architecture could be better" is not, and must never start a search.
    """

    capability: str
    blocked_strategy: str
    evidence: str

    @property
    def actionable(self) -> bool:
        return bool(self.capability.strip() and self.evidence.strip())


@dataclass
class Candidate:
    name: str
    source: Source
    #: Where the claim came from. An unsourced candidate is a guess.
    reference: str
    #: Cost to try it. Anything above zero is unavailable while cash is zero.
    trial_cost_yen: int = 0
    license: str = ""
    maturity: Maturity = "candidate"
    note: str = ""


@dataclass
class CapabilityLedger:
    """What the company can do, and what it already tried and rejected."""

    capabilities: set[str] = field(default_factory=set)
    rejected: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)

    def adopt(self, capability: str, candidate: Candidate, note: str = "") -> None:
        self.capabilities.add(capability)
        candidate.maturity = "adopted"
        self._log("adopted", capability, candidate.name, note)

    def reject(self, capability: str, candidate: Candidate, reason: str) -> None:
        # Keyed by candidate so a different tool can still be tried for the
        # same capability later.
        self.rejected[candidate.name] = reason
        candidate.maturity = "rejected"
        self._log("rejected", capability, candidate.name, reason)

    def already_rejected(self, candidate: Candidate) -> bool:
        return candidate.name in self.rejected

    def _log(self, action: str, capability: str, candidate: str, note: str) -> None:
        self.history.append({
            "at": datetime.now(UTC).isoformat(),
            "action": action,
            "capability": capability,
            "candidate": candidate,
            "note": note,
        })


@dataclass
class DiscoveryResult:
    resolved: bool
    capability: str
    adopted: Candidate | None
    tried: list[str] = field(default_factory=list)
    reason: str = ""


class DiscoveryEngine:
    """bottleneck -> search -> trial -> capability update, with no human step."""

    def __init__(
        self,
        *,
        search: Callable[[Bottleneck], list[Candidate]],
        trial: Callable[[Bottleneck, Candidate], tuple[bool, str]],
        ledger: CapabilityLedger,
        affordable: Callable[[int], bool] = lambda cost: cost == 0,
        max_trials: int = 3,
    ):
        self.search = search
        self.trial = trial
        self.ledger = ledger
        self.affordable = affordable
        self.max_trials = max_trials

    def resolve(self, bottleneck: Bottleneck) -> DiscoveryResult:
        if not bottleneck.actionable:
            # Refusing vague bottlenecks is what keeps this from becoming an
            # open-ended rebuild of the system for its own sake.
            return DiscoveryResult(
                False, bottleneck.capability, None,
                reason="ボトルネックが具体的でないため探索しません",
            )

        candidates = [
            c for c in self.search(bottleneck)
            if not self.ledger.already_rejected(c) and self.affordable(c.trial_cost_yen)
        ]
        if not candidates:
            return DiscoveryResult(
                False, bottleneck.capability, None,
                reason="現在の資金で試せる候補がありません",
            )

        tried: list[str] = []
        for candidate in candidates[: self.max_trials]:
            tried.append(candidate.name)
            passed, note = self.trial(bottleneck, candidate)
            if passed:
                self.ledger.adopt(bottleneck.capability, candidate, note)
                return DiscoveryResult(True, bottleneck.capability, candidate, tried, note)
            self.ledger.reject(bottleneck.capability, candidate, note)

        return DiscoveryResult(
            False, bottleneck.capability, None, tried,
            reason=f"{len(tried)}件試したがボトルネックを解消できませんでした",
        )

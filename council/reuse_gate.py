"""Refuses to let Guildless build what already exists.

Writing something is more satisfying than finding it, and the result looks like
progress either way, so the preference has to be enforced rather than
encouraged. Building from scratch is the last option, and reaching it requires
showing the search happened, that real candidates were considered, and why each
was rejected.

The gate is deterministic. A model asked "did you search properly?" will say
yes, so the check is on recorded facts — a completed search, a candidate count,
written rejection reasons — and only then does a model get an opinion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from council.failure_ledger import Match, Proposal, match


Resolution = Literal[
    "reuse_existing", "compose_existing", "wrap_existing", "fork_existing", "build_new"
]

#: In order. Each step is only reachable when everything above it fails.
RESOLUTION_PRIORITY: tuple[Resolution, ...] = (
    "reuse_existing", "compose_existing", "wrap_existing", "fork_existing", "build_new",
)

#: A candidate scoring at or above this makes building from scratch indefensible.
GOOD_ENOUGH = 0.7


@dataclass
class Candidate:
    name: str
    source: str
    #: How well it meets the measurable requirements, 0..1.
    fit: float
    license: str = ""
    reason: str = ""
    rejected_because: str = ""

    @property
    def viable(self) -> bool:
        return self.fit >= GOOD_ENOUGH and not self.rejected_because


@dataclass
class GateResult:
    allowed: bool
    resolution: Resolution | None
    reason: str
    matches: list[Match] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def must_search(self) -> bool:
        return any("reuse_search" in m.unmet for m in self.matches)


class ReuseScout:
    """Looks for something that already does the job, without being asked to."""

    def __init__(self, search: Callable[[str], list[Candidate]]):
        self.search = search

    def survey(self, proposal: Proposal) -> list[Candidate]:
        candidates = self.search(proposal.summary)
        proposal.reuse_search_completed = True
        proposal.candidates_evaluated = len(candidates)
        proposal.rejection_reasons = [
            f"{c.name}: {c.rejected_because}" for c in candidates if c.rejected_because
        ]
        proposal.evidence.add("reuse_search")
        if candidates:
            proposal.evidence.add("candidates_evaluated")
        if proposal.rejection_reasons or not candidates:
            proposal.evidence.add("rejection_reasons")
        return candidates


class FailureCritic:
    """Checks a proposal against mistakes already made. Runs before any build."""

    def review(self, proposal: Proposal) -> list[Match]:
        matches = match(proposal)
        if proposal.asks_human_intermediate_question:
            from council.failure_ledger import BY_ID

            matches.append(Match(BY_ID["F001"], ("human_role_check",)))
        return matches


class ReuseGate:
    """The single decision point before anything new is written."""

    def __init__(self, scout: ReuseScout, critic: FailureCritic | None = None):
        self.scout = scout
        self.critic = critic or FailureCritic()

    def decide(self, proposal: Proposal) -> GateResult:
        matches = self.critic.review(proposal)

        # Asking a person to make an intermediate call is refused outright.
        # There is no evidence that redeems it; the answer is to decide.
        if proposal.asks_human_intermediate_question:
            return GateResult(
                False, None,
                "工程途中の判断を人間に返す提案は却下します。自分で決めてください。",
                matches,
            )

        if not proposal.creates_new_primitive:
            blocking = [m for m in matches if m.blocking]
            if blocking:
                return GateResult(
                    False, None,
                    _explain(blocking), matches,
                )
            return GateResult(True, "reuse_existing", "新しい部品を作らないため通過します", matches)

        candidates = (
            self.scout.survey(proposal)
            if not proposal.reuse_search_completed
            else []
        )
        matches = self.critic.review(proposal)

        viable = sorted(
            (c for c in candidates if c.viable), key=lambda c: c.fit, reverse=True
        )
        if viable:
            best = viable[0]
            return GateResult(
                False, "wrap_existing",
                f"{best.name}（適合度{best.fit:.2f}）が要件を満たすため自作しません。"
                f"ActionGatewayの背後にアダプタとして接続します。",
                matches, candidates,
            )

        blocking = [m for m in matches if m.blocking]
        if blocking:
            return GateResult(False, None, _explain(blocking), matches, candidates)

        if not proposal.reuse_search_completed:
            return GateResult(
                False, None, "既存物の探索が完了していないため自作できません", matches, candidates
            )
        if proposal.candidates_evaluated == 0:
            return GateResult(
                False, None,
                "候補を1つも評価していません。探索が機能していない可能性があります。",
                matches, candidates,
            )
        if not proposal.rejection_reasons:
            return GateResult(
                False, None, "各候補を却下した理由が記録されていません", matches, candidates
            )

        return GateResult(
            True, "build_new",
            f"{proposal.candidates_evaluated}件を評価し、いずれも要件を満たさないため自作を許可します。",
            matches, candidates,
        )


def _explain(blocking: list[Match]) -> str:
    return "過去の失敗に該当します: " + "; ".join(
        f"{m.pattern.id} {m.pattern.pattern}（不足: {', '.join(m.unmet)}）"
        for m in blocking
    )

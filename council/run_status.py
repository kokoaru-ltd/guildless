"""Decides when a person is genuinely needed, and refuses to stop before then.

This has now moved the boundary twice, and the direction both times was the
same: away from asking.

The first version stopped because no outreach permission existed, while the
real blockage was that it had found nobody to contact -- waiting for a
permission it did not yet need. The second stopped at the side-effect boundary:
permission was requested the moment the next step reached a person. That is
better, and still wrong. It gates on *access*, so one researched email to one
prospect was treated exactly like a blast to ten thousand, and the run still
ended every attempt by handing the work back.

The boundary is the decision, not the door. Outreach, publishing a page,
creating a checkout, spending inside the capital the owner already committed --
all of it proceeds. A person is stopped only when a specific action is
irreversible and the consequence is not bounded by something they already
agreed to, which :mod:`council.decision_boundary` decides per action.

So this module no longer knows about grants at all. It reports what the run is
doing and whether it has finished; the one thing that can put it in
HUMAN_REQUIRED is a real ruling on a real pending action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from council.decision_boundary import Action, Budget, rule

Status = Literal["RUNNING", "BLOCKED", "HUMAN_REQUIRED", "SUCCESS", "TERMINAL_FAILURE"]


@dataclass
class RunFacts:
    """What the run has actually achieved, as counted state."""

    real_payments: int = 0
    prospects_inspected: int = 0
    prospects_eligible: int = 0
    delivery_proof_passed: bool = False
    #: A message exists for a specific prospect and passed the safety checks.
    message_ready: bool = False
    safety_passed: bool = False
    identity_present: bool = False
    #: Set only when the run has genuinely run out of things to try.
    strategies_exhausted: bool = False
    deadline_passed: bool = False
    capital_exhausted: bool = False
    #: The one thing that can stop the run: an action whose consequence the
    #: owner has not already authorised. None while nothing is pending.
    pending_action: Action | None = None
    budget: Budget = field(default_factory=Budget)


@dataclass
class StatusDecision:
    status: Status
    current_action: str
    human_required: list[dict[str, str]] = field(default_factory=list)
    reason: str = ""

    @property
    def waiting_on_human(self) -> bool:
        return self.status == "HUMAN_REQUIRED"


def decide(facts: RunFacts) -> StatusDecision:
    if facts.real_payments > 0:
        return StatusDecision("SUCCESS", "収支を確認しています", reason="実入金を確認しました")

    if facts.deadline_passed or facts.capital_exhausted or facts.strategies_exhausted:
        return StatusDecision(
            "TERMINAL_FAILURE",
            "この条件では実入金に到達できませんでした",
            reason="期限・資金・戦略のいずれかが尽きました",
        )

    # The only reason to stop. Note what is *not* here: having found prospects,
    # having a message ready, lacking a permission. Those are work, and work
    # proceeds.
    if facts.pending_action is not None:
        ruling = rule(facts.pending_action, facts.budget)
        if ruling.needs_human:
            return StatusDecision(
                "HUMAN_REQUIRED",
                "承認待ちです。それ以外の作業は続けています。",
                human_required=[{
                    "task": facts.pending_action.kind,
                    "title": ruling.prompt,
                    "detail": ruling.reason,
                }],
                reason=ruling.reason,
            )

    if facts.prospects_eligible == 0:
        # The real blockage, and it is Guildless's own problem to solve.
        if facts.prospects_inspected > 0:
            return StatusDecision(
                "RUNNING",
                "新しい顧客発見経路を探索しています",
                reason=f"{facts.prospects_inspected}社を検査して適格0社。別の経路を探します。",
            )
        return StatusDecision("RUNNING", "条件に合う見込み客を探しています")

    if not facts.delivery_proof_passed:
        return StatusDecision("RUNNING", "売る前に、作れることを確かめています")

    if not facts.message_ready:
        return StatusDecision("RUNNING", "見込み客ごとの提案文を作成しています")

    return StatusDecision("RUNNING", "見込み客へ接触しています")

"""Decides when a person is genuinely needed, and refuses to stop before then.

The mistake this fixes: the run reported HUMAN_REQUIRED because no outreach
grant existed, while the actual blockage was that it had found nobody to
contact. Waiting for permission it did not yet need turns the whole thing back
into an ordinary assistant — one that halts and asks, instead of working until
it hits something only a person can do.

Permission is needed at the side-effect boundary and nowhere earlier. Searching,
qualifying, researching, drafting, proving delivery and comparing strategies all
proceed without it, because none of them touch anyone. The grant is requested at
the moment there is a real prospect, a finished message, a passed safety check,
and the only remaining step is the irreversible one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Status = Literal["RUNNING", "BLOCKED", "HUMAN_REQUIRED", "SUCCESS", "TERMINAL_FAILURE"]

#: Work that reaches nobody. All of it continues without any permission.
NON_SIDE_EFFECT_WORK: frozenset[str] = frozenset({
    "customer_discovery",
    "eligibility_check",
    "channel_discovery",
    "contact_discovery",
    "case_research",
    "offer_design",
    "message_drafting",
    "delivery_proof",
    "strategy_comparison",
    "asset_generation",
    "free_sample_generation",
})


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
    grant_present: bool = False
    identity_present: bool = False
    #: Set only when the run has genuinely run out of things to try.
    strategies_exhausted: bool = False
    deadline_passed: bool = False
    capital_exhausted: bool = False


@dataclass
class StatusDecision:
    status: Status
    current_action: str
    human_required: list[dict[str, str]] = field(default_factory=list)
    reason: str = ""

    @property
    def waiting_on_human(self) -> bool:
        return self.status == "HUMAN_REQUIRED"


def at_side_effect_boundary(facts: RunFacts) -> bool:
    """True only when the next step is the irreversible one.

    Every condition must hold. A missing grant with nobody to contact is not
    a blockage, it is a permission that has not become relevant yet.
    """
    return (
        facts.prospects_eligible > 0
        and facts.message_ready
        and facts.safety_passed
        and facts.delivery_proof_passed
        and not facts.grant_present
    )


def decide(facts: RunFacts) -> StatusDecision:
    if facts.real_payments > 0:
        return StatusDecision("SUCCESS", "収支を確認しています", reason="実入金を確認しました")

    if facts.deadline_passed or facts.capital_exhausted or facts.strategies_exhausted:
        return StatusDecision(
            "TERMINAL_FAILURE",
            "この条件では実入金に到達できませんでした",
            reason="期限・資金・戦略のいずれかが尽きました",
        )

    if at_side_effect_boundary(facts):
        return StatusDecision(
            "HUMAN_REQUIRED",
            "送信の直前で止まっています。許可があれば続行します。",
            human_required=[{
                "task": "grant_external_contact",
                "title": "外部への接触を許可してください",
                "detail": (
                    f"適格な見込み客{facts.prospects_eligible}社と送信内容が用意でき、"
                    "安全確認も通っています。残るのは送信だけで、これは取り消せません。"
                ),
            }],
            reason="不可逆な外部作用の直前",
        )

    if not facts.grant_present and facts.prospects_eligible > 0 and not facts.message_ready:
        return StatusDecision(
            "RUNNING", "見込み客ごとの提案文を作成しています",
            reason="許可はまだ不要です",
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

    return StatusDecision("RUNNING", "実行を進めています")


def may_proceed_without_grant(work: str) -> bool:
    """Whether this task runs while no external permission exists."""
    return work in NON_SIDE_EFFECT_WORK

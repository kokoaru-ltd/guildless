"""Mistakes this project has actually made, in a form a machine can check.

Every entry below was paid for once. Writing them down as prose would leave
them where prose goes — read, agreed with, and repeated. As patterns they can be
matched against a proposal before any work starts, which is the only version of
"we learned from that" that survives contact with a new task.

The last entry is the one that produced this file: a browser form stack was
designed and written without anyone checking whether a browser agent already
existed. Every earlier fix in this project was a correction of a specific
mistake; this is the layer that stops them being noticed by a person first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FailurePattern:
    id: str
    pattern: str
    example: str
    rule: str
    #: Words in a proposal that suggest this mistake is being repeated.
    triggers: tuple[str, ...] = ()
    #: What the proposal must show to proceed anyway.
    requires: tuple[str, ...] = ()


LEDGER: tuple[FailurePattern, ...] = (
    FailurePattern(
        id="F001",
        pattern="intermediate_human_question",
        example="「法律を確認しますか？」を工程ごとに人間へ返した",
        rule="autonomous_goalrun_must_continue",
        triggers=("確認しますか", "続けますか", "どちらにしますか", "should i ask",
                  "ask the user", "ask the human", "続行しますか"),
        requires=("human_role_check",),
    ),
    FailurePattern(
        id="F002",
        pattern="premature_infrastructure",
        example="納品証明の前にStripe連携を進めた",
        rule="prove_delivery_before_payment_integration",
        triggers=("stripe", "決済連携", "payment integration", "課金基盤"),
        requires=("delivery_proof_passed",),
    ),
    FailurePattern(
        id="F003",
        pattern="capability_fixation",
        example="品質ゲートに落ちた後もアニメ案を続けようとした",
        rule="pivot_when_capability_gate_fails",
        triggers=("もう一度試す", "同じ方法で", "retry same", "再挑戦"),
        requires=("pivot_considered",),
    ),
    FailurePattern(
        id="F004",
        pattern="human_discovered_missing_tool",
        example="必要なツールを人間が先に見つけて渡した",
        rule="capability_gap_triggers_external_discovery",
        triggers=("必要なツールがない", "能力が足りない", "capability gap",
                  "できない", "not capable"),
        requires=("reuse_search",),
    ),
    FailurePattern(
        id="F005",
        pattern="reinvent_existing_software_without_search",
        example="browser-useやStagehandを調べずPlaywright部品を自作した",
        rule="reuse_gate_before_new_primitive",
        triggers=("実装する", "自作", "新しく作る", "build", "implement",
                  "executor", "framework", "engine", "primitive", "from scratch"),
        requires=("reuse_search", "candidates_evaluated", "rejection_reasons"),
    ),
    FailurePattern(
        id="F006",
        pattern="pleasant_fake_success",
        example="全プロバイダが停止しているのに画面は穏やかな文章を表示していた",
        rule="verify_real_side_effect_and_real_outcome",
        triggers=("成功", "完了しました", "success", "done", "200 ok"),
        requires=("outcome_verified",),
    ),
)

BY_ID = {pattern.id: pattern for pattern in LEDGER}


@dataclass
class Proposal:
    """What is about to be done, stated before it is done."""

    summary: str
    #: True when this introduces a new subsystem, executor, engine or protocol.
    creates_new_primitive: bool = False
    asks_human_intermediate_question: bool = False
    #: Set by ReuseScout once it has actually looked.
    reuse_search_completed: bool = False
    candidates_evaluated: int = 0
    rejection_reasons: list[str] = field(default_factory=list)
    #: Evidence the proposal supplies to clear a matched pattern.
    evidence: set[str] = field(default_factory=set)

    def mentions(self, token: str) -> bool:
        return token.lower() in self.summary.lower()


@dataclass
class Match:
    pattern: FailurePattern
    unmet: tuple[str, ...]

    @property
    def blocking(self) -> bool:
        return bool(self.unmet)


def match(proposal: Proposal) -> list[Match]:
    """Find known mistakes this proposal resembles, and what it has not shown."""
    matches: list[Match] = []
    for pattern in LEDGER:
        if not any(proposal.mentions(trigger) for trigger in pattern.triggers):
            continue
        unmet = tuple(r for r in pattern.requires if r not in proposal.evidence)
        matches.append(Match(pattern, unmet))
    return matches


def compile_feedback(*, pattern: str, example: str, rule: str,
                     triggers: tuple[str, ...]) -> FailurePattern:
    """Turn a human's correction into a pattern that blocks the next repeat.

    Feedback that stays in a conversation is advice. Feedback compiled to a
    checkable pattern is a guarantee, and the difference is whether the same
    mistake can happen twice.
    """
    next_id = f"F{len(LEDGER) + 1:03d}"
    return FailurePattern(
        id=next_id, pattern=pattern, example=example, rule=rule,
        triggers=triggers, requires=("explicit_resolution",),
    )


def as_dicts() -> list[dict[str, Any]]:
    return [
        {"id": p.id, "pattern": p.pattern, "example": p.example, "rule": p.rule}
        for p in LEDGER
    ]

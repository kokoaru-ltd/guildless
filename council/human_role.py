"""Defines the only work a human is allowed to be asked for.

The earlier rule was "humans do physical world tasks only". A council review
killed it: payment KYC, terms consent, bank verification, refunds and legal
signature are all digital, all unavoidable, and all legally require a named
person. Under the old rule the company would have automated itself right up to
the point of taking money and then frozen, or worse, had an agent tick a
consent box on a real person's behalf.

So the boundary is not physical versus digital. It is whether the law, or a
provider's identity requirement, demands a specific accountable human.

Everything else — writing, researching, listing, sending, supporting, counting
— belongs to the machine. Asking a human for that work is the failure this file
exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


HumanTask = Literal[
    "identity_verification",
    "terms_consent",
    "bank_or_card_authorisation",
    "legal_signature",
    "irreversible_high_risk_approval",
    "physical_world_task",
]

#: Work only a legally accountable person may do. An agent doing any of these
#: on someone's behalf is impersonation, however convenient.
HUMAN_ONLY: dict[str, str] = {
    "identity_verification": "本人確認（KYC）",
    "terms_consent": "規約への本人同意",
    "bank_or_card_authorisation": "銀行・カードの本人認証",
    "legal_signature": "法的効力のある署名",
    "irreversible_high_risk_approval": "取り消せない高リスク判断の承認",
    "physical_world_task": "物理的な作業",
}

#: Work the machine must do. Handing these to a human means the product has
#: failed at the thing it is for.
MACHINE_OWNED: frozenset[str] = frozenset({
    "write_copy", "find_prospects", "send_message", "research",
    "build_product", "customer_support", "bookkeeping", "analysis",
    "schedule", "follow_up", "price_calculation", "reporting",
})


@dataclass(frozen=True)
class Ruling:
    allowed: bool
    reason: str


def may_ask_human(task: str) -> Ruling:
    """Whether the company is permitted to put this on a person."""
    if task in HUMAN_ONLY:
        return Ruling(True, f"{HUMAN_ONLY[task]}は法令・本人確認の要件により人間が行います")
    if task in MACHINE_OWNED:
        return Ruling(
            False,
            f"{task}はGuildless側が行う作業です。人間に渡すと商品として成立しません",
        )
    return Ruling(
        False,
        f"{task}は人間限定作業に該当しません。自動化できないか先に検討してください",
    )


def residual_action_count(human_tasks: list[str]) -> int:
    """How many times the customer still has to act after paying.

    This is the product quality metric: the customer bought an outcome, and
    every remaining step is outcome they did not get. Zero is not the target,
    because irreversible approvals should stay with a person, but everything
    that is not on the human-only list should be driven to zero.
    """
    return sum(1 for task in human_tasks if may_ask_human(task).allowed)


def unnecessary_human_work(human_tasks: list[str]) -> list[str]:
    """Tasks being pushed onto a person that the machine should have done."""
    return [task for task in human_tasks if not may_ask_human(task).allowed]

"""Where a person is genuinely needed: at decisions, not at access.

The model this replaces gated on reach. Anything that touched the outside world
asked permission, so one researched email to one prospect was treated exactly
like a blast to ten thousand people. That is an *access* boundary, and it is the
wrong one -- it turns the system back into an assistant waiting for a human to
open doors, which is what every agent product already does.

The boundary is the *decision*. Execution proceeds on its own; a person is
stopped only for a commitment that is irreversible and high-stakes.

What makes something high-stakes is not that it leaves the machine. It is that
the consequence is not bounded by something the owner already agreed to:

* **Spending inside the committed capital is not a new decision.** Someone who
  starts a run with ¥5,000 has already said "lose up to ¥5,000 pursuing this".
  Asking again before each ¥800 of it re-litigates a settled decision. Spending
  *past* that line is new money and does need a person.
* **Open-ended liability is never bounded by capital**, however small the first
  payment. A ¥980/month subscription and a signed contract both commit the
  owner to something the ignition figure never covered.
* **Blast radius is not bounded by capital either.** A domain burned by bulk
  mail, or a public post under the owner's name, costs something no budget
  caps and no refund undoes.
* **Destroying data is not bounded by anything.**

Everything else executes. That is the default, and it is deliberate: a system
that asks whenever it is unsure produces the same halting behaviour the access
boundary did, wearing better vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["execute", "approve"]

#: One action reaching more than this stops being outreach and becomes a
#: campaign. The risk it carries -- spam complaints, a blacklisted domain, a
#: reputation the owner cannot buy back -- is not capped by the run's money, so
#: capital cannot authorise it.
RECIPIENTS_PER_ACTION = 100

#: And the same limit across the whole run, because a hundred sends of a
#: hundred recipients each reaches ten thousand people without one action ever
#: crossing the per-action line.
RECIPIENTS_PER_RUN = 500


@dataclass(frozen=True)
class Action:
    """A concrete thing about to happen, described in the owner's terms.

    ``summary`` is what the approval prompt shows. It is written for the person
    who will read it at the moment of deciding, so it names the real object --
    "83件の休眠リードへ再接触" -- rather than the internal step that produced it.
    """

    kind: str
    summary: str
    #: Money committed by this action, in yen.
    yen: int = 0
    #: How many distinct people or organisations it reaches.
    recipients: int = 0
    #: True when the commitment continues after this action: subscriptions,
    #: retainers, anything that bills again without being asked.
    recurring: bool = False
    #: True when it creates an obligation a court would enforce.
    legally_binding: bool = False
    #: True when it destroys data or state that cannot be reconstructed.
    destroys_data: bool = False
    #: True when it puts something permanent in public under the owner's name.
    public_under_owner_identity: bool = False


@dataclass(frozen=True)
class Budget:
    """The authorisation envelope set at ignition.

    ``remaining_yen`` is what is left of the capital the owner committed, and it
    is the whole reason most spending needs no approval: it was already given.
    """

    remaining_yen: int = 0
    recipients_used: int = 0


@dataclass(frozen=True)
class Ruling:
    verdict: Verdict
    reason: str
    #: Shown verbatim when approval is required, figure included. Empty for
    #: actions that execute.
    prompt: str = ""

    @property
    def needs_human(self) -> bool:
        return self.verdict == "approve"

    def as_dict(self) -> dict[str, object]:
        return {"verdict": self.verdict, "reason": self.reason, "prompt": self.prompt}


def _yen(value: int) -> str:
    return f"¥{value:,}"


def rule(action: Action, budget: Budget) -> Ruling:
    """Decide whether this action executes or waits for a person.

    Checks run worst-consequence first, so the reason a person is stopped is
    the most serious one rather than whichever test happened to be written
    first. An action that is both a contract and over budget is reported as a
    contract, because that is what the reader needs to weigh.
    """
    if action.legally_binding:
        return Ruling(
            "approve",
            "法的な義務が発生します",
            f"{action.summary}。これは契約として拘束力を持ち、取り消せません。Approve",
        )

    if action.destroys_data:
        return Ruling(
            "approve",
            "復元できないデータの破壊です",
            f"{action.summary}。失われたデータは戻せません。Approve",
        )

    if action.recurring:
        # Size is irrelevant here. The problem is not this month's charge, it
        # is that no figure agreed at ignition bounds the total.
        return Ruling(
            "approve",
            "継続的な支払い義務は元手で上限が決まりません",
            f"{action.summary}（{_yen(action.yen)}／継続）。"
            "解約するまで請求が続きます。Approve",
        )

    if action.public_under_owner_identity:
        return Ruling(
            "approve",
            "取り消せない公開物です",
            f"{action.summary}。あなたの名前で公開され、完全には取り消せません。Approve",
        )

    if action.recipients > RECIPIENTS_PER_ACTION:
        return Ruling(
            "approve",
            "一斉送信の規模です",
            f"{action.summary}（{action.recipients:,}件）。"
            "この規模の送信は送信ドメインの評価を損なう恐れがあり、元手では取り返せません。Approve",
        )

    if budget.recipients_used + action.recipients > RECIPIENTS_PER_RUN:
        return Ruling(
            "approve",
            "このRun全体の接触数が上限を超えます",
            f"{action.summary}。このRunの接触先が累計"
            f"{budget.recipients_used + action.recipients:,}件になります。Approve",
        )

    if action.yen > budget.remaining_yen:
        return Ruling(
            "approve",
            "預かった元手を超える支出です",
            f"{action.summary}（{_yen(action.yen)}）。"
            f"残っている元手は{_yen(budget.remaining_yen)}で、超過分は新しいお金です。Approve",
        )

    # Everything else is execution of a decision the owner already made.
    if action.yen:
        return Ruling(
            "execute",
            f"元手{_yen(budget.remaining_yen)}の範囲内です",
        )
    return Ruling("execute", "取り消せる範囲の作業です")


def authorised_by_capital(action: Action, budget: Budget) -> bool:
    """Whether the ignition capital already covers this action's money.

    Separate from ``rule`` on purpose: a caller sometimes needs to know that
    the spend itself is fine while the action is stopped for another reason.
    """
    return action.yen <= budget.remaining_yen

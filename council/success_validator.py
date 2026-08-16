"""Separates "the process finished" from "the business got something".

This module exists because of a real incident. The council was returning HTTP
200 and the screen showed a calm sentence while every provider was in fact
dead and no decision existed. The process succeeded; the business got nothing.

Two ladders are graded here, and neither of them treats a returned string as
success:

* Deliberation — did the council produce something that can be acted on and
  later scored, or only prose?
* Business — how far did real money actually get? Text is the bottom rung and
  payment is the only top one.

Both are computed from structure and counted numbers. No model is asked whether
it did well, because that is exactly the judgement the incident proved
untrustworthy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


#: Deliberation quality, lowest first.
DeliberationLevel = Literal["none", "text_only", "structured", "executable"]

#: How far real money got, lowest first.
#:
#: "payment" is not the top rung. Money can arrive on an experiment that cost
#: more than it earned, and calling that success is how a company spends itself
#: to death while every dashboard stays green. Only "profit" is success.
BusinessLevel = Literal[
    "none", "text", "sent", "delivered", "replied", "meeting", "payment", "profit"
]

_BUSINESS_ORDER: tuple[BusinessLevel, ...] = (
    "none", "text", "sent", "delivered", "replied", "meeting", "payment", "profit",
)


@dataclass(frozen=True)
class Verdict:
    level: str
    #: True only when the result is good enough to act on or bank.
    ok: bool
    reason: str


def validate_deliberation(
    final_decision: dict[str, Any] | None,
    *,
    require_experiment: bool,
) -> Verdict:
    """Grade what the council actually produced.

    ``require_experiment`` is set for money questions. For those, prose is a
    failure however well written, because nothing downstream can execute or
    score it.
    """
    if not final_decision:
        return Verdict("none", False, "判断が生成されていません")

    decision_text = str(final_decision.get("decision") or "").strip()
    if not decision_text:
        return Verdict("none", False, "結論が空です")

    has_evidence = bool(final_decision.get("evidence"))
    experiment = final_decision.get("experiment")

    if not has_evidence:
        return Verdict(
            "text_only",
            not require_experiment,
            "文章はありますが根拠が示されていません",
        )

    if experiment is None:
        return Verdict(
            "structured",
            not require_experiment,
            "根拠付きの結論はありますが、実行できる実験がありません"
            if require_experiment
            else "根拠付きの結論が出ています",
        )

    missing = _missing_experiment_fields(experiment)
    if missing:
        return Verdict(
            "structured",
            False,
            f"実験の必須項目が欠けています: {'、'.join(missing)}",
        )

    return Verdict("executable", True, "根拠と実行可能な実験がそろっています")


def _missing_experiment_fields(experiment: dict[str, Any]) -> list[str]:
    required = (
        "hypothesis", "target_customer", "offer", "price_yen", "channel",
        "sample_size", "max_budget_yen", "success_condition", "failure_condition",
    )
    missing = []
    for field in required:
        value = experiment.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    # A test nobody can afford or that contacts nobody is not executable.
    if isinstance(experiment.get("sample_size"), int) and experiment["sample_size"] < 1:
        missing.append("sample_size")
    return missing


def business_level(
    *,
    text_produced: bool = False,
    sent: int = 0,
    delivered: int = 0,
    replied: int = 0,
    meetings: int = 0,
    payments: int = 0,
    revenue_yen: int = 0,
    cost_yen: int = 0,
) -> Verdict:
    """Grade how far the business actually got, from counted events only.

    Accepting a send is not delivery, delivery is not a reply, none of them are
    money, and money that cost more to earn than it brought in is not success
    either. Only profit passes.
    """
    if payments > 0:
        net = revenue_yen - cost_yen
        if net > 0:
            return Verdict("profit", True, f"入金{payments}件・純増¥{net:,}")
        return Verdict(
            "payment",
            False,
            f"入金{payments}件はありましたが、売上¥{revenue_yen:,}に対し費用¥{cost_yen:,}で赤字です",
        )
    if meetings > 0:
        return Verdict("meeting", False, f"商談{meetings}件まで進みましたが入金はありません")
    if replied > 0:
        return Verdict("replied", False, f"返信{replied}件がありましたが商談も入金もありません")
    if delivered > 0:
        return Verdict("delivered", False, f"{delivered}件が届きましたが反応がありません")
    if sent > 0:
        return Verdict("sent", False, f"{sent}件を送信しましたが到達確認がありません")
    if text_produced:
        return Verdict("text", False, "文章を作っただけで、まだ誰にも送っていません")
    return Verdict("none", False, "外部には何も起きていません")


def at_least(level: BusinessLevel, minimum: BusinessLevel) -> bool:
    """True when ``level`` reaches ``minimum`` on the business ladder."""
    return _BUSINESS_ORDER.index(level) >= _BUSINESS_ORDER.index(minimum)

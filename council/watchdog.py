"""Detects the company going wrong, without asking a model whether it is.

Every failure this looks for has actually happened to systems like this one:
agents repeating a dead action forever, the same customer contacted twice, a
provider erroring in a loop while the bill climbs, a run reported as succeeded
while nothing reached the world, an idle fleet burning tokens overnight.

None of these are detectable by asking the system how it is doing. A model in a
meltdown loop reports that it is fine, because believing it is fine is the
failure. So every check here is arithmetic over the recorded log, and the only
outputs are stop and continue.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["warn", "stop"]


@dataclass(frozen=True)
class Alarm:
    code: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Thresholds:
    #: Identical failing action repeated this many times means it will not
    #: start working on the next attempt either.
    repeated_failure: int = 3
    #: Consecutive provider errors before the circuit opens.
    provider_error_streak: int = 3
    #: Share of the AI budget that may be spent before anything reaches a
    #: customer. Thinking is not working.
    inference_share_without_contact: float = 0.5
    #: Actions attempted with nothing executed. A fleet talking to itself.
    attempts_without_effect: int = 10


def check(
    *,
    actions: list[dict[str, Any]],
    capital_summary: dict[str, Any],
    outcome_updated: bool = True,
    thresholds: Thresholds = Thresholds(),
) -> list[Alarm]:
    """Run every check over the current log. Empty list means keep going."""
    alarms: list[Alarm] = []
    alarms += _repeated_failures(actions, thresholds)
    alarms += _provider_error_streak(actions, thresholds)
    alarms += _duplicate_effects(actions)
    alarms += _spend_without_contact(actions, capital_summary, thresholds)
    alarms += _effortless_activity(actions, thresholds)
    alarms += _silent_success(actions, outcome_updated)
    alarms += _budget_exhausted(capital_summary)
    return alarms


def should_stop(alarms: list[Alarm]) -> bool:
    return any(alarm.severity == "stop" for alarm in alarms)


def _repeated_failures(actions: list[dict], thresholds: Thresholds) -> list[Alarm]:
    """The meltdown loop: the same action failing over and over."""
    counts = Counter(
        (row.get("kind"), row.get("target"))
        for row in actions
        if row.get("status") == "failed"
    )
    return [
        Alarm(
            "repeated_failure",
            "stop",
            f"{kind}（{target}）が{count}回連続で失敗しています。再試行を止めて再検討が必要です。",
            {"kind": kind, "target": target, "count": count},
        )
        for (kind, target), count in counts.items()
        if count >= thresholds.repeated_failure
    ]


def _provider_error_streak(actions: list[dict], thresholds: Thresholds) -> list[Alarm]:
    """An outage the system keeps walking into."""
    streak = 0
    for row in reversed(actions):
        if row.get("status") == "failed":
            streak += 1
        elif row.get("status") == "executed":
            break
    if streak >= thresholds.provider_error_streak:
        return [
            Alarm(
                "provider_error_streak",
                "stop",
                f"直近{streak}件が連続で失敗しています。外部サービスの障害の可能性があります。",
                {"streak": streak},
            )
        ]
    return []


def _duplicate_effects(actions: list[dict]) -> list[Alarm]:
    """Two real-world effects under one identity. Should be impossible."""
    executed = Counter(
        row.get("idempotency_key")
        for row in actions
        if row.get("status") == "executed" and row.get("idempotency_key")
    )
    return [
        Alarm(
            "duplicate_effect",
            "stop",
            f"同一の操作キー{key}が{count}回実行されています。二重送信・二重課金の疑いがあります。",
            {"idempotency_key": key, "count": count},
        )
        for key, count in executed.items()
        if count > 1
    ]


def _spend_without_contact(
    actions: list[dict], capital: dict[str, Any], thresholds: Thresholds
) -> list[Alarm]:
    """Money going into thinking while nothing reaches a customer."""
    envelopes = capital.get("envelopes") or {}
    ai_spent = int((envelopes.get("ai_api") or {}).get("spent_yen", 0))
    ai_allocated = int((envelopes.get("ai_api") or {}).get("allocated_yen", 0))
    if ai_allocated <= 0:
        return []
    reached_someone = any(row.get("status") == "executed" for row in actions)
    share = ai_spent / ai_allocated
    if not reached_someone and share >= thresholds.inference_share_without_contact:
        return [
            Alarm(
                "spend_without_contact",
                "stop",
                f"外部接触0件のままAI費の{share:.0%}（¥{ai_spent:,}）を消費しています。考えるだけで金が減っています。",
                {"ai_spent_yen": ai_spent, "share": round(share, 3)},
            )
        ]
    return []


def _effortless_activity(actions: list[dict], thresholds: Thresholds) -> list[Alarm]:
    """Lots of attempts, nothing reaching the world."""
    if not actions:
        return []
    executed = sum(1 for row in actions if row.get("status") == "executed")
    if executed == 0 and len(actions) >= thresholds.attempts_without_effect:
        return [
            Alarm(
                "attempts_without_effect",
                "stop",
                f"{len(actions)}回試行して1件も実行できていません。全て事前チェックで止まっています。",
                {"attempts": len(actions)},
            )
        ]
    return []


def _silent_success(actions: list[dict], outcome_updated: bool) -> list[Alarm]:
    """The exact failure that already bit this project: green status, no result."""
    if any(row.get("status") == "executed" for row in actions) and not outcome_updated:
        return [
            Alarm(
                "silent_success",
                "warn",
                "外部実行は成功していますが、結果が記録されていません。成功表示だけが残る状態です。",
                {},
            )
        ]
    return []


def _budget_exhausted(capital: dict[str, Any]) -> list[Alarm]:
    envelopes = capital.get("envelopes") or {}
    experiment = envelopes.get("experiment") or {}
    allocated = int(experiment.get("allocated_yen", 0))
    available = int(experiment.get("available_yen", 0))
    if allocated > 0 and available == 0:
        return [
            Alarm(
                "budget_exhausted",
                "stop",
                "実験予算を使い切りました。結果を評価するまで新しい実験は開始できません。",
                {"allocated_yen": allocated},
            )
        ]
    return []

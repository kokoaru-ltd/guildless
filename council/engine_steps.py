"""The work the engine actually performs each tick.

Kept apart from the engine so that what runs can change without touching the
machinery that proves it ran. Each step returns a sentence describing what it
did, or an empty string when there was nothing to do — and "nothing to do" is
recorded as silence rather than as invented activity.

Every step here is read-only with respect to the outside world. Reaching anyone
requires a grant and goes through the gateway, so a tick can run unattended
without contacting a single person.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from council.prospect_funnel import from_inspection
from council.state_audit import audit, bottleneck


@dataclass
class StepContext:
    root: Path

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    def read(self, name: str, default=None):
        path = self.runs / name
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return default


def observe_state(ctx: StepContext) -> str:
    """Re-read the world. Cheap, and the basis for everything after it."""
    report = audit(ctx.root)
    payments = report.get("real_payments", 0)
    eligible = report.get("prospects_eligible", 0)
    inspected = report.get("prospects_inspected", 0)
    return (
        f"状態を確認：実入金{payments}件、見込み客{eligible}/{inspected}社、"
        f"資本¥{report.get('capital_yen', 0):,}"
    )


def diagnose_bottleneck(ctx: StepContext) -> str:
    """Name the single thing blocking revenue, from counted facts."""
    report = audit(ctx.root)
    return f"ボトルネック：{bottleneck(report)}"


def classify_losses(ctx: StepContext) -> str:
    """Work out which fix the recorded failures point at."""
    rows = ctx.read("prospect_inspection.json", [])
    if not rows:
        return ""
    funnel = from_inspection(rows)
    if not funnel.losses:
        return ""
    breakdown = "、".join(f"{k} {v}社" for k, v in funnel.losses.most_common())
    return f"失敗の内訳：{breakdown} → {funnel.next_move()}"


def check_readiness(ctx: StepContext) -> str:
    """Report what is missing before anyone can be contacted."""
    report = audit(ctx.root)
    missing = []
    if report.get("external_action_grant") == "未付与":
        missing.append("外部接触の許可")
    if report.get("sender_identity") == "未設定":
        missing.append("送信者情報")
    if report.get("prospects_eligible", 0) == 0:
        missing.append("適格な見込み客")
    if not missing:
        return "送信の準備が整っています"
    return f"送信に必要で未整備：{'、'.join(missing)}"


def build_steps(root: Path) -> list[tuple[str, Callable[[], str]]]:
    ctx = StepContext(Path(root))
    return [
        ("observe", lambda: observe_state(ctx)),
        ("diagnose", lambda: diagnose_bottleneck(ctx)),
        ("classify", lambda: classify_losses(ctx)),
        ("readiness", lambda: check_readiness(ctx)),
    ]

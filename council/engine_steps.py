"""The work performed each pass.

Kept apart from the loop machinery so that what runs can change without
touching the machinery that proves it ran. Each step returns a sentence
describing what it did, or an empty string when there was nothing to do — and
"nothing to do" is recorded as silence rather than as invented activity.

This used to be four read-only steps: observe, diagnose, classify, check
readiness. Every one read a file and described it, so the company could run for
a week with nothing changing but the timestamp. The screen was honest about a
system that was doing nothing.

Now the pass is the business itself — find, write, read the answers, ask for
money, bank what arrived — driven through :mod:`council.world`. Which world it
runs against is a deployment choice; the loop is identical either way, because
a mock with its own control flow tests something you never shipped. Simulated
receipts carry their provenance and are counted separately, so a simulation can
advance the funnel without ever moving the cash figure.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from council.operator import Operator
from council.prospect_funnel import from_inspection
from council.state_audit import audit, bottleneck
from council.world import SimulatedWorld


@dataclass
class StepContext:
    root: Path
    #: Set by ``build_steps``. Observation reads the live ledger when one
    #: exists, so the reported state is the pass that just ran rather than a
    #: file written some time ago.
    operator: object | None = None

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
    """Report the state the pass just produced.

    Returns silence until something has happened. A running company that has
    inspected nobody has nothing to say, and saying it anyway is how the old
    version filled a week with activity that was not activity.
    """
    live = getattr(ctx.operator, "ledger", None)
    if live is None:
        return ""
    if not live.inspected:
        return ""
    return (
        f"状態：見込み客{len(live.eligible)}/{live.inspected}社、"
        f"接触{len(live.contacted)}件、返信{len(live.replied)}件、"
        f"入金¥{live.cash_yen:,}"
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


def build_operator(root: Path, world=None) -> Operator:
    """The company's working state, built from what the run has settled on.

    Separate from ``build_steps`` so the API can hold the same object the loop
    is mutating. The screen must read the ledger the pass just wrote, not a
    second copy that agrees with it only sometimes.
    """
    report = audit(Path(root))
    return Operator(
        world=world or SimulatedWorld(),
        offer=str(report.get("offer_name") or ""),
        price_yen=int(report.get("offer_price_yen") or 0),
        capital_yen=int(report.get("initial_capital_yen") or 0),
    )


def build_steps(
    root: Path, world=None, operator: Operator | None = None
) -> list[tuple[str, Callable[[], str]]]:
    """The pass the company runs, plus the bookkeeping that supports it.

    The business steps come first because they are the work; observation
    follows so the diagnosis describes the state the pass just produced rather
    than the one before it.
    """
    ctx = StepContext(Path(root))
    operator = operator or build_operator(root, world)
    ctx.operator = operator
    return [
        *operator.steps(),
        ("observe", lambda: observe_state(ctx)),
        ("diagnose", lambda: diagnose_bottleneck(ctx)),
        ("classify", lambda: classify_losses(ctx)),
    ]

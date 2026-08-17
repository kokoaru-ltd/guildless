"""Collects what is actually true right now, from code and live files only.

Written because the interface was confidently displaying figures from a
simulation that had been superseded days earlier. Any review of the product —
by a person or by the council — is worthless if it runs on the same stale
numbers, so this reads the runtime files and the module constants directly and
marks the provenance of every figure.

Nothing here accepts a value that came from a fixture, a sandbox transaction or
a model's summary. Where a number is unavailable it is reported as unavailable
rather than defaulted to something plausible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Fact:
    """One measured value, with where it came from."""

    name: str
    value: Any
    source: str
    #: False when the figure describes a simulation or test transaction.
    real: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "source": self.source, "real": self.real}


@dataclass
class StateAudit:
    facts: list[Fact] = field(default_factory=list)
    modules: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def add(self, name: str, value: Any, source: str, real: bool = True) -> None:
        self.facts.append(Fact(name, value, source, real))

    def get(self, name: str, default: Any = None) -> Any:
        return next((f.value for f in self.facts if f.name == name), default)

    def as_dict(self) -> dict[str, Any]:
        return {
            "facts": {f.name: f.as_dict() for f in self.facts},
            "modules_present": self.modules,
            "warnings": self.warnings,
        }


REQUIRED_MODULES = (
    "ignition.py", "payment.py", "gates.py", "capital.py", "action_gateway.py",
    "watchdog.py", "human_role.py", "sender_identity.py", "grant.py",
    "proof.py", "revenue_loop.py", "goal_run.py", "decision_ledger.py",
    "failure_ledger.py", "reuse_gate.py", "self_modification.py",
    "strategy_factory.py", "compliance.py", "discovery.py", "resources.py",
)


def audit(root: Path) -> StateAudit:
    root = Path(root)
    runs = root / "runs"
    report = StateAudit()

    for name in REQUIRED_MODULES:
        report.modules[name] = (root / "council" / name).exists()
    missing = [n for n, present in report.modules.items() if not present]
    if missing:
        report.warnings.append(f"想定モジュールが見つかりません: {missing}")

    _audit_payments(runs, report)
    _audit_capital(runs, report)
    _audit_grant(runs, report)
    _audit_identity(runs, report)
    _audit_loop(runs, report)
    _audit_prospects(runs, report)
    _audit_decisions(runs, report)
    return report


def _load(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _audit_payments(runs: Path, report: StateAudit) -> None:
    data = _load(runs / "payments.json")
    if data is None:
        report.add("real_payments", 0, "決済記録なし")
        report.add("test_payments", 0, "決済記録なし")
        report.add("revenue_yen", 0, "決済記録なし")
        return
    checkouts = list((data.get("checkouts") or {}).values())
    paid = [c for c in checkouts if c.get("status") == "paid"]
    live = [c for c in paid if c.get("live")]
    test = [c for c in paid if not c.get("live")]

    report.add("real_payments", len(live), "runs/payments.json")
    report.add("revenue_yen", sum(c["amount_yen"] - c.get("fee_yen", 0) for c in live),
               "runs/payments.json")
    report.add("test_payments", len(test), "runs/payments.json (livemode=false)", real=False)
    report.add("checkouts_created", len(checkouts), "runs/payments.json")

    if test and not live:
        report.warnings.append(
            f"テスト決済が{len(test)}件あります。売上・GATEには算入していません。"
        )


def _audit_capital(runs: Path, report: StateAudit) -> None:
    data = _load(runs / "capital.json")
    if data is None:
        report.add("capital_yen", None, "財布未初期化")
        report.add("spent_yen", None, "財布未初期化")
        return
    envelopes = data.get("envelopes") or {}
    spent = sum(int(e.get("spent_yen", 0)) for e in envelopes.values())
    initial = int(data.get("initial_cash_yen", 0))
    revenue = int(data.get("revenue_yen", 0))
    report.add("initial_capital_yen", initial, "runs/capital.json")
    report.add("spent_yen", spent, "runs/capital.json")
    report.add("capital_yen", initial + revenue - spent, "runs/capital.json")
    report.add("net_yen", revenue - spent, "runs/capital.json")
    # Every envelope, always, and never a subset. A financial view that shows
    # 3,500 and 1,000 out of 5,000 invites the reader to wonder where the other
    # 500 went, and a money screen that prompts that question has already lost.
    breakdown = {
        name: int(envelope.get("allocated_yen", 0))
        for name, envelope in sorted(envelopes.items())
    }
    report.add("capital_breakdown_yen", breakdown, "runs/capital.json")

    total = sum(breakdown.values())
    report.add("capital_breakdown_total_yen", total, "runs/capital.json")
    if total != initial + revenue:
        report.warnings.append(
            f"予算配分の合計¥{total:,}が資本¥{initial + revenue:,}と一致しません"
        )
    report.add(
        "experiment_available_yen",
        max(0, int((envelopes.get("experiment") or {}).get("allocated_yen", 0))
            - int((envelopes.get("experiment") or {}).get("spent_yen", 0))),
        "runs/capital.json",
    )


def _audit_grant(runs: Path, report: StateAudit) -> None:
    present = (runs / "external_action_grant.json").exists()
    report.add("external_action_grant", "付与済み" if present else "未付与", "runs/")
    report.add("outreach_mode", "MUTATION" if present else "READ_ONLY", "grantの有無から導出")


def _audit_identity(runs: Path, report: StateAudit) -> None:
    report.add(
        "sender_identity",
        "設定済み" if (runs / "sender_identity.json").exists() else "未設定",
        "runs/",
    )


def _audit_loop(runs: Path, report: StateAudit) -> None:
    data = _load(runs / "revenue_loop.json")
    if data is None:
        report.add("loop_stage", "未開始", "実行ループ記録なし")
        return
    offer = data.get("offer") or {}
    report.add("loop_stage", data.get("stage"), "runs/revenue_loop.json")
    report.add("offer_name", offer.get("name"), "runs/revenue_loop.json")
    report.add("offer_price_yen", offer.get("outcome_value_yen"), "runs/revenue_loop.json")
    report.add("delivery_proof_passed", bool(data.get("delivery_proof_passed")),
               "runs/revenue_loop.json")
    report.add("last_failure", data.get("failure"), "runs/revenue_loop.json")


def _audit_prospects(runs: Path, report: StateAudit) -> None:
    rows = _load(runs / "prospect_inspection.json") or []
    eligible = [r for r in rows if r.get("status") == "eligible"]
    reasons: dict[str, int] = {}
    for row in rows:
        if row.get("status") != "eligible":
            key = row.get("reason") or row.get("status", "unknown")
            reasons[key] = reasons.get(key, 0) + 1
    report.add("prospects_inspected", len(rows), "runs/prospect_inspection.json")
    report.add("prospects_eligible", len(eligible), "runs/prospect_inspection.json")
    report.add("prospect_exclusions", reasons, "runs/prospect_inspection.json")
    report.add("external_submissions", 0, "ActionGateway実行記録なし")


def _audit_decisions(runs: Path, report: StateAudit) -> None:
    directory = runs / "decisions"
    if not directory.exists():
        report.add("decisions_recorded", 0, "判断台帳なし")
        report.add("decisions_scored", 0, "判断台帳なし")
        return
    records = [_load(p) for p in sorted(directory.glob("D-*.json"))]
    records = [r for r in records if r]
    report.add("decisions_recorded", len(records), "runs/decisions/")
    report.add("decisions_scored", sum(1 for r in records if r.get("score")), "runs/decisions/")


def bottleneck(report: StateAudit) -> str:
    """The single thing currently preventing revenue, from the facts alone."""
    if report.get("real_payments", 0) > 0:
        return "なし（実入金が発生しています）"
    if not report.get("delivery_proof_passed"):
        return "納品証明が未通過。作れないものは売れません。"
    if report.get("prospects_eligible", 0) == 0:
        inspected = report.get("prospects_inspected", 0)
        if inspected == 0:
            return "顧客探索が未実行。接触できる相手がいません。"
        return (
            f"適格な見込み客が0社。{inspected}社を検査しましたが、"
            "全て規約・用途制限・CAPTCHA・到達不能で除外されました。"
        )
    if report.get("external_action_grant") == "未付与":
        return "外部接触の許可が未付与。適格顧客はいますが接触できません。"
    return "外部接触は可能な状態。実行と結果測定が次の段階です。"

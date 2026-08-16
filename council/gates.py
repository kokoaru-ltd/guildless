"""Locks advanced capability behind real revenue.

Every expensive subsystem here is genuinely good engineering, which is exactly
why it is dangerous right now. A simulated market, counterfactual forks and
self-evolving skills all produce a great deal of convincing internal activity
and no money, and a company with no customers cannot tell the difference
between that and progress.

So capability unlocks on evidence, not on argument. The gate reads one number —
how many third parties have actually paid — and refuses everything above the
current level. A model may conclude that building the simulator first is
correct; it will still be unable to do it.

One payment does not mean the market is understood, so the gates open in steps
rather than all at once on the first sale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


GateLevel = Literal["G0", "G1", "G2", "G3"]

#: Capabilities that only pay off once real market data exists. Names are the
#: single vocabulary used by callers; unknown names are denied by default.
CAPABILITIES: dict[str, GateLevel] = {
    # G0 — allowed with no revenue at all. Everything that can produce a sale.
    "web_research": "G0",
    "offer_hypothesis": "G0",
    "delivery_proof": "G0",
    "customer_search": "G0",
    "outreach": "G0",
    "landing_page": "G0",
    "payment": "G0",
    "delivery": "G0",
    "real_market_test": "G0",
    "single_model_decision": "G0",
    # G1 — one confirmed payment. Modelling assisted by real customers only.
    "simple_customer_model": "G1",
    "real_data_hypothesis_support": "G1",
    # G2 — a few payments. Enough history to compare approaches.
    "skill_comparison": "G2",
    "correction_compiler": "G2",
    "strategy_selection_from_history": "G2",
    # G3 — enough real market data to be worth simulating.
    "virtual_market": "G3",
    "customer_simulator": "G3",
    "counterfactual": "G3",
    "snapshot_fork_replay": "G3",
    "skill_evolution": "G3",
}

_LEVEL_ORDER: dict[GateLevel, int] = {"G0": 0, "G1": 1, "G2": 2, "G3": 3}

#: Payments needed to reach each level. G3 additionally needs contact volume,
#: because a simulator built on five data points is fiction with a progress bar.
_PAYMENTS_REQUIRED: dict[GateLevel, int] = {"G0": 0, "G1": 1, "G2": 3, "G3": 10}
_CONTACTS_REQUIRED_FOR_G3 = 50


class GateError(RuntimeError):
    """Raised when locked capability is invoked. Deliberately not catchable as
    a normal denial: reaching this means something tried to build ahead of the
    evidence."""


@dataclass(frozen=True)
class GateStatus:
    level: GateLevel
    real_payments: int
    real_contacts: int
    reason: str

    def allows(self, capability: str) -> bool:
        required = CAPABILITIES.get(capability)
        if required is None:
            return False
        return _LEVEL_ORDER[self.level] >= _LEVEL_ORDER[required]


def current_level(*, real_payments: int, real_contacts: int = 0) -> GateStatus:
    """Read the gate from counted reality. No estimates, no projections."""
    level: GateLevel = "G0"
    if real_payments >= _PAYMENTS_REQUIRED["G3"] and real_contacts >= _CONTACTS_REQUIRED_FOR_G3:
        level = "G3"
    elif real_payments >= _PAYMENTS_REQUIRED["G2"]:
        level = "G2"
    elif real_payments >= _PAYMENTS_REQUIRED["G1"]:
        level = "G1"

    reasons = {
        "G0": "実入金0件。売上に直結する作業のみ許可します。",
        "G1": f"実入金{real_payments}件。実顧客データによる補助のみ解禁しました。",
        "G2": f"実入金{real_payments}件。過去実績による比較・訂正を解禁しました。",
        "G3": f"実入金{real_payments}件・実接触{real_contacts}件。仮想市場を解禁しました。",
    }
    return GateStatus(level, real_payments, real_contacts, reasons[level])


def require(capability: str, *, real_payments: int, real_contacts: int = 0) -> None:
    """Raise unless the evidence justifies this capability. Call before use."""
    status = current_level(real_payments=real_payments, real_contacts=real_contacts)
    if status.allows(capability):
        return
    required = CAPABILITIES.get(capability)
    if required is None:
        raise GateError(
            f"{capability}は未登録の機能です。G0では登録された売上直結機能のみ実行できます。"
        )
    needed = _PAYMENTS_REQUIRED[required]
    detail = f"実入金{needed}件"
    if required == "G3":
        detail += f"・実接触{_CONTACTS_REQUIRED_FOR_G3}件"
    raise GateError(
        f"{capability}は{required}以上で解禁されます（{detail}が必要）。"
        f"現在は{status.level}・実入金{real_payments}件のため実行できません。"
    )


def locked_capabilities(*, real_payments: int, real_contacts: int = 0) -> list[str]:
    status = current_level(real_payments=real_payments, real_contacts=real_contacts)
    return sorted(name for name in CAPABILITIES if not status.allows(name))

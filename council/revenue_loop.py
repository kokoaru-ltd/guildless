"""The single path from an idea to verified profit.

One state machine, one offer at a time, no branches. Running three offers in
parallel would triple the spend and make every result uninterpretable, which at
five thousand yen of capital is the same as having no capital.

The order is the point. Delivery proof comes before anyone is contacted,
because selling something that cannot be produced is the most expensive
mistake available: it costs the outreach, the refund, and the reputation. If
Guildless cannot build the thing on its own, the offer dies before a single
prospect hears about it.

Offers are filtered against hard numbers rather than judged. A cheap product
made cheaply is the trap this project already fell into once — it produces
activity, a tiny sale, and no evidence that anything valuable can be sold.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from council.gates import require
from council.proof import FAILURE_MEANING, Measurements, evaluate
from council.storage import write_json


Stage = Literal[
    "offer_selection",
    "delivery_proof",
    "customer_search",
    "outreach",
    "payment",
    "delivery",
    "profit",
    "killed",
]

STAGE_ORDER: tuple[Stage, ...] = (
    "offer_selection", "delivery_proof", "customer_search",
    "outreach", "payment", "delivery", "profit",
)

STAGE_LABEL: dict[str, str] = {
    "offer_selection": "商品を選ぶ",
    "delivery_proof": "作れることを証明する",
    "customer_search": "顧客を探す",
    "outreach": "営業する",
    "payment": "入金を待つ",
    "delivery": "納品する",
    "profit": "利益を確認する",
    "killed": "停止",
}


@dataclass(frozen=True)
class OfferCriteria:
    """The floor an offer must clear. Set by the human, enforced by code."""

    min_outcome_value_yen: int = 30_000
    max_build_cost_yen: int = 5_000
    max_delivery_hours: int = 48
    allow_human_digital_work: bool = False
    allowed_legal_risk: frozenset[str] = frozenset({"low"})


@dataclass
class Offer:
    offer_id: str
    name: str
    #: What the customer pays. Not what it costs to make.
    outcome_value_yen: int
    build_cost_yen: int
    delivery_hours: int
    legal_risk: str
    customer_reachable: bool
    requires_human_digital_work: bool = False
    rationale: str = ""


@dataclass
class LoopState:
    goal: str
    stage: Stage = "offer_selection"
    offer: dict[str, Any] | None = None
    rejected_offers: list[dict[str, Any]] = field(default_factory=list)
    delivery_proof_passed: bool = False
    delivery_proof_evidence: str = ""
    measurements: dict[str, Any] = field(default_factory=dict)
    failure: str | None = None
    failure_meaning: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""


class LoopError(RuntimeError):
    pass


def screen_offers(
    candidates: list[Offer], criteria: OfferCriteria = OfferCriteria()
) -> tuple[list[Offer], list[dict[str, Any]]]:
    """Split candidates into those worth attempting and those that are not."""
    passed: list[Offer] = []
    rejected: list[dict[str, Any]] = []
    for offer in candidates:
        reasons = []
        if offer.outcome_value_yen < criteria.min_outcome_value_yen:
            reasons.append(
                f"単価¥{offer.outcome_value_yen:,}が下限¥{criteria.min_outcome_value_yen:,}未満"
            )
        if offer.build_cost_yen > criteria.max_build_cost_yen:
            reasons.append(f"初期原価¥{offer.build_cost_yen:,}が上限を超過")
        if offer.delivery_hours > criteria.max_delivery_hours:
            reasons.append(f"納品{offer.delivery_hours}時間が上限{criteria.max_delivery_hours}時間を超過")
        if offer.legal_risk not in criteria.allowed_legal_risk:
            reasons.append(f"法的リスク{offer.legal_risk}は許容外")
        if not offer.customer_reachable:
            reasons.append("顧客に到達する手段がない")
        if offer.requires_human_digital_work and not criteria.allow_human_digital_work:
            reasons.append("人間のデジタル作業を要する")
        if reasons:
            rejected.append({"offer": asdict(offer), "reasons": reasons})
        else:
            passed.append(offer)
    return passed, rejected


class RevenueLoop:
    def __init__(self, path: Path, goal: str = "Real Net Cash > 0"):
        self.path = Path(path)
        self.state = self._load(goal)

    # -- stage 1: pick exactly one offer ------------------------------------

    def select_offer(
        self, candidates: list[Offer], criteria: OfferCriteria = OfferCriteria()
    ) -> Offer:
        """Screen candidates and commit to the single best one.

        Ties break toward the cheapest to build, because at this capital the
        cost of being wrong matters more than the size of being right.
        """
        require("offer_hypothesis", real_payments=0)
        if self.state.offer is not None and self.state.stage != "killed":
            raise LoopError(
                "既に実行中の商品があります。G0では同時に1つしか実行できません。"
            )
        passed, rejected = screen_offers(candidates, criteria)
        self.state.rejected_offers = rejected
        if not passed:
            self._record("offer_selection", "条件を満たす商品候補がありませんでした")
            raise LoopError("条件を満たす商品候補がありません。条件か候補を見直してください。")
        chosen = sorted(passed, key=lambda o: (o.build_cost_yen, -o.outcome_value_yen))[0]
        self.state.offer = asdict(chosen)
        self.state.stage = "delivery_proof"
        self.state.delivery_proof_passed = False
        self.state.failure = None
        self._record("offer_selection", f"{chosen.name}（¥{chosen.outcome_value_yen:,}）を選択")
        return chosen

    # -- stage 2: prove it can be built before selling it --------------------

    def record_delivery_proof(self, *, passed: bool, evidence: str) -> None:
        require("delivery_proof", real_payments=0)
        if self.state.stage != "delivery_proof":
            raise LoopError(f"現在の段階は{self.state.stage}です")
        if not evidence.strip():
            raise LoopError("納品証明には成果物の証拠が必要です")
        self.state.delivery_proof_passed = passed
        self.state.delivery_proof_evidence = evidence.strip()
        if passed:
            self.state.stage = "customer_search"
            self._record("delivery_proof", f"納品可能を確認: {evidence[:80]}")
        else:
            self.kill("DELIVERY_FAILURE", f"納品できないため販売しません: {evidence[:80]}")

    # -- stages 3-6 ----------------------------------------------------------

    def advance(self) -> Stage:
        """Move to the next stage, refusing to skip the proof.

        ``profit`` is deliberately unreachable from here. Walking forward
        through the stages must never be able to declare the company profitable;
        only counted money can do that, via :meth:`evaluate_proof`.
        """
        if self.state.stage == "killed":
            raise LoopError("停止済みのループです")
        if self.state.stage in ("outreach", "customer_search") and not self.state.delivery_proof_passed:
            raise LoopError("納品証明が通っていないため営業に進めません")
        index = STAGE_ORDER.index(self.state.stage)
        if index >= STAGE_ORDER.index("delivery"):
            raise LoopError(
                "納品まで到達しています。利益は実測値の評価でのみ確定します。"
            )
        nxt = STAGE_ORDER[index + 1]
        require(_CAPABILITY_FOR_STAGE[nxt], real_payments=self._payments())
        self.state.stage = nxt
        self._record(nxt, f"{STAGE_LABEL[nxt]}へ進みました")
        return nxt

    def record_measurements(self, measurements: Measurements) -> None:
        self.state.measurements = asdict(measurements)
        self._record("measurement", f"接触{measurements.contacted}・入金{measurements.payments}")

    # -- terminal ------------------------------------------------------------

    def evaluate_proof(self):
        """Check Proof A against counted reality and classify any failure."""
        measurements = Measurements(
            **{**self.state.measurements,
               "delivery_proof_passed": self.state.delivery_proof_passed}
        )
        result = evaluate(measurements)
        if result.passed:
            self.state.stage = "profit"
            self.state.failure = None
            self.state.failure_meaning = ""
            self._record("profit", result.reason)
        else:
            self.state.failure = result.failure
            self.state.failure_meaning = result.failure_meaning
            self._record("evaluation", f"{result.failure}: {result.reason}")
        return result

    def kill(self, failure: str, reason: str) -> None:
        self.state.stage = "killed"
        self.state.failure = failure
        self.state.failure_meaning = FAILURE_MEANING.get(failure, "")
        self._record("killed", reason)

    def reset_for_next_offer(self) -> None:
        """Clear the slot so exactly one offer can run again."""
        if self.state.stage not in ("killed", "profit"):
            raise LoopError("実行中のループは終了させてから次に進みます")
        self.state.offer = None
        self.state.stage = "offer_selection"
        self.state.delivery_proof_passed = False
        self.state.delivery_proof_evidence = ""
        self.state.measurements = {}
        self._record("reset", "次の商品候補へ")

    # -- reading -------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        offer = self.state.offer or {}
        measurements = self.state.measurements
        return {
            "goal": self.state.goal,
            "stage": self.state.stage,
            "stage_label": STAGE_LABEL[self.state.stage],
            "offer": offer.get("name", "未選択"),
            "delivery_proof_passed": self.state.delivery_proof_passed,
            "real_payments": measurements.get("payments", 0),
            "revenue_yen": measurements.get("revenue_yen", 0),
            "direct_cost_yen": measurements.get("direct_cost_yen", 0),
            "net_yen": measurements.get("revenue_yen", 0) - measurements.get("direct_cost_yen", 0),
            "failure": self.state.failure,
            "failure_meaning": self.state.failure_meaning,
        }

    # -- internals -----------------------------------------------------------

    def _payments(self) -> int:
        return int(self.state.measurements.get("payments", 0))

    def _record(self, stage: str, message: str) -> None:
        self.state.history.append(
            {"at": datetime.now(UTC).isoformat(), "stage": stage, "message": message}
        )
        write_json(self.path, asdict(self.state))

    def _load(self, goal: str) -> LoopState:
        if not self.path.exists():
            state = LoopState(goal=goal, created_at=datetime.now(UTC).isoformat())
            write_json(self.path, asdict(state))
            return state
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return LoopState(**raw)


_CAPABILITY_FOR_STAGE: dict[str, str] = {
    "delivery_proof": "delivery_proof",
    "customer_search": "customer_search",
    "outreach": "outreach",
    "payment": "payment",
    "delivery": "delivery",
    "profit": "real_market_test",
}

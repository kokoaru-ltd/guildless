"""Records every decision as a prediction, then scores it against what happened.

An advisory system that is never checked cannot improve and cannot be trusted.
The ledger closes that gap: each decision is written down with the experiment it
predicted would work, and once the experiment reports real counted numbers the
same record is scored positive or negative.

Scoring is deliberately mechanical. Asking a model whether its own advice worked
would reproduce the bias the ledger exists to detect, so the verdict comes from
counted outcomes against the sample size the decision itself chose.

Once enough records accumulate, per-provider accuracy answers a question no
benchmark does: which model is actually right about this business.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from council.storage import write_json


Score = Literal["positive", "negative", "inconclusive"]


@dataclass(frozen=True)
class Outcome:
    """Counted results of an experiment. Every field is an observed integer."""

    contacted: int = 0
    replied: int = 0
    meetings: int = 0
    orders: int = 0
    revenue_yen: int = 0
    cost_yen: int = 0


def score_outcome(outcome: Outcome, sample_size: int) -> tuple[Score, str]:
    """Score a decision from counted numbers alone.

    A paid order proves the decision was right regardless of anything else. A
    fully spent sample with no order proves it was wrong. Anything in between is
    not yet evidence, and saying so is more useful than a flattering guess.
    """
    if outcome.orders > 0:
        return "positive", f"{outcome.contacted}件接触して{outcome.orders}件が購入した"
    if outcome.contacted >= sample_size:
        return "negative", f"予定した{sample_size}件すべてに接触したが購入は0件だった"
    return (
        "inconclusive",
        f"まだ{outcome.contacted}/{sample_size}件しか接触しておらず判断できない",
    )


@dataclass
class DecisionRecord:
    decision_id: str
    created_at: str
    kind: str
    tier: str
    question: str
    decision: str
    experiment: dict[str, Any] | None
    evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    #: Providers that proposed, and the one that judged. Scoring attributes the
    #: result to all of them so per-model accuracy can be computed later.
    proposers: list[str] = field(default_factory=list)
    judge: str = ""
    run_id: str = ""
    outcome: dict[str, Any] | None = None
    score: Score | None = None
    score_reason: str = ""
    scored_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "created_at": self.created_at,
            "kind": self.kind,
            "tier": self.tier,
            "question": self.question,
            "decision": self.decision,
            "experiment": self.experiment,
            "evidence": self.evidence,
            "assumptions": self.assumptions,
            "unknowns": self.unknowns,
            "proposers": self.proposers,
            "judge": self.judge,
            "run_id": self.run_id,
            "outcome": self.outcome,
            "score": self.score,
            "score_reason": self.score_reason,
            "scored_at": self.scored_at,
        }


class DecisionLedger:
    """Append-only store of decisions and their eventual scores."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.dir = self.root / "decisions"

    def _path(self, decision_id: str) -> Path:
        return self.dir / f"{decision_id}.json"

    def _next_id(self) -> str:
        if not self.dir.exists():
            return "D-0001"
        existing = [p.stem for p in self.dir.glob("D-*.json")]
        highest = 0
        for name in existing:
            try:
                highest = max(highest, int(name.split("-", 1)[1]))
            except (IndexError, ValueError):
                continue
        return f"D-{highest + 1:04d}"

    def record(
        self,
        *,
        kind: str,
        tier: str,
        question: str,
        final_decision: dict[str, Any],
        proposers: list[str],
        judge: str,
        run_id: str,
    ) -> DecisionRecord:
        """Write a decision down before its result is known."""
        experiment = final_decision.get("experiment")
        if experiment is not None:
            experiment = dict(experiment)
            # Models cannot produce a reliable absolute timestamp, so the clock
            # time is stamped here from the relative window they chose.
            hours = int(experiment.get("next_review_hours") or 24)
            experiment["next_review_at"] = _iso_in_hours(hours)
        record = DecisionRecord(
            decision_id=self._next_id(),
            created_at=_now(),
            kind=kind,
            tier=tier,
            question=question,
            decision=str(final_decision.get("decision") or ""),
            experiment=experiment,
            evidence=list(final_decision.get("evidence") or []),
            assumptions=list(final_decision.get("assumptions") or []),
            unknowns=list(final_decision.get("unknowns") or []),
            proposers=list(proposers),
            judge=judge,
            run_id=run_id,
        )
        write_json(self._path(record.decision_id), record.to_json())
        return record

    def get(self, decision_id: str) -> DecisionRecord | None:
        path = self._path(decision_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return DecisionRecord(**data)

    def score(self, decision_id: str, outcome: Outcome) -> DecisionRecord:
        """Attach measured results to a decision and grade it."""
        record = self.get(decision_id)
        if record is None:
            raise KeyError(decision_id)
        sample_size = int((record.experiment or {}).get("sample_size") or 0) or 1
        score, reason = score_outcome(outcome, sample_size)
        record.outcome = {
            "contacted": outcome.contacted,
            "replied": outcome.replied,
            "meetings": outcome.meetings,
            "orders": outcome.orders,
            "revenue_yen": outcome.revenue_yen,
            "cost_yen": outcome.cost_yen,
        }
        record.score = score
        record.score_reason = reason
        record.scored_at = _now()
        write_json(self._path(decision_id), record.to_json())
        return record

    def all(self) -> list[DecisionRecord]:
        if not self.dir.exists():
            return []
        records = []
        for path in sorted(self.dir.glob("D-*.json")):
            try:
                records.append(DecisionRecord(**json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, TypeError):
                continue
        return records

    def provider_accuracy(self) -> dict[str, dict[str, int]]:
        """Scored decisions per provider, so weak judgement becomes visible.

        Inconclusive decisions are counted but never held against a provider.
        """
        tally: dict[str, dict[str, int]] = {}
        for record in self.all():
            if record.score is None:
                continue
            for provider in {*record.proposers, record.judge} - {""}:
                bucket = tally.setdefault(
                    provider, {"positive": 0, "negative": 0, "inconclusive": 0}
                )
                bucket[record.score] += 1
        return tally


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _iso_in_hours(hours: int) -> str:
    from datetime import timedelta

    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()

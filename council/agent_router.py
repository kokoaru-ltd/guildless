"""Picks who leads each domain, from measured track record rather than equality.

Treating every model as an equal voter wastes the good ones and launders the
bad ones. A frontend review returned at 0.62 confidence and a security review
that has caught real defects are not two votes; they are a challenger and a
lead. So each agent carries a score per domain, updated from what its findings
actually turned out to be worth, and the highest scorer leads.

Majority vote is refused outright. Four models agreeing that something is safe
is not evidence it is safe — it is evidence they share a prior. Where a
deterministic check exists, that check decides and the models only propose what
to check.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from council.storage import write_json


Domain = Literal[
    "ux", "visual", "frontend", "backend", "security",
    "product", "outcome", "research", "coding",
]

DOMAINS: tuple[Domain, ...] = (
    "ux", "visual", "frontend", "backend", "security",
    "product", "outcome", "research", "coding",
)

#: How a finding turned out, and what it is worth to the agent's score.
FINDING_WEIGHTS: dict[str, float] = {
    "accepted": 1.0,
    "unique": 1.5,          # nobody else saw it
    "bug_found": 2.0,       # confirmed by a test
    "regression_prevented": 2.5,
    "false_positive": -1.5,  # cost real time to disprove
    "missed": -1.0,          # someone else caught what this seat should have
}


@dataclass
class Record:
    """One agent's measured history in one domain."""

    accepted_findings: int = 0
    unique_findings: int = 0
    bugs_found: int = 0
    regressions_prevented: int = 0
    false_positives: int = 0
    missed: int = 0
    implementation_passes: int = 0
    implementation_attempts: int = 0
    browser_review_correct: int = 0
    browser_review_total: int = 0
    external_evidence_agreements: int = 0

    @property
    def score(self) -> float:
        return (
            self.accepted_findings * FINDING_WEIGHTS["accepted"]
            + self.unique_findings * FINDING_WEIGHTS["unique"]
            + self.bugs_found * FINDING_WEIGHTS["bug_found"]
            + self.regressions_prevented * FINDING_WEIGHTS["regression_prevented"]
            + self.false_positives * FINDING_WEIGHTS["false_positive"]
            + self.missed * FINDING_WEIGHTS["missed"]
            + self.external_evidence_agreements * 0.5
        )

    @property
    def false_positive_rate(self) -> float:
        total = self.accepted_findings + self.false_positives
        return self.false_positives / total if total else 0.0

    @property
    def implementation_pass_rate(self) -> float:
        return (
            self.implementation_passes / self.implementation_attempts
            if self.implementation_attempts else 0.0
        )

    @property
    def evidence_count(self) -> int:
        """How much this score rests on. A high score from one call is noise."""
        return (
            self.accepted_findings + self.unique_findings + self.bugs_found
            + self.false_positives + self.missed + self.implementation_attempts
        )


@dataclass
class Assignment:
    domain: Domain
    lead: str
    challenger: str
    #: Present for decisions that are irreversible or define success.
    prosecutor: str = ""
    #: The deterministic check that actually decides, where one exists.
    oracle: str = ""
    reason: str = ""


#: Where a machine decides and the models only propose what to test.
DOMAIN_ORACLES: dict[str, str] = {
    "backend": "property tests over the money invariants",
    "security": "property tests plus the restricted-adapter regressions",
    "outcome": "the payment ledger, provider-verified only",
    "frontend": "real browser render at 1366px and 1920px",
    "visual": "five-second test on a screenshot, answered by a fresh model",
}

#: Starting positions until measurements replace them. Deliberately low
#: confidence: these are priors, not results.
SEED: dict[str, dict[str, float]] = {
    "gemini": {"ux": 2.0, "visual": 1.5, "product": 1.5, "research": 2.0, "backend": 1.0},
    "codex": {"coding": 3.0, "frontend": 2.5, "backend": 2.5},
    "deepseek_api": {"security": 2.0, "outcome": 1.5, "backend": 1.0},
    "glm": {"outcome": 1.5, "product": 1.0, "visual": 1.0},
    "sakana": {"product": 1.5, "research": 1.0},
    "qwen_vl": {"visual": 2.5, "ux": 1.5},
    "qwen_coder": {"coding": 2.0, "frontend": 1.5, "backend": 1.5},
    "qwen3": {"security": 1.0},
}


class AgentRouter:
    """Chooses lead and challenger per domain, and never counts votes."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self.records: dict[str, dict[str, Record]] = {}
        if self.path and self.path.exists():
            self._load()
        else:
            self._seed()

    # -- routing -------------------------------------------------------------

    def score(self, agent: str, domain: Domain) -> float:
        return self.records.get(agent, {}).get(domain, Record()).score

    def ranked(self, domain: Domain, available: list[str]) -> list[str]:
        return sorted(available, key=lambda a: self.score(a, domain), reverse=True)

    def assign(
        self, domain: Domain, available: list[str], *, weight: str = "normal"
    ) -> Assignment:
        """Pick the seats for one decision.

        ``weight`` is "normal", "major" for consequential design, or
        "irreversible" for anything that defines success or cannot be undone.
        Heavier decisions add a prosecutor from a different lineage; they never
        add more voters.
        """
        if not available:
            raise ValueError("利用可能なAgentがありません")

        order = self.ranked(domain, available)
        lead = order[0]
        # The challenger must be a different model family, otherwise it agrees
        # with the lead for the same reasons the lead was wrong.
        challenger = next((a for a in order[1:] if _family(a) != _family(lead)), "")
        if not challenger and len(order) > 1:
            challenger = order[1]

        prosecutor = ""
        if weight in ("major", "irreversible"):
            prosecutor = next(
                (a for a in order[1:]
                 if a not in (lead, challenger) and _family(a) not in (_family(lead), _family(challenger))),
                "",
            )

        oracle = DOMAIN_ORACLES.get(domain, "")
        if weight == "irreversible" and not oracle:
            oracle = "deterministic check required before this may proceed"

        return Assignment(
            domain=domain, lead=lead, challenger=challenger,
            prosecutor=prosecutor, oracle=oracle,
            reason=(
                f"{domain}の実績値: "
                + "、".join(f"{a}={self.score(a, domain):.1f}" for a in order[:3])
            ),
        )

    # -- learning ------------------------------------------------------------

    def record_finding(self, agent: str, domain: Domain, outcome: str) -> None:
        record = self._record(agent, domain)
        mapping = {
            "accepted": "accepted_findings",
            "unique": "unique_findings",
            "bug_found": "bugs_found",
            "regression_prevented": "regressions_prevented",
            "false_positive": "false_positives",
            "missed": "missed",
        }
        attribute = mapping.get(outcome)
        if attribute is None:
            raise ValueError(f"unknown finding outcome: {outcome}")
        setattr(record, attribute, getattr(record, attribute) + 1)
        self._save()

    def record_implementation(self, agent: str, domain: Domain, passed: bool) -> None:
        record = self._record(agent, domain)
        record.implementation_attempts += 1
        if passed:
            record.implementation_passes += 1
        self._save()

    def record_browser_review(self, agent: str, correct: bool) -> None:
        record = self._record(agent, "visual")
        record.browser_review_total += 1
        if correct:
            record.browser_review_correct += 1
        self._save()

    def report(self) -> dict[str, dict[str, float]]:
        return {
            agent: {
                domain: round(record.score, 2)
                for domain, record in domains.items()
                if record.evidence_count or record.score
            }
            for agent, domains in self.records.items()
        }

    # -- internals -----------------------------------------------------------

    def _record(self, agent: str, domain: str) -> Record:
        return self.records.setdefault(agent, {}).setdefault(domain, Record())

    def _seed(self) -> None:
        for agent, domains in SEED.items():
            for domain, value in domains.items():
                # Seeds are expressed as accepted findings so they decay in
                # significance as real results accumulate.
                self._record(agent, domain).accepted_findings = int(value)

    def _save(self) -> None:
        if not self.path:
            return
        write_json(self.path, {
            agent: {domain: asdict(record) for domain, record in domains.items()}
            for agent, domains in self.records.items()
        })

    def _load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.records = {
            agent: {domain: Record(**values) for domain, values in domains.items()}
            for agent, domains in raw.items()
        }


def _family(agent: str) -> str:
    """Group agents that would fail the same way, so a challenger differs."""
    if agent.startswith("qwen"):
        return "qwen"
    if agent in ("codex",):
        return "openai"
    return agent

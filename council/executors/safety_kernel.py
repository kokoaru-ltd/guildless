"""Keeps the thing that acts separate from the thing that decides it worked.

A browser agent is a good actuator and an unacceptable witness. It drives the
page with a model in the loop, which means it can also report that the form was
sent — and a model that has just spent twenty steps trying to submit something
is the least reliable judge of whether it succeeded. Letting the same component
act and score produces a funnel full of contacts that never happened, and every
decision downstream is then made on invented numbers.

So the actuator is treated as untrusted. It is allowed to fill and click, and
nothing else it says is believed. Permission to submit is a single-use
capability bound to one company, one form and one attempt, and it expires. The
evidence is gathered on a separate path, and only the verifier may record that
a submission happened.

This is the council's own ruling on the question, and its stated P0 risk was
exactly this boundary collapsing.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Literal, Protocol


Stage = Literal["policy", "authorised", "acted", "verified", "refused"]


class KernelError(RuntimeError):
    pass


class CapabilityError(KernelError):
    """Raised when something tries to submit without a valid, unused permit."""


# --- policy -----------------------------------------------------------------


@dataclass(frozen=True)
class PolicyVerdict:
    allowed: bool
    reason: str
    rule: str = ""


class PolicyGate(Protocol):
    """Business and legal checks. Deterministic, and never a model call."""

    def evaluate(self, rendered: Any) -> PolicyVerdict: ...


# --- single-use permission --------------------------------------------------


@dataclass
class SubmissionCapability:
    """Permission to submit exactly one form, once.

    Bound to the company, the form's shape and one attempt id, so a capability
    obtained for one target cannot be spent on another — which is the failure
    mode when an agent is free to navigate wherever it likes mid-task.
    """

    capability_id: str
    company: str
    target_url: str
    form_schema_hash: str
    attempt_id: str
    expires_at: datetime
    _spent: bool = field(default=False, repr=False)

    @property
    def spent(self) -> bool:
        return self._spent

    def expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at

    def consume(self, *, company: str, target_url: str, form_schema_hash: str,
                now: datetime | None = None) -> None:
        """Spend the permit, or refuse and stay unspent."""
        if self._spent:
            raise CapabilityError("この送信許可は既に使用済みです")
        if self.expired(now):
            raise CapabilityError("送信許可の有効期限が切れています")
        if company != self.company:
            raise CapabilityError(f"許可は{self.company}宛であり{company}には使えません")
        if target_url != self.target_url:
            raise CapabilityError("許可されたURLと異なります")
        if form_schema_hash != self.form_schema_hash:
            raise CapabilityError("フォームの構成が許可時から変化しています")
        self._spent = True


def issue_capability(*, company: str, target_url: str, form_schema_hash: str,
                     ttl_seconds: int = 180) -> SubmissionCapability:
    return SubmissionCapability(
        capability_id=uuid.uuid4().hex,
        company=company,
        target_url=target_url,
        form_schema_hash=form_schema_hash,
        attempt_id=uuid.uuid4().hex,
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )


# --- evidence, gathered independently ---------------------------------------


@dataclass
class SubmissionEvidence:
    company: str
    target_url: str
    attempt_id: str
    form_schema_hash: str
    message_hash: str
    before_text: str = ""
    after_text: str = ""
    after_url: str = ""
    #: What the actuator claimed. Recorded, never believed.
    actuator_claim: str = ""
    collected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class EvidenceCollector:
    """Reads page state directly, on a path the actuator does not control."""

    def __init__(self, read_text: Callable[[], str], read_url: Callable[[], str]):
        self.read_text = read_text
        self.read_url = read_url

    def before(self, *, company: str, target_url: str, capability: SubmissionCapability,
               message: str) -> SubmissionEvidence:
        return SubmissionEvidence(
            company=company,
            target_url=target_url,
            attempt_id=capability.attempt_id,
            form_schema_hash=capability.form_schema_hash,
            message_hash=hashlib.sha256(message.encode("utf-8", "replace")).hexdigest()[:32],
            before_text=self._safe(self.read_text)[:2_000],
        )

    def after(self, evidence: SubmissionEvidence, *, claim: str = "") -> SubmissionEvidence:
        evidence.after_text = self._safe(self.read_text)[:2_000]
        evidence.after_url = self._safe(self.read_url)
        evidence.actuator_claim = claim[:300]
        return evidence

    @staticmethod
    def _safe(reader: Callable[[], str]) -> str:
        try:
            return reader() or ""
        except Exception:  # noqa: BLE001 - unreadable state is evidence of nothing
            return ""


# --- the only component that may say a submission happened ------------------


@dataclass(frozen=True)
class SubmissionRecord:
    submitted: bool
    reason: str
    company: str
    attempt_id: str
    at: str


class SubmissionVerifier:
    """Sole writer of the submitted ledger.

    Nothing else may append to it. The actuator's claim is passed in only so it
    can be compared against the page, and a claim of success with no supporting
    page text is itself a signal worth recording.
    """

    def __init__(self, verify_text: Callable[[str], tuple[bool, str]]):
        self.verify_text = verify_text
        self._ledger: list[SubmissionRecord] = []

    @property
    def ledger(self) -> tuple[SubmissionRecord, ...]:
        return tuple(self._ledger)

    @property
    def submitted_count(self) -> int:
        return sum(1 for row in self._ledger if row.submitted)

    def judge(self, evidence: SubmissionEvidence) -> SubmissionRecord:
        confirmed, reason = self.verify_text(evidence.after_text)

        if not confirmed and evidence.actuator_claim:
            # Worth naming precisely: this is the moment an unchecked system
            # would have counted a contact that never happened.
            reason = f"{reason}（操作側は「{evidence.actuator_claim[:60]}」と報告）"

        record = SubmissionRecord(
            submitted=confirmed,
            reason=reason,
            company=evidence.company,
            attempt_id=evidence.attempt_id,
            at=datetime.now(UTC).isoformat(),
        )
        self._ledger.append(record)
        return record


# --- the kernel -------------------------------------------------------------


@dataclass
class KernelOutcome:
    stage: Stage
    submitted: bool
    reason: str
    evidence: SubmissionEvidence | None = None
    record: SubmissionRecord | None = None


class SubmissionSafetyKernel:
    """Runs policy, issues one permit, lets the actuator act, then judges."""

    def __init__(
        self,
        *,
        policy: PolicyGate,
        collector: EvidenceCollector,
        verifier: SubmissionVerifier,
        schema_hash: Callable[[Any], str],
    ):
        self.policy = policy
        self.collector = collector
        self.verifier = verifier
        self.schema_hash = schema_hash

    def submit(
        self,
        *,
        company: str,
        target_url: str,
        rendered: Any,
        message: str,
        actuate: Callable[[SubmissionCapability], str],
        dry_run: bool = True,
    ) -> KernelOutcome:
        verdict = self.policy.evaluate(rendered)
        if not verdict.allowed:
            return KernelOutcome("refused", False, verdict.reason)

        capability = issue_capability(
            company=company,
            target_url=target_url,
            form_schema_hash=self.schema_hash(rendered),
        )

        if dry_run:
            # Everything short of the irreversible act. The permit is never
            # handed over, so no code path can submit by accident.
            return KernelOutcome(
                "authorised", False, "許可が無いため送信直前で停止しました"
            )

        evidence = self.collector.before(
            company=company, target_url=target_url,
            capability=capability, message=message,
        )

        try:
            claim = actuate(capability)
        except CapabilityError as exc:
            return KernelOutcome("refused", False, f"送信能力の検証に失敗: {exc}", evidence)
        except Exception as exc:  # noqa: BLE001 - an actuator crash is not a submission
            evidence = self.collector.after(evidence, claim="")
            record = self.verifier.judge(evidence)
            return KernelOutcome(
                "acted", record.submitted,
                f"操作中に例外が発生しました: {type(exc).__name__}", evidence, record,
            )

        if not capability.spent:
            # The actuator finished without ever spending the permit, so
            # whatever it did, it was not the authorised submission.
            return KernelOutcome(
                "refused", False,
                "送信許可が使用されていません。認可された送信は行われていません。",
                evidence,
            )

        evidence = self.collector.after(evidence, claim=claim)
        record = self.verifier.judge(evidence)
        return KernelOutcome(
            "verified" if record.submitted else "acted",
            record.submitted, record.reason, evidence, record,
        )

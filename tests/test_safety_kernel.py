"""The boundary the council named as the P0 risk: actor and judge must differ."""

from datetime import UTC, datetime, timedelta

import pytest

from council.executors.form_runner import verify as verify_text
from council.executors.safety_kernel import (
    CapabilityError,
    EvidenceCollector,
    PolicyVerdict,
    SubmissionSafetyKernel,
    SubmissionVerifier,
    issue_capability,
)


class Policy:
    def __init__(self, allowed=True, reason="公開フォームです", rule=""):
        self.verdict = PolicyVerdict(allowed, reason, rule)

    def evaluate(self, rendered):
        return self.verdict


class Page:
    """Stands in for the browser. The actuator writes here; the kernel reads."""

    def __init__(self, after="送信しました。ありがとうございました。"):
        self.text = "お問い合わせフォーム"
        self.after = after
        self.url = "https://example.jp/contact"


def kernel(page, policy=None, verifier=None):
    return SubmissionSafetyKernel(
        policy=policy or Policy(),
        collector=EvidenceCollector(lambda: page.text, lambda: page.url),
        verifier=verifier or SubmissionVerifier(lambda t: (verify_text(t).submitted, verify_text(t).reason)),
        schema_hash=lambda rendered: "schema-1",
    )


def honest_actuator(page, claim="送信しました"):
    def act(capability):
        capability.consume(
            company="対象株式会社", target_url="https://example.jp/contact",
            form_schema_hash="schema-1",
        )
        page.text = page.after
        return claim

    return act


def run(page, actuate, **overrides):
    options = dict(
        company="対象株式会社", target_url="https://example.jp/contact",
        rendered=object(), message="ご提案", actuate=actuate, dry_run=False,
    )
    options.update(overrides)
    return kernel(page, **{k: v for k, v in overrides.items() if k in ("policy", "verifier")}).submit(
        **{k: v for k, v in options.items() if k not in ("policy", "verifier")}
    )


# --- the actuator is not believed ------------------------------------------

def test_a_confirmed_page_counts_as_submitted():
    page = Page()
    outcome = run(page, honest_actuator(page))
    assert outcome.submitted is True
    assert outcome.stage == "verified"


def test_an_actuator_claiming_success_on_an_unconfirmed_page_is_not_believed():
    """The exact failure the council rated P0."""
    page = Page(after="ホームへ戻る")
    outcome = run(page, honest_actuator(page, claim="送信に成功しました"))

    assert outcome.submitted is False
    assert outcome.stage == "acted"
    assert "操作側は" in outcome.record.reason


def test_an_actuator_claim_never_reaches_the_ledger_as_success():
    page = Page(after="必須項目が未入力です")
    verifier = SubmissionVerifier(lambda t: (verify_text(t).submitted, verify_text(t).reason))
    kernel(page, verifier=verifier).submit(
        company="対象株式会社", target_url="https://example.jp/contact",
        rendered=object(), message="m", actuate=honest_actuator(page, "完了しました"),
        dry_run=False,
    )
    assert verifier.submitted_count == 0
    assert len(verifier.ledger) == 1


def test_only_the_verifier_writes_the_ledger():
    verifier = SubmissionVerifier(lambda t: (True, "ok"))
    assert isinstance(verifier.ledger, tuple)
    with pytest.raises(AttributeError):
        verifier.ledger.append("偽の送信")  # type: ignore[attr-defined]


# --- permission is single-use and bound ------------------------------------

def test_a_capability_can_be_spent_once():
    capability = issue_capability(
        company="A社", target_url="https://a.jp", form_schema_hash="h"
    )
    capability.consume(company="A社", target_url="https://a.jp", form_schema_hash="h")
    with pytest.raises(CapabilityError, match="使用済み"):
        capability.consume(company="A社", target_url="https://a.jp", form_schema_hash="h")


def test_a_capability_cannot_be_spent_on_another_company():
    capability = issue_capability(
        company="A社", target_url="https://a.jp", form_schema_hash="h"
    )
    with pytest.raises(CapabilityError, match="A社"):
        capability.consume(company="B社", target_url="https://a.jp", form_schema_hash="h")
    assert capability.spent is False


def test_a_capability_cannot_be_spent_on_another_url():
    capability = issue_capability(
        company="A社", target_url="https://a.jp", form_schema_hash="h"
    )
    with pytest.raises(CapabilityError, match="URL"):
        capability.consume(company="A社", target_url="https://evil.jp", form_schema_hash="h")


def test_a_changed_form_invalidates_the_capability():
    capability = issue_capability(
        company="A社", target_url="https://a.jp", form_schema_hash="h"
    )
    with pytest.raises(CapabilityError, match="構成"):
        capability.consume(company="A社", target_url="https://a.jp", form_schema_hash="different")


def test_an_expired_capability_cannot_be_spent():
    capability = issue_capability(
        company="A社", target_url="https://a.jp", form_schema_hash="h", ttl_seconds=1
    )
    later = datetime.now(UTC) + timedelta(seconds=5)
    with pytest.raises(CapabilityError, match="期限"):
        capability.consume(
            company="A社", target_url="https://a.jp", form_schema_hash="h", now=later
        )


def test_an_actuator_that_never_spends_the_permit_did_not_submit():
    page = Page()

    def wandering(capability):
        page.text = "送信しました"  # claims the page says so, but never consumed
        return "送信しました"

    outcome = run(page, wandering)
    assert outcome.submitted is False
    assert outcome.stage == "refused"
    assert "使用されていません" in outcome.reason


# --- policy and dry run -----------------------------------------------------

def test_policy_refusal_happens_before_any_permit_exists():
    page = Page()
    reached = []
    outcome = kernel(page, policy=Policy(False, "営業お断りの記載があります")).submit(
        company="A社", target_url="https://a.jp", rendered=object(), message="m",
        actuate=lambda cap: reached.append(1) or "", dry_run=False,
    )
    assert outcome.stage == "refused"
    assert reached == []


def test_dry_run_never_hands_over_the_permit():
    page = Page()
    reached = []
    outcome = kernel(page).submit(
        company="A社", target_url="https://a.jp", rendered=object(), message="m",
        actuate=lambda cap: reached.append(1) or "", dry_run=True,
    )
    assert outcome.stage == "authorised"
    assert outcome.submitted is False
    assert reached == []


def test_an_actuator_crash_is_not_a_submission():
    page = Page(after="送信しました")

    def broken(capability):
        capability.consume(
            company="対象株式会社", target_url="https://example.jp/contact",
            form_schema_hash="schema-1",
        )
        raise RuntimeError("browser died")

    outcome = run(page, broken)
    assert outcome.submitted is False
    assert "例外" in outcome.reason


# --- evidence ---------------------------------------------------------------

def test_evidence_is_read_from_the_page_not_from_the_actuator():
    page = Page(after="受け付けました")
    outcome = run(page, honest_actuator(page, claim="でたらめ"))
    assert outcome.evidence.after_text.startswith("受け付けました")
    assert outcome.evidence.actuator_claim == "でたらめ"
    assert outcome.submitted is True


def test_evidence_records_the_attempt_and_message_identity():
    page = Page()
    outcome = run(page, honest_actuator(page))
    assert outcome.evidence.attempt_id
    assert outcome.evidence.message_hash
    assert outcome.evidence.form_schema_hash == "schema-1"

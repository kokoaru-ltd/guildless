"""Drives the real browser stack against local fixture forms.

Chromium actually renders these, so JS-injected fields, computed visibility and
confirmation steps behave as they would on a real site, without depending on
anyone else's server.
"""

from __future__ import annotations

import json

import pytest

from council.executors.browser import BrowserFetcher, detect_challenges
from council.executors.form_inspector import classify, inspect_form
from council.executors.form_runner import FormSubmissionRunner, verify
from council.sender_identity import IdentityError, SenderIdentity
from council.sender_identity import load as load_identity
from tests.fixtures.forms import FIXTURES

playwright_api = pytest.importorskip("playwright.sync_api")


IDENTITY = SenderIdentity(
    company_name="テスト合同会社",
    sender_name="山田 太郎",
    email="contact@example.jp",
    phone="03-0000-0000",
    website="https://example.jp",
)


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        instance = p.chromium.launch()
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


class FixtureFetcher(BrowserFetcher):
    """Loads fixture HTML into the real page instead of navigating."""

    def __init__(self, page, html):
        super().__init__(page)
        self.html = html

    def fetch(self, url):
        self.page.set_content(self.html)
        rendered = super().fetch("about:blank") if False else None
        # Re-read the live DOM without navigating away from the fixture.
        from council.executors.browser import FIELD_SCRIPT, FormField

        raw = self.page.evaluate(FIELD_SCRIPT) or []
        from council.executors.browser import IGNORED_INPUT_TYPES, RenderedPage

        fields = [
            FormField(
                name=str(i.get("name") or ""), field_type=str(i.get("type") or "text"),
                label=str(i.get("label") or ""), required=bool(i.get("required")),
                honeypot=bool(i.get("hidden")),
                options=[str(o) for o in (i.get("options") or [])],
            )
            for i in raw
            if str(i.get("type", "")).lower() not in IGNORED_INPUT_TYPES
        ]
        html = self.page.content()
        text = self.page.inner_text("body")
        return RenderedPage(
            url=url, final_url=url, title=self.page.title(), text=text,
            fields=fields, has_form=bool(fields),
            challenges=detect_challenges(html, text), html=html,
        )


def runner(page, fixture, tmp_path, identity=IDENTITY):
    return FormSubmissionRunner(
        FixtureFetcher(page, FIXTURES[fixture]),
        page,
        identity,
        evidence_dir=tmp_path,
        capture_screenshots=False,
    )


def submit(page, fixture, tmp_path, *, dry_run=False, key="k1", identity=IDENTITY):
    return runner(page, fixture, tmp_path, identity).run(
        company="対象株式会社", url=f"https://fixture.invalid/{fixture}",
        subject="ご提案", message="レビュー分析のご提案です。",
        idempotency_key=key, dry_run=dry_run,
    )


# --- the ten fixture cases --------------------------------------------------

def test_normal_form_is_submitted_and_confirmed(page, tmp_path):
    ok, evidence = submit(page, "normal_success", tmp_path)
    assert ok is True
    assert evidence.status == "submitted"
    assert "送信しました" in evidence.verification_reason


def test_confirmation_page_is_followed_through_to_submission(page, tmp_path):
    ok, evidence = submit(page, "confirmation_page", tmp_path)
    assert ok is True
    assert evidence.status == "submitted"


def test_js_injected_fields_are_found(page, tmp_path):
    ok, evidence = submit(page, "js_injected", tmp_path)
    assert ok is True, evidence.verification_reason


def test_an_unidentifiable_required_field_stops_the_attempt(page, tmp_path):
    ok, evidence = submit(page, "unknown_required_field", tmp_path)
    assert ok is False
    assert evidence.status == "skipped"
    assert "必須項目の意味を特定できません" in evidence.verification_reason


def test_captcha_is_never_worked_around(page, tmp_path):
    ok, evidence = submit(page, "captcha", tmp_path)
    assert ok is False
    assert evidence.status == "blocked"
    assert "recaptcha" in evidence.challenges


def test_a_honeypot_is_left_empty(page, tmp_path):
    ok, evidence = submit(page, "honeypot", tmp_path)
    # The fixture reports an error if the trap was filled. Success proves it
    # was not.
    assert ok is True, evidence.verification_reason
    assert page.locator('[name="url_confirm"]').input_value() == ""


def test_a_validation_complaint_is_not_a_submission(page, tmp_path):
    ok, evidence = submit(page, "ambiguous_success", tmp_path)
    assert ok is False
    assert evidence.status == "unconfirmed"
    assert "入力エラー" in evidence.verification_reason


def test_clicking_submit_without_confirmation_is_not_a_submission(page, tmp_path):
    ok, evidence = submit(page, "no_confirmation", tmp_path)
    assert ok is False
    assert evidence.status == "unconfirmed"


def test_without_a_grant_the_pipeline_stops_before_submitting(page, tmp_path):
    ok, evidence = submit(page, "normal_success", tmp_path, dry_run=True)
    assert ok is False
    assert evidence.status == "dry_run"
    # It got far enough to have understood the form.
    assert evidence.form_schema_hash


def test_the_same_target_twice_produces_the_same_form_hash(page, tmp_path):
    _, first = submit(page, "normal_success", tmp_path, key="a")
    _, second = submit(page, "normal_success", tmp_path, key="b")
    assert first.form_schema_hash == second.form_schema_hash
    assert first.message_hash == second.message_hash


# --- evidence ---------------------------------------------------------------

def test_every_attempt_leaves_evidence_on_disk(page, tmp_path):
    submit(page, "normal_success", tmp_path, key="evidence-1")
    saved = json.loads((tmp_path / "evidence-1.json").read_text(encoding="utf-8"))
    assert saved["status"] == "submitted"
    assert saved["idempotency_key"] == "evidence-1"
    assert saved["message_hash"]
    assert saved["timestamp"]
    assert saved["verification_reason"]


# --- identity ---------------------------------------------------------------

def test_outreach_needs_a_real_identity(tmp_path):
    assert load_identity(tmp_path) is None


def test_a_blank_identity_field_is_never_filled_in(tmp_path):
    (tmp_path / "sender_identity.json").write_text(
        json.dumps({"company_name": "テスト", "sender_name": "", "email": "a@b.jp"}),
        encoding="utf-8",
    )
    with pytest.raises(IdentityError, match="推測で補完はしません"):
        load_identity(tmp_path)


def test_a_complete_identity_loads(tmp_path):
    (tmp_path / "sender_identity.json").write_text(
        json.dumps({"company_name": "テスト合同会社", "sender_name": "山田",
                    "email": "a@b.jp", "phone": "03-0000-0000"}),
        encoding="utf-8",
    )
    identity = load_identity(tmp_path)
    assert identity.sender_name == "山田"


# --- unit level -------------------------------------------------------------

@pytest.mark.parametrize(
    "name,label,expected",
    [
        ("company", "会社名", "company"),
        ("your_name", "お名前", "name"),
        ("email", "メールアドレス", "email"),
        ("tel", "電話番号", "phone"),
        ("message", "お問い合わせ内容", "message"),
        ("q7b", "Q7-B", "unknown"),
    ],
)
def test_field_roles_are_read_from_their_own_wording(name, label, expected):
    from council.executors.browser import FormField

    role, _ = classify(FormField(name=name, field_type="text", label=label, required=True))
    assert role == expected


def test_a_form_with_no_message_box_is_unusable():
    from council.executors.browser import FormField

    plan = inspect_form([
        FormField(name="email", field_type="email", label="メール", required=True)
    ])
    assert plan.usable is False
    assert "本文" in plan.reason


@pytest.mark.parametrize(
    "text,expected",
    [
        ("送信しました", True),
        ("受け付けました", True),
        ("必須項目が未入力です", False),
        ("ホームへ戻る", False),
        ("", False),
        ("お問い合わせありがとうございます。エラーが発生しました", False),
    ],
)
def test_verification_requires_an_explicit_confirmation(text, expected):
    assert verify(text).submitted is expected


def test_a_receipt_number_counts_as_confirmation():
    assert verify("受付番号: AB-99120").submitted is True

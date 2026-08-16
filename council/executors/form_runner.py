"""Fills, submits, and then proves whether anything was actually sent.

The last step is the one that matters. Clicking submit is not sending, a 200 is
not sending, and the URL changing is not sending — plenty of forms navigate to
a page that says the required field was blank. Counting any of those as a
delivered enquiry would give the company a funnel full of contacts that never
happened, and every decision downstream would be made on it.

So a submission counts only when the page afterwards says so, and every attempt
leaves an evidence bundle: what was on the form, what was sent, what came back,
and why it was or was not judged a submission. The watchdog can then check the
claim rather than trusting it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from council.executors.browser import BrowserFetcher, RenderedPage
from council.executors.form_inspector import FormPlan, inspect_form
from council.sender_identity import SenderIdentity
from council.storage import write_json


#: Wording that appears only after a form has been accepted.
SUCCESS_MARKERS = (
    "送信しました", "送信が完了", "送信完了", "受け付けました", "受付済",
    "受付ました", "受付完了", "お問い合わせありがとう", "ありがとうございました",
    "内容を確認の上", "折り返しご連絡", "自動返信メール",
    "thank you for", "we have received", "your message has been sent",
    "successfully submitted", "submission received",
)

#: Wording that means the form came back with a complaint. Checked first,
#: because a validation page often also contains a polite thank-you elsewhere.
FAILURE_MARKERS = (
    "必須項目", "入力してください", "エラー", "正しく入力", "未入力",
    "選択してください", "は必須です",
    "is required", "please enter", "invalid", "error occurred",
)

#: Buttons that move to a confirmation step rather than sending.
CONFIRM_LABELS = ("確認", "確認画面", "入力内容の確認", "次へ", "confirm", "review")
SUBMIT_LABELS = ("送信", "送信する", "この内容で送信", "submit", "send")


class PageLike(Protocol):
    def fill(self, selector: str, value: str) -> Any: ...
    def check(self, selector: str) -> Any: ...
    def click(self, selector: str, **kwargs: Any) -> Any: ...
    def inner_text(self, selector: str) -> str: ...
    def content(self) -> str: ...
    def screenshot(self, **kwargs: Any) -> bytes: ...
    def wait_for_timeout(self, ms: int) -> Any: ...
    @property
    def url(self) -> str: ...


@dataclass
class Verification:
    submitted: bool
    reason: str
    marker: str = ""


def verify(page_text: str) -> Verification:
    """Judge whether the page after submitting says the form was accepted."""
    text = (page_text or "").lower()
    if not text.strip():
        return Verification(False, "送信後のページを読めませんでした")

    for marker in FAILURE_MARKERS:
        if marker.lower() in text:
            return Verification(False, f"入力エラーの表示があります（{marker}）", marker)

    for marker in SUCCESS_MARKERS:
        if marker.lower() in text:
            return Verification(True, f"受付確認の表示を検出しました（{marker}）", marker)

    receipt = re.search(r"(受付番号|問い合わせ番号|reference|ticket)\s*[:：]?\s*([A-Za-z0-9\-]{4,})", page_text or "")
    if receipt:
        return Verification(True, f"受付番号を検出しました（{receipt.group(2)}）", receipt.group(0))

    return Verification(False, "受付確認の表示がないため送信とみなしません")


@dataclass
class Evidence:
    company: str
    target_url: str
    final_url: str
    timestamp: str
    form_schema_hash: str
    message_hash: str
    idempotency_key: str
    verification_reason: str
    status: str
    challenges: list[str] = field(default_factory=list)
    pre_submit_text: str = ""
    post_submit_text: str = ""
    screenshots: dict[str, str] = field(default_factory=dict)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:32]


def schema_hash(plan: FormPlan) -> str:
    shape = sorted(
        f"{m.field.name}:{m.field.field_type}:{m.role}:{int(m.field.required)}"
        for m in plan.mapped
    )
    return _hash("|".join(shape))


class FormFiller:
    """Writes the identity and message into the fields that were identified."""

    def __init__(self, page: PageLike, identity: SenderIdentity):
        self.page = page
        self.identity = identity

    def fill(self, plan: FormPlan, *, subject: str, message: str) -> list[str]:
        values = self.identity.as_form_values()
        written: list[str] = []

        by_role = {
            "company": values["company"],
            "name": values["name"],
            "email": values["email"],
            "phone": values["phone"],
            "website": values["website"],
            "address": values["address"],
            "subject": subject,
            "message": message,
        }

        for mapped in plan.mapped:
            if not mapped.confident:
                continue
            if mapped.role == "consent":
                self.page.check(_selector(mapped.field.name))
                written.append("consent")
                continue
            value = by_role.get(mapped.role, "")
            if not value:
                continue
            self.page.fill(_selector(mapped.field.name), value)
            written.append(mapped.role)

        # Honeypots are left untouched on purpose. Filling one is how a site
        # identifies an automated sender, and it would be an accurate signal.
        return written


def _selector(name: str) -> str:
    return f'[name="{name}"]'


class FormSubmissionRunner:
    """The whole path for one company, in one browser session."""

    def __init__(
        self,
        fetcher: BrowserFetcher,
        page: PageLike,
        identity: SenderIdentity,
        *,
        evidence_dir: Path | None = None,
        capture_screenshots: bool = True,
    ):
        self.fetcher = fetcher
        self.page = page
        self.identity = identity
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        self.capture_screenshots = capture_screenshots

    def run(
        self,
        *,
        company: str,
        url: str,
        subject: str,
        message: str,
        idempotency_key: str,
        dry_run: bool,
    ) -> tuple[bool, Evidence]:
        rendered = self.fetcher.fetch(url)

        if rendered.blocked:
            # A CAPTCHA or login wall is the site declining automation. Leaving
            # is the only acceptable response.
            return False, self._evidence(
                company, url, rendered, idempotency_key, message,
                None, "自動化防止措置があるため送信しません", "blocked",
            )

        plan = inspect_form(rendered.fields)
        if not plan.usable:
            return False, self._evidence(
                company, url, rendered, idempotency_key, message,
                plan, plan.reason, "skipped",
            )

        missing = self.identity.missing(plan.required_roles - {"consent", "message", "subject"})
        if missing:
            return False, self._evidence(
                company, url, rendered, idempotency_key, message,
                plan, f"送信者情報に{sorted(missing)}がなく、捏造もしません", "skipped",
            )

        pre_shot = self._screenshot("pre")
        self.filler = FormFiller(self.page, self.identity)
        self.filler.fill(plan, subject=subject, message=message)

        if dry_run:
            # Everything up to the irreversible act, and then stop. Without a
            # grant the pipeline still runs so its behaviour can be observed.
            evidence = self._evidence(
                company, url, rendered, idempotency_key, message,
                plan, "許可がないため送信直前で停止しました", "dry_run",
            )
            evidence.screenshots = {"pre": pre_shot} if pre_shot else {}
            self._save(evidence)
            return False, evidence

        self._click_through()
        self.page.wait_for_timeout(1_500)
        post_text = self._text()
        verification = verify(post_text)

        evidence = self._evidence(
            company, url, rendered, idempotency_key, message,
            plan, verification.reason,
            "submitted" if verification.submitted else "unconfirmed",
        )
        evidence.post_submit_text = post_text[:2_000]
        evidence.final_url = self.page.url
        post_shot = self._screenshot("post")
        evidence.screenshots = {
            k: v for k, v in {"pre": pre_shot, "post": post_shot}.items() if v
        }
        self._save(evidence)
        return verification.submitted, evidence

    # -- internals -----------------------------------------------------------

    def _click_through(self) -> None:
        """Submit, following a confirmation step when the form has one."""
        for labels in (CONFIRM_LABELS, SUBMIT_LABELS):
            for label in labels:
                try:
                    self.page.click(f'button:has-text("{label}"), input[value*="{label}"]', timeout=3_000)
                    self.page.wait_for_timeout(1_200)
                    break
                except Exception:  # noqa: BLE001 - absent button simply means no such step
                    continue

    def _text(self) -> str:
        try:
            return self.page.inner_text("body")
        except Exception:  # noqa: BLE001
            return ""

    def _screenshot(self, tag: str) -> str:
        if not (self.capture_screenshots and self.evidence_dir):
            return ""
        try:
            path = self.evidence_dir / f"{tag}_{datetime.now(UTC).strftime('%H%M%S%f')}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path))
            return str(path)
        except Exception:  # noqa: BLE001 - evidence is valuable, not essential
            return ""

    def _evidence(
        self, company, url, rendered: RenderedPage, key, message,
        plan: FormPlan | None, reason: str, status: str,
    ) -> Evidence:
        return Evidence(
            company=company,
            target_url=url,
            final_url=rendered.final_url,
            timestamp=datetime.now(UTC).isoformat(),
            form_schema_hash=schema_hash(plan) if plan else "",
            message_hash=_hash(message),
            idempotency_key=key,
            verification_reason=reason,
            status=status,
            challenges=list(rendered.challenges),
            pre_submit_text=rendered.text[:2_000],
        )

    def _save(self, evidence: Evidence) -> None:
        if not self.evidence_dir:
            return
        path = self.evidence_dir / f"{evidence.idempotency_key}.json"
        write_json(path, asdict(evidence))

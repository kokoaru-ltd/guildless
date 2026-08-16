"""Submits public contact forms, and refuses far more often than it submits.

A contact form is not covered by the same opt-in rule as advertising email, but
that is not permission. Many forms carry a stated purpose — recruitment,
existing-customer support — or say outright that sales approaches are unwanted,
and using them anyway is both rude and the fastest way to get a domain blocked.

So every target is inspected first, and anything unclear is skipped. Skipping a
possible customer costs one lead. Submitting to a form that said not to costs
the channel. The asymmetry is the whole design, and it is why "uncertain" is
treated as "no" rather than as a question for a person.

CAPTCHAs, logins and anti-bot controls are never worked around. They are a site
saying no by other means.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Literal


Decision = Literal["eligible", "skip"]

#: Phrases that refuse sales approaches. Matching any of them ends the attempt.
SALES_PROHIBITED = (
    "営業お断り", "営業目的", "営業のご連絡", "セールス目的", "勧誘お断り",
    "売り込み", "営業メールお断り", "広告メール", "営業・勧誘",
    "no solicitation", "no sales", "not accept sales",
)

#: Forms that exist for something else. Sending a pitch through one is a
#: misuse of the channel even where nothing forbids it in words.
PURPOSE_RESTRICTED = (
    "採用", "求人", "応募", "エントリー", "リクルート",
    "既存のお客様", "契約者様専用", "会員専用", "サポート専用",
    "報道関係", "取材", "プレス", "IR", "苦情", "個人情報開示",
    "recruit", "careers", "press", "media", "support only", "existing customers",
)

#: Signals a machine must not push past.
ANTI_BOT = (
    "recaptcha", "g-recaptcha", "hcaptcha", "turnstile", "captcha",
    "data-sitekey", "cf-challenge", "認証コード", "画像認証",
)

LOGIN_REQUIRED = ("login", "ログイン", "サインイン", "会員登録", "signin", "sign in")


@dataclass
class Target:
    company: str
    url: str
    #: Fetched page text. Empty means it could not be read, which is a skip.
    page_text: str = ""
    form_fields: list[str] = field(default_factory=list)
    previously_opted_out: bool = False


@dataclass
class Inspection:
    decision: Decision
    reason: str
    #: Which check settled it, for the ledger and for later analysis.
    rule: str = ""


def inspect(target: Target, *, relevance: Callable[[Target], bool] | None = None) -> Inspection:
    """Decide whether this form may be used. Defaults to no."""
    if target.previously_opted_out:
        return Inspection("skip", "以前に配信停止の意思表示を受けています", "opt_out")

    text = (target.page_text or "").lower()
    if not text.strip():
        return Inspection("skip", "ページ内容を取得できず、利用条件を確認できません", "unreadable")

    for phrase in SALES_PROHIBITED:
        if phrase.lower() in text:
            return Inspection("skip", f"営業を禁止する記載があります（{phrase}）", "sales_prohibited")

    for phrase in PURPOSE_RESTRICTED:
        if phrase.lower() in text:
            return Inspection("skip", f"フォームの用途が限定されています（{phrase}）", "purpose_restricted")

    for phrase in ANTI_BOT:
        if phrase in text:
            return Inspection("skip", "CAPTCHA等の自動化防止措置があるため送信しません", "anti_bot")

    for phrase in LOGIN_REQUIRED:
        if phrase in text:
            return Inspection("skip", "ログインが必要なため送信しません", "login_required")

    if not target.form_fields:
        return Inspection("skip", "送信可能なフォーム項目を特定できません", "no_form")

    if relevance is not None and not relevance(target):
        return Inspection("skip", "商材と相手の事業が適合しません", "not_relevant")

    return Inspection("eligible", "公開フォームであり利用制限は見当たりません", "ok")


@dataclass
class SubmissionOutcome:
    """What actually happened. HTTP success is not on this list by itself."""

    submitted: bool
    detail: str
    #: Confirmed by the page after posting, not by the status code alone.
    confirmation: str = ""


@dataclass
class Funnel:
    """Counts along the only path that matters, each stage stricter."""

    discovered: int = 0
    eligible: int = 0
    attempted: int = 0
    submitted: int = 0
    blocked: int = 0
    replied: int = 0
    converted: int = 0
    opted_out: int = 0
    skips: dict[str, int] = field(default_factory=dict)

    def skip(self, rule: str) -> None:
        self.blocked += 1
        self.skips[rule] = self.skips.get(rule, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "discovered": self.discovered,
            "eligible": self.eligible,
            "attempted": self.attempted,
            "submitted": self.submitted,
            "blocked": self.blocked,
            "replied": self.replied,
            "converted": self.converted,
            "opted_out": self.opted_out,
            "skips": dict(self.skips),
        }


CONFIRMATION_MARKERS = (
    "送信しました", "受け付けました", "ありがとうございました", "完了しました",
    "thank you", "we have received", "submitted successfully",
)


class FormSubmissionExecutor:
    """Inspects, then submits. Refuses everything it is not sure about."""

    def __init__(
        self,
        *,
        fetch: Callable[[str], Target],
        submit: Callable[[Target, dict[str, Any]], SubmissionOutcome],
        relevance: Callable[[Target], bool] | None = None,
        funnel: Funnel | None = None,
    ):
        self.fetch = fetch
        self.submit = submit
        self.relevance = relevance
        self.funnel = funnel or Funnel()

    def __call__(self, request) -> dict[str, Any]:
        """Executor interface for :class:`council.action_gateway.ActionGateway`.

        Raises on refusal so the gateway records a failure and releases any
        money, rather than counting a skipped company as contacted.
        """
        self.funnel.discovered += 1
        try:
            target = self.fetch(request.target)
        except Exception as exc:  # noqa: BLE001 - an unreadable site is a skip, not a crash
            self.funnel.skip("fetch_failed")
            raise RuntimeError(f"取得できないため送信しません: {type(exc).__name__}") from None

        verdict = inspect(target, relevance=self.relevance)
        if verdict.decision == "skip":
            self.funnel.skip(verdict.rule)
            if verdict.rule == "opt_out":
                self.funnel.opted_out += 1
            raise RuntimeError(f"送信しません: {verdict.reason}")

        self.funnel.eligible += 1
        self.funnel.attempted += 1
        outcome = self.submit(target, request.payload)

        # A 200 is the site accepting bytes. Only a confirmation on the page
        # means the enquiry actually reached anyone.
        confirmed = outcome.submitted and _confirmed(outcome.confirmation)
        if not confirmed:
            self.funnel.skip("unconfirmed")
            raise RuntimeError(f"送信確認が取れませんでした: {outcome.detail[:120]}")

        self.funnel.submitted += 1
        return {
            "submitted": True,
            "company": target.company,
            "confirmation": outcome.confirmation[:200],
            "actual_cost_yen": 0,
        }


def _confirmed(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker.lower() in lowered for marker in CONFIRMATION_MARKERS)


def strip_html(html: str) -> str:
    """Rough text extraction. Only used to read policy statements."""
    without_scripts = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return re.sub(r"(?s)<[^>]+>", " ", without_scripts)

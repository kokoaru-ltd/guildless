"""Works out what each form field is actually for, and gives up when unsure.

The failure to avoid is a confident guess. Putting a phone number in a field
that turned out to be a budget box, or a sales pitch in "お名前", produces a
message that reads as spam sent by something that did not understand the page.

So mapping is done on the field's own words — its name, id, label and
placeholder — and every match carries a confidence. If a field the form marks
as required cannot be identified with confidence, the target is skipped. One
lead is cheap; being the company that sends garbage is not.

No model is involved. A model asked "which field is this?" will always answer,
and always with certainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Literal

from council.executors.browser import FormField


Role = Literal[
    "company", "name", "name_kana", "email", "phone", "subject",
    "message", "website", "address", "consent", "unknown",
]

#: Ordered most-specific first. An earlier match wins, which is why "会社名"
#: must be tested before the bare "名" that appears inside it.
PATTERNS: list[tuple[Role, tuple[str, ...], float]] = [
    ("company", ("company_name", "companyname", "corp", "会社名", "法人名", "貴社名", "団体名", "組織名"), 0.95),
    ("company", ("company", "kaisha", "会社", "御社"), 0.8),
    ("name_kana", ("kana", "furigana", "フリガナ", "ふりがな", "せい", "めい"), 0.9),
    ("email", ("e-mail", "email", "mail", "メール", "メールアドレス"), 0.95),
    ("phone", ("phone", "tel", "telephone", "電話", "連絡先電話", "携帯"), 0.9),
    ("subject", ("subject", "title", "件名", "題名", "お問い合わせ種別", "種別"), 0.85),
    ("message", ("message", "inquiry", "content", "body", "detail", "本文",
                 "お問い合わせ内容", "問い合わせ内容", "ご相談内容", "内容", "詳細"), 0.9),
    ("website", ("website", "url", "homepage", "ホームページ", "サイト"), 0.85),
    ("address", ("address", "住所", "所在地"), 0.85),
    ("name", ("your_name", "yourname", "fullname", "担当者名", "お名前", "氏名", "name", "名前"), 0.9),
    ("consent", ("agree", "consent", "privacy", "同意", "承諾", "個人情報の取り扱い"), 0.9),
]

#: Below this a field is treated as unidentified.
CONFIDENT = 0.75


@dataclass
class MappedField:
    field: FormField
    role: Role
    confidence: float

    @property
    def confident(self) -> bool:
        return self.confidence >= CONFIDENT


@dataclass
class FormPlan:
    usable: bool
    reason: str
    mapped: list[MappedField] = dataclass_field(default_factory=list)
    #: Required fields that could not be identified. Any entry means skip.
    unmapped_required: list[str] = dataclass_field(default_factory=list)
    honeypots: list[str] = dataclass_field(default_factory=list)

    def by_role(self, role: Role) -> MappedField | None:
        return next((m for m in self.mapped if m.role == role and m.confident), None)

    @property
    def required_roles(self) -> set[str]:
        return {m.role for m in self.mapped if m.field.required and m.confident}


def classify(form_field: FormField) -> tuple[Role, float]:
    """Identify one field from its own wording."""
    if form_field.field_type == "checkbox":
        haystack = f"{form_field.name} {form_field.label}".lower()
        if any(token in haystack for token in ("agree", "consent", "同意", "承諾", "privacy")):
            return "consent", 0.9

    haystack = f"{form_field.name} {form_field.label}".lower()
    if not haystack.strip():
        return "unknown", 0.0

    for role, tokens, confidence in PATTERNS:
        for token in tokens:
            if token in haystack:
                # A textarea is overwhelmingly the message body; a short token
                # match on one should not outrank that.
                if form_field.field_type == "textarea" and role not in ("message",):
                    return "message", 0.8
                return role, confidence

    if form_field.field_type == "textarea":
        return "message", 0.8
    if form_field.field_type == "email":
        return "email", 0.9
    if form_field.field_type == "tel":
        return "phone", 0.9
    return "unknown", 0.0


def inspect_form(fields: list[FormField]) -> FormPlan:
    """Build a fill plan, or refuse the form."""
    real = [f for f in fields if not f.honeypot]
    honeypots = [f.name for f in fields if f.honeypot]

    if not real:
        return FormPlan(False, "入力可能なフォーム項目がありません", honeypots=honeypots)

    mapped = []
    for form_field in real:
        role, confidence = classify(form_field)
        mapped.append(MappedField(form_field, role, confidence))

    unmapped_required = [
        m.field.name or m.field.label or "(無名)"
        for m in mapped
        if m.field.required and not m.confident
    ]
    if unmapped_required:
        return FormPlan(
            False,
            f"必須項目の意味を特定できません: {', '.join(unmapped_required)}",
            mapped, unmapped_required, honeypots,
        )

    if not any(m.role == "message" and m.confident for m in mapped):
        return FormPlan(False, "本文を入れる項目が見つかりません", mapped, honeypots=honeypots)
    if not any(m.role == "email" and m.confident for m in mapped):
        return FormPlan(False, "返信先メールアドレスの項目が見つかりません", mapped, honeypots=honeypots)

    return FormPlan(True, "全必須項目を特定しました", mapped, honeypots=honeypots)

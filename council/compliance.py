"""Picks a lawful way to reach buyers, without asking anyone whether to check.

Reading the rules is the run's own work. A channel that is unlawful, or lawful
only under conditions this company cannot meet, is not a question to escalate —
it is a channel to discard in favour of the next one.

The rules encoded here are Japanese, because that is where the first customers
are. They are conservative on purpose: the cost of being wrong is a banned
sending domain or a regulator, and either one ends the company long before the
saved effort pays for itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Channel = Literal["email_cold", "contact_form", "sns_dm", "phone", "marketplace", "ads"]

Verdict = Literal["allowed", "conditional", "prohibited"]


@dataclass(frozen=True)
class ChannelRule:
    channel: Channel
    verdict: Verdict
    basis: str
    #: What must be true to use it. Unmet conditions make it unusable, not a
    #: matter for discussion.
    conditions: tuple[str, ...] = ()
    #: Rough cost per contact, used to order equally lawful options.
    cost_per_contact_yen: int = 0


#: Japanese B2B outreach, ordered by how safely a company with no track record
#: can use them.
RULES: dict[str, ChannelRule] = {
    "contact_form": ChannelRule(
        "contact_form",
        # Not unconditional. A form is outside the opt-in rule for advertising
        # email, but a stated purpose -- recruitment, existing customers,
        # support -- or an explicit refusal of sales approaches makes it
        # unusable regardless. Each target is inspected before submission.
        "conditional",
        "公開フォームへの営業は特定電子メール法の「電子メール」とは扱いが異なるが、"
        "フォーム側に営業禁止・用途限定の記載がある場合は使用しない。",
        conditions=(
            "送信前に各サイトの営業禁止・用途限定の記載を確認する",
            "採用・サポート・報道など用途が限定されたフォームには送らない",
            "CAPTCHA・ログイン・bot対策があるサイトは突破せず除外する",
            "送信者の氏名・連絡先を明記する",
            "1社あたり1回、再送は返信があった場合のみ",
        ),
        cost_per_contact_yen=0,
    ),
    "email_cold": ChannelRule(
        "email_cold",
        "conditional",
        "特定電子メール法はオプトイン原則。法人等が自ら公表しているアドレスは"
        "例外になり得るが、「広告メール拒否」等の表示があれば例外は成立しない。",
        conditions=(
            "法人が自ら公開しているアドレスに限る",
            "「広告メール等は送信しないでください」等の表示があるアドレスは除外する",
            "個人アドレスには送らない",
            "送信者名・住所・連絡先・受信拒否方法を本文に明記する",
            "受信拒否後は再送しない",
            "送信ドメインにSPF/DKIM/DMARCを設定済みであること",
        ),
        cost_per_contact_yen=2,
    ),
    "marketplace": ChannelRule(
        "marketplace",
        "conditional",
        "各プラットフォームの規約に従う。多くは直接取引の誘導を禁止している。",
        conditions=("プラットフォーム外への誘導を行わない", "手数料を原価に含める"),
        cost_per_contact_yen=0,
    ),
    "sns_dm": ChannelRule(
        "sns_dm",
        "prohibited",
        "主要SNSは無差別な営業DMを規約で禁止しており、アカウント凍結リスクが高い。",
    ),
    "phone": ChannelRule(
        "phone",
        "prohibited",
        "人間のデジタル作業0の制約下では通話対応が破綻し、"
        "記録・同意の管理も満たせない。",
    ),
    "ads": ChannelRule(
        "ads",
        "prohibited",
        "広告費0の制約に反する。",
    ),
}


@dataclass(frozen=True)
class ChannelChoice:
    channel: Channel
    rule: ChannelRule
    #: Conditions the caller confirmed it can satisfy.
    satisfied: tuple[str, ...]


def usable_channels(capabilities: set[str]) -> list[ChannelChoice]:
    """Channels this company can actually use right now, cheapest first.

    ``capabilities`` is what the company can currently do — for example
    ``{"sender_identity", "opt_out_link", "spf_dkim_dmarc"}``. A conditional
    channel whose conditions are unmet is simply absent from the result, so the
    caller never has to decide whether to bend a rule.
    """
    choices: list[ChannelChoice] = []
    for rule in RULES.values():
        if rule.verdict == "prohibited":
            continue
        required = _capabilities_for(rule)
        if not required <= capabilities:
            continue
        choices.append(ChannelChoice(rule.channel, rule, rule.conditions))
    choices.sort(key=lambda c: c.rule.cost_per_contact_yen)
    return choices


def _capabilities_for(rule: ChannelRule) -> set[str]:
    if rule.channel == "email_cold":
        return {"sender_identity", "opt_out_link", "spf_dkim_dmarc", "public_company_addresses"}
    if rule.channel == "contact_form":
        return {"sender_identity", "form_submission"}
    if rule.channel == "marketplace":
        return {"marketplace_account"}
    return set()


def explain(channel: str) -> str:
    rule = RULES.get(channel)
    return rule.basis if rule else f"{channel}は未評価のため使用しません"

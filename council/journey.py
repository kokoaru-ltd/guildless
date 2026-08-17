"""The one path from a spark to money, as the person who asked would see it.

The previous screen showed observe, diagnose, classify and readiness every
twenty seconds. Those are the worker's internal steps, and a person watching
them cannot tell what was decided, what changed, or how far the idea has got
toward earning anything.

So the journey has eight stages, each one a thing a business does rather than a
thing a program does, and exactly one of them is current. Every stage reports
what was decided, why, what was actually done, what that revealed, and what
happens next — because "客を探す" is only useful alongside "前回の方法は失敗した
ので廃止した".

Stage state is derived from counted facts, never from a step having executed. A
stage is complete when its result exists, so a run that crashed halfway cannot
show a finished journey.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


StageState = Literal["done", "current", "pending", "failed"]

StageId = Literal[
    "understand", "strategy", "offer", "customers",
    "contact", "sale", "delivery", "payment",
]

STAGE_ORDER: tuple[StageId, ...] = (
    "understand", "strategy", "offer", "customers",
    "contact", "sale", "delivery", "payment",
)

TITLES: dict[str, dict[str, str]] = {
    "understand": {"ja": "火種を理解する", "en": "Understand the spark", "zh": "理解火种"},
    "strategy": {"ja": "売れる形を探す", "en": "Find a sellable shape", "zh": "寻找可售形态"},
    "offer": {"ja": "商品を作る", "en": "Build the offer", "zh": "打造商品"},
    "customers": {"ja": "客を探す", "en": "Find customers", "zh": "寻找客户"},
    "contact": {"ja": "最初の接触", "en": "First contact", "zh": "首次接触"},
    "sale": {"ja": "販売", "en": "Sell", "zh": "销售"},
    "delivery": {"ja": "納品", "en": "Deliver", "zh": "交付"},
    "payment": {"ja": "入金確認", "en": "Confirm payment", "zh": "确认入账"},
}


@dataclass
class Stage:
    id: StageId
    state: StageState
    #: One line, in the language of the business rather than the program.
    summary: str = ""
    decided: str = ""
    why: str = ""
    did: str = ""
    learned: str = ""
    next_up: str = ""

    def as_dict(self, lang: str = "ja") -> dict[str, Any]:
        return {
            "id": self.id,
            "title": TITLES[self.id].get(lang, TITLES[self.id]["ja"]),
            "state": self.state,
            "summary": self.summary,
            "decided": self.decided,
            "why": self.why,
            "did": self.did,
            "learned": self.learned,
            "next": self.next_up,
        }


@dataclass
class Journey:
    stages: list[Stage] = field(default_factory=list)

    @property
    def current(self) -> Stage | None:
        return next((s for s in self.stages if s.state == "current"), None)

    @property
    def position(self) -> int:
        """Which stage of eight, for a reader who wants one number."""
        for index, stage in enumerate(self.stages, start=1):
            if stage.state in ("current", "failed"):
                return index
        return len(self.stages)

    def as_dict(self, lang: str = "ja") -> dict[str, Any]:
        return {
            "stages": [stage.as_dict(lang) for stage in self.stages],
            "position": self.position,
            "total": len(self.stages),
        }


def build(facts: dict[str, Any]) -> Journey:
    """Derive the journey from measured state.

    ``facts`` is the audit output. Nothing here consults the worker's step
    names, because a step running is not the same as a result existing.
    """
    spark = facts.get("spark") or ""
    offer = facts.get("offer_name") or ""
    proof = bool(facts.get("delivery_proof_passed"))
    inspected = int(facts.get("prospects_inspected") or 0)
    eligible = int(facts.get("prospects_eligible") or 0)
    submissions = int(facts.get("external_submissions") or 0)
    payments = int(facts.get("real_payments") or 0)
    delivered = int(facts.get("delivered") or 0)
    exclusions = facts.get("prospect_exclusions") or {}
    granted = facts.get("external_action_grant") == "付与済み"

    stages = [
        Stage("understand", "done" if spark else "current",
              summary=spark or "火種がまだ入力されていません",
              decided=f"「{spark}」を事業候補として扱う" if spark else "",
              why="火種と使える資源だけで始められるため、計画は求めていません",
              did="火種を記録し、探索の出発点にしました" if spark else "",
              next_up="この火種で誰が金を払うかを探します"),

        Stage("strategy", "done" if offer else ("current" if spark else "pending"),
              summary=f"「{offer}」を選択" if offer else "誰が金を払うかを探しています",
              decided=f"{offer}で進める" if offer else "",
              why="単価・原価・納品時間・法的リスク・到達可能性の条件を通過した中で初期原価が最小",
              did="候補を条件で選別し、1つに絞りました" if offer else "",
              next_up="選んだ商品を実際に作れるか確かめます"),

        Stage("offer", "done" if proof else ("current" if offer else "pending"),
              summary="作れることを確認済み" if proof else "作れるかどうかを確認しています",
              decided="この商品を販売してよい" if proof else "",
              why="作れないものを売ると、接触費用と返金と信用を同時に失うため",
              did="実データで成果物を生成し、品質を検査しました" if proof else "",
              next_up="この商品を買う可能性のある相手を探します"),

        _customers_stage(proof, inspected, eligible, exclusions),

        Stage("contact",
              "done" if submissions else ("current" if (eligible and granted) else "pending"),
              summary=(f"{submissions}社へ送信済み" if submissions
                       else "接触できる相手がまだいません" if not eligible
                       else "外部への接触許可を待っています"),
              decided="許可された範囲でのみ連絡する",
              why="実在企業への連絡は取り消せないため、範囲を決めた許可が要ります",
              did=f"{submissions}社へ送信し、受付確認を取りました" if submissions else "",
              next_up="返信と反応を集計します"),

        Stage("sale", "done" if payments else "pending",
              summary=f"{payments}件が購入" if payments else "まだ購入はありません",
              decided="", why="", did="",
              next_up="購入されたら成果物を納品します"),

        Stage("delivery", "done" if delivered else "pending",
              summary=f"{delivered}件を納品" if delivered else "納品はまだありません",
              decided="", why="", did="",
              next_up="納品後、入金が確定しているか外部証拠で確認します"),

        Stage("payment", "done" if payments else "pending",
              summary=(f"実入金{payments}件を確認" if payments
                       else "外部の決済事業者が確認した入金のみを成功として数えます"),
              decided="", why="", did="",
              next_up="ここに到達して初めて成功です"),
    ]

    # Exactly one current stage: the first that is not done.
    seen_current = False
    for stage in stages:
        if stage.state == "current":
            if seen_current:
                stage.state = "pending"
            seen_current = True
    if not seen_current:
        for stage in stages:
            if stage.state == "pending":
                stage.state = "current"
                break

    return Journey(stages)


def _customers_stage(proof: bool, inspected: int, eligible: int,
                     exclusions: dict[str, Any]) -> Stage:
    """The stage that is currently failing, so it says why in plain words."""
    if eligible:
        return Stage("customers", "done",
                     summary=f"{eligible}社が条件に合致",
                     decided=f"{eligible}社へ接触する",
                     why="商品の対象であり、合法的に連絡できる相手だけを残しました",
                     did=f"{inspected}社を調べ、{eligible}社が残りました",
                     next_up="連絡内容を用意し、送信の許可を求めます")

    if not inspected:
        return Stage("customers", "current" if proof else "pending",
                     summary="実在する見込み客を探しています",
                     next_up="条件に合う相手が見つかったら、連絡内容を作ります")

    # Translate the internal taxonomy into what a person needs to know.
    plain = {
        "Error": "企業URLの推測に失敗",
        "guessed_url": "企業URLの推測に失敗",
        "purpose_restricted": "問い合わせ窓口が営業用途で使えない",
        "sales_prohibited": "営業を断る記載があった",
        "recaptcha,generic_captcha": "自動化を拒否する仕組みがあった",
        "generic_captcha": "自動化を拒否する仕組みがあった",
        "no_form": "連絡手段が特定できなかった",
        "unreadable": "サイトを読み取れなかった",
        "unreachable": "サイトに到達できなかった",
    }
    lines = [
        f"{count}社 {plain.get(reason, reason)}"
        for reason, count in sorted(exclusions.items(), key=lambda kv: -kv[1])
    ]
    biggest = max(exclusions.items(), key=lambda kv: kv[1])[0] if exclusions else ""
    dropped = plain.get(biggest, biggest)

    return Stage(
        "customers", "current",
        summary=f"{inspected}社を調べましたが、条件に合う相手は0社でした",
        decided=f"「{dropped}」が最大の原因だったため、その方法を廃止しました",
        why="同じやり方で相手を増やしても、同じ理由で落ちるだけだからです",
        did="調べた結果の内訳：" + "、".join(lines),
        learned="企業を名前から推測するのをやめ、実際に掲載されているリンクだけを辿ります",
        next_up="新しい発見手段で相手を探し直します",
    )

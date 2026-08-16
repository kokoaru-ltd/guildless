"""Asks a model what to sell, then throws out everything that fails the numbers.

The model proposes; it does not decide. Generation is judgement work and runs on
a single strong model rather than the full council, because the commitment is
made by :func:`council.revenue_loop.screen_offers`, which is arithmetic and
cannot be talked round.

The constraints are the human's, and they are hard. A model asked for business
ideas will reliably suggest something cheap and easy to build, which is the trap
this project already fell into: it produces a small sale and no evidence that
anything worth selling can be sold.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from council.revenue_loop import Offer
from council.schemas import StrictModel


class OfferCandidate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    #: What the buyer gets, stated as a finished result rather than a process.
    outcome: str = Field(min_length=1, max_length=400)
    target_customer: str = Field(min_length=1, max_length=300)
    #: Why this buyer pays now instead of later, or not at all.
    why_they_pay: str = Field(min_length=1, max_length=400)
    price_yen: int = Field(ge=0, le=10_000_000)
    build_cost_yen: int = Field(ge=0, le=10_000_000)
    delivery_hours: int = Field(ge=1, le=720)
    legal_risk: Literal["low", "medium", "high"]
    #: How the first buyers are reached without paid advertising.
    reach_method: str = Field(min_length=1, max_length=300)
    customer_reachable: bool
    requires_human_digital_work: bool
    #: Everything that must be true for this to work, stated plainly so the
    #: delivery proof can attack the weakest one first.
    key_assumption: str = Field(min_length=1, max_length=300)

    def to_offer(self, offer_id: str) -> Offer:
        return Offer(
            offer_id=offer_id,
            name=self.name,
            outcome_value_yen=self.price_yen,
            build_cost_yen=self.build_cost_yen,
            delivery_hours=self.delivery_hours,
            legal_risk=self.legal_risk,
            customer_reachable=self.customer_reachable,
            requires_human_digital_work=self.requires_human_digital_work,
            rationale=f"{self.outcome} / {self.why_they_pay}",
        )


class OfferCandidates(StrictModel):
    candidates: list[OfferCandidate] = Field(min_length=3, max_length=6)


PROMPT = """
あなたは資本¥{capital:,}しか持たない会社の事業責任者です。
第三者から実際に入金を得ることだけが目的で、それ以外の成果は無価値です。

必須条件（1つでも外れたら候補として無効）:
- 販売価格 ¥{min_price:,} 以上
- 最初の1件を納品するまでの原価 ¥{max_build:,} 以下
- 受注から納品まで {max_hours} 時間以内
- 納品物はデジタルで完結し、物流・在庫を持たない
- 人間のデジタル作業は0。営業文・リサーチ・制作・顧客対応は全てAIが行う
  （本人確認・規約同意・法的署名だけは人間が行う）
- 法的リスクが低い。医療・法律・金融の助言、資格が要る業務、広告規制が厳しい領域は除外
- 広告費0で最初の顧客に到達できる経路がある

避けるべきもの:
- 単価が低く作業量が多いもの（安い制作代行、テンプレ販売、記事作成）
- 「AIで効率化します」という手段の販売。買い手が欲しいのは結果であって道具ではない
- 買い手が受け取った後に自分で大量の作業をしなければ完成しないもの

各候補について、買い手が金を払った後に「本人が何回動く必要があるか」が
少ないほど良い商品です。

{count}個の候補を出してください。日本語で答えてください。
""".strip()


def build_prompt(
    *, capital_yen: int, min_price_yen: int, max_build_yen: int, max_hours: int, count: int = 5
) -> str:
    return PROMPT.format(
        capital=capital_yen,
        min_price=min_price_yen,
        max_build=max_build_yen,
        max_hours=max_hours,
        count=count,
    )

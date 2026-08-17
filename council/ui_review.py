"""Seven independent reviews of the product, from seven different seats.

A single model asked "is this good?" produces one opinion wearing several hats.
Independence is the point, so each role gets the same measured facts, a
different question, and no sight of the others' answers until all are in.

The roles are deliberately adversarial to each other. What a designer calls
clean, an outcome auditor calls information withheld; what a frontend engineer
calls simple, a security reviewer calls unverifiable. The disagreements are the
useful output, not a problem to smooth over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from council.schemas import StrictModel


RoleId = Literal[
    "product", "ux", "visual", "frontend", "backend", "security", "outcome"
]


@dataclass(frozen=True)
class Role:
    id: RoleId
    title: str
    seat: str
    question: str


ROLES: tuple[Role, ...] = (
    Role(
        "product", "プロダクト / 創業者",
        "この製品で金を集める立場",
        "これが何をする製品か1画面で理解できるか。火種から実入金¥1までが中心に据えられているか。"
        "よくあるAI Agentダッシュボードになっていないか。",
    ),
    Role(
        "ux", "UX",
        "説明なしで初めて触る利用者",
        "説明なしで使えるか。何を入力すればよいか、いま何をしているか、なぜ止まっているか、"
        "次に何が起きるかが分かるか。人間の介入が本当に必要な箇所はどこか。",
    ),
    Role(
        "visual", "ビジュアル / プロダクトデザイン",
        "金を払う価値のある画面かを判断する立場",
        "情報階層・余白・タイポグラフィ・密度・状態表現は適切か。"
        "AIが生成した安いダッシュボードに見えないか。重要情報が一目で見えるか。",
    ),
    Role(
        "frontend", "フロントエンド実装",
        "実際に作る立場",
        "バックエンドの真実を正しく画面へ投影できるか。モックに依存していないか。"
        "状態管理・進行表示・証拠表示をどうするか。不要な複雑性はないか。",
    ),
    Role(
        "backend", "バックエンド / システム",
        "真実を供給する立場",
        "UIに必要な真実APIは存在するか。画面の都合で成功条件が書き換えられていないか。"
        "台帳を単一の真実として扱えているか。実行イベントをどう供給するか。",
    ),
    Role(
        "security", "セキュリティ / 敵対的レビュー",
        "この画面で嘘をつく方法を探す立場",
        "Agentの自己申告を真実として表示していないか。偽の売上・偽の成功・古い状態・"
        "テスト状態が混入する経路はないか。保護された境界を画面から変更できないか。",
    ),
    Role(
        "outcome", "アウトカム監査",
        "金が増えたかだけを見る立場",
        "この画面だけで、実際の金がいくら増えたか、何を試したか、何が失敗したか、"
        "いまどこで詰まっているか、なぜその戦略を選んだかが分かるか。",
    ),
)


class ScreenElement(StrictModel):
    name: str = Field(min_length=1, max_length=60)
    #: Why it earns its place. An element without one is decoration.
    justification: str = Field(min_length=1, max_length=300)
    priority: Literal["always_visible", "one_click_away", "on_demand"]


class RoleReview(StrictModel):
    verdict: Literal["usable", "not_usable", "usable_with_changes"]
    #: The single most damaging problem from this seat.
    biggest_problem: str = Field(min_length=1, max_length=400)
    must_show: list[ScreenElement] = Field(min_length=1, max_length=10)
    #: Things that must never appear by default, and why.
    must_not_show: list[str] = Field(max_length=10)
    #: Where this seat expects to disagree with the others.
    expected_conflict: str = Field(default="", max_length=300)
    confidence: float = Field(ge=0.0, le=1.0)


def review_prompt(role: Role, facts: str) -> str:
    return f"""
あなたは{role.title}として、{role.seat}からGuildlessをレビューします。

Guildlessは、火種（「昔の写真を動かせたら面白そう」程度の思いつき）と資本と制約だけを
受け取り、市場調査・商品設計・納品証明・顧客探索・営業・決済・納品まで自律実行し、
第三者からの実入金が出るまで人間に返さない製品です。

成功の定義は変更不能です:
- LP完成・店舗公開・営業送信・返信・商談・購入ボタン押下・「買います」の返答は
  すべてPROGRESSであり成功ではありません
- 外部の決済事業者が確認した実入金のみがBUSINESS SUCCESSです
- テストモード決済は実入金ではありません

現在の実測値（これが唯一の真実。ここに無い数字を作らないこと）:
{facts}

あなたの問い:
{role.question}

架空の数値・架空の成功・存在しない機能を前提にしないでください。
現在の実測値が「実入金0円・外部送信0件・適格顧客0社」であることを踏まえ、
その状態でも利用者が正しく現実を理解できる画面を検討してください。
日本語で、指定のJSONスキーマのみを返してください。
""".strip()


def facts_block(audit_dict: dict) -> str:
    lines = []
    for name, entry in audit_dict["facts"].items():
        mark = "" if entry["real"] else "  ※実データではない"
        lines.append(f"- {name}: {entry['value']}{mark}")
    for warning in audit_dict.get("warnings", []):
        lines.append(f"- 警告: {warning}")
    return "\n".join(lines)

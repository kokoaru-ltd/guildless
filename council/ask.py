"""The question drawer: a read-only window onto a run that is already decided.

Deliberately not a chat agent. Guildless claims that an AI can run the business
end to end, and a chat box that quietly accepts "actually, drop the price"
would refute that claim while appearing to support it -- the human would be
steering and the transcript would say the machine did it. So the direction is
fixed at ignition and this channel only reads.

Two consequences follow, and both are load-bearing:

* An instruction is answered with a refusal that names the remedy (start a new
  run), never with silence. Silently ignoring "drop the price" is worse than
  refusing it: the reader believes it landed.
* Questions with a factual answer are answered from the snapshot arithmetically
  and never reach a model, because a model asked "how much money have we made"
  can be wrong and the ledger cannot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Verbs that make a sentence an order rather than a question. Matched against
# the whole text, because "why is it slow, speed it up" is still an order.
_IMPERATIVE = (
    # Japanese: plain imperative, ~te form request, and "should do" phrasing.
    "しろ", "してくれ", "してほしい", "してください", "やれ", "やって",
    "変えろ", "変えて", "止めろ", "止めて", "停止しろ", "やめろ", "やめて",
    "下げろ", "下げて", "上げろ", "上げて", "売れ", "送れ", "送って",
    "作れ", "作って", "使え", "使って", "進めろ", "進めて", "設定しろ",
    "にしろ", "に変更", "べきだ", "した方がいい", "したほうがいい",
    # English.
    "change the", "stop the", "lower the", "raise the", "switch to",
    "instead use", "you should", "make it", "set the price",
)

# A question mark alone does not make something a question: "値段下げてくれる?"
# is an order wearing a question mark. Imperative detection runs first.
_INTERROGATIVE = (
    "?", "？", "なぜ", "なんで", "どうして", "どう", "どこ", "いつ", "誰",
    "いくら", "何", "なに", "教えて", "説明",
    "why", "what", "how", "when", "where", "who", "how much", "explain",
)


class AskError(RuntimeError):
    """The question could not be answered at all."""


@dataclass(frozen=True)
class Answer:
    """What the drawer shows back.

    ``grounded_in`` names the snapshot fields the answer was computed from. It
    is not decoration: an answer nobody can trace back to a measurement is the
    kind of confident guess this whole system exists to avoid.
    """

    text: str
    grounded_in: tuple[str, ...] = ()
    refused: bool = False
    from_model: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "grounded_in": list(self.grounded_in),
            "refused": self.refused,
            "from_model": self.from_model,
        }


def is_instruction(question: str) -> bool:
    """True when the text tells the run to do something.

    Ordering matters. An imperative that ends in a question mark is still an
    imperative, so this never short-circuits on punctuation.
    """
    text = question.strip().lower()
    if not text:
        return False
    return any(marker in text for marker in _IMPERATIVE)


def looks_like_a_question(question: str) -> bool:
    text = question.strip().lower()
    return any(marker in text for marker in _INTERROGATIVE)


# --- the deterministic answers ---------------------------------------------
#
# Each entry is (trigger words, field names it reads, formatter). Kept as data
# rather than a chain of ifs so a reader can see the whole answerable surface
# at once, and so the test can assert every entry is reachable.


def _yen(value: Any) -> str:
    return f"¥{round(float(value or 0)):,}"


def _money(snapshot: dict[str, Any]) -> str:
    net = snapshot.get("verified_net_outcome_yen") or 0
    money = snapshot.get("money") or {}
    excluded = (snapshot.get("excluded_from_totals") or {}).get("test_payments") or 0
    parts = [
        f"確認できた純増は {_yen(net)} です。",
        f"元手 {_yen(money.get('starting_capital_yen'))}、"
        f"使った額 {_yen(money.get('spent_yen'))}。",
    ]
    if net == 0:
        parts.append("第三者からの入金がまだ1件も確認できていないため、0円のままです。")
    if excluded:
        parts.append(f"テスト決済 {excluded} 件は売上に数えていません。")
    return "".join(parts)


def _doing(snapshot: dict[str, Any]) -> str:
    engine = snapshot.get("engine") or {}
    if not engine.get("alive"):
        return "いま動いているものはありません。実行は停止しています。"
    action = (snapshot.get("current_action") or "").strip()
    activity = engine.get("activity") or []
    if action:
        return f"いま {action} を進めています。"
    if activity:
        return f"直近の動きは「{activity[0].get('detail', '')}」です。"
    return "実行中ですが、まだ報告できる変化がありません。"


def _stuck(snapshot: dict[str, Any]) -> str:
    bottleneck = (snapshot.get("bottleneck") or "").strip()
    human = snapshot.get("human_required") or []
    if human:
        titles = "、".join(task.get("title", "") for task in human)
        return f"あなたの操作が要る段階で止まっています：{titles}"
    if bottleneck:
        return f"詰まっているのは {bottleneck} です。"
    return "止まっている箇所は特定できていません。"


def _plan(snapshot: dict[str, Any]) -> str:
    strategy = snapshot.get("strategy") or {}
    offer = (strategy.get("offer") or "").strip()
    if not offer:
        return "売るものはまだ決まっていません。"
    lines = [f"売るのは「{offer}」"]
    if strategy.get("price_yen"):
        lines.append(f"価格は {_yen(strategy['price_yen'])}")
    reason = (strategy.get("chosen_because") or "").strip()
    if reason:
        lines.append(f"選んだ理由は {reason}")
    for rejected in strategy.get("rejected") or []:
        reasons = rejected.get("reasons") or []
        if reasons:
            lines.append(f"見送ったのは {rejected.get('name')}（{reasons[0]}）")
    return "。".join(lines) + "。"


def _stage(snapshot: dict[str, Any]) -> str:
    path = snapshot.get("journey") or {}
    stages = path.get("stages") or []
    current = next((s for s in stages if s.get("state") == "current"), None)
    position = path.get("position")
    total = path.get("total")
    if not current:
        return "進行中の工程はありません。"
    return (
        f"{total and f'{position}/{total}' or ''} 「{current.get('title')}」の段階です。"
        f"{current.get('summary', '')}"
    ).strip()


_ORACLES: tuple[tuple[tuple[str, ...], tuple[str, ...], Any], ...] = (
    (
        ("いくら", "利益", "売上", "儲", "金", "収益", "money", "revenue", "profit", "earned"),
        ("verified_net_outcome_yen", "money", "excluded_from_totals"),
        _money,
    ),
    (
        ("なにして", "何して", "今なに", "今何", "動いて", "doing", "working on", "right now"),
        ("engine", "current_action"),
        _doing,
    ),
    (
        ("止ま", "詰ま", "進まな", "遅い", "stuck", "blocked", "waiting"),
        ("bottleneck", "human_required"),
        _stuck,
    ),
    (
        ("売る", "商品", "値段", "価格", "戦略", "offer", "price", "strategy", "selling"),
        ("strategy",),
        _plan,
    ),
    (
        ("どこまで", "進捗", "段階", "工程", "progress", "stage", "how far"),
        ("journey",),
        _stage,
    ),
)


def answer_from_state(question: str, snapshot: dict[str, Any]) -> Answer | None:
    """Answer arithmetically, or return None when no oracle applies.

    First match wins. The triggers are ordered by how badly a wrong answer
    would mislead -- money first, because a hallucinated revenue figure is the
    single most damaging thing this product could say.
    """
    text = question.strip().lower()
    if not text:
        return None
    for triggers, fields, render in _ORACLES:
        if any(trigger in text for trigger in triggers):
            return Answer(text=render(snapshot), grounded_in=fields)
    return None


REFUSAL = (
    "ここは質問だけを受ける窓口です。実行中の方針は着火時に確定していて、"
    "途中で人が変えられません。変えたい場合は新しいRunを作ってください。"
)


def refusal() -> Answer:
    return Answer(text=REFUSAL, grounded_in=("spark",), refused=True)


def prepare(question: str, snapshot: dict[str, Any]) -> Answer | None:
    """Everything decidable without a model. None means: ask one.

    Returns the refusal for instructions, the oracle answer for factual
    questions, and None only for open questions that genuinely need language.
    """
    if not question.strip():
        raise AskError("質問が空です。")
    if is_instruction(question):
        return refusal()
    return answer_from_state(question, snapshot)


def grounding_prompt(snapshot: dict[str, Any]) -> str:
    """The only facts a model is allowed to answer from."""
    money = snapshot.get("money") or {}
    strategy = snapshot.get("strategy") or {}
    path = snapshot.get("journey") or {}
    engine = snapshot.get("engine") or {}
    lines = [
        f"依頼された内容: {snapshot.get('spark') or '(なし)'}",
        f"確認済み純増: {_yen(snapshot.get('verified_net_outcome_yen'))}",
        f"元手: {_yen(money.get('starting_capital_yen'))} / 使用済み: {_yen(money.get('spent_yen'))}",
        f"状態: {snapshot.get('status')}",
        f"詰まり: {snapshot.get('bottleneck') or '(なし)'}",
        f"売るもの: {strategy.get('offer') or '(未決定)'}",
        f"実行中か: {'はい' if engine.get('alive') else 'いいえ'}",
    ]
    for stage in path.get("stages") or []:
        lines.append(
            f"工程 {stage.get('title')}: {stage.get('state')} — {stage.get('summary', '')}"
        )
    for item in (engine.get("activity") or [])[:10]:
        lines.append(f"直近の動き: {item.get('detail', '')}")
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "あなたは稼働中の事業の状況を、経営者に日本語で説明する役です。"
    "与えられた事実だけを使ってください。事実にないことは"
    "「その情報は計測されていません」と答えます。推測・一般論・励ましは書きません。"
    "指示を受け付ける立場ではないので、依頼された場合も実行しません。"
    "3文以内で答えます。"
)

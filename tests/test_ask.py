"""The question drawer reads; it never steers, and it never guesses money."""

import pytest

from council import ask


SNAPSHOT = {
    "spark": "AIで昔の写真を動かす",
    "verified_net_outcome_yen": 0,
    "status": "RUNNING",
    "bottleneck": "顧客発見",
    "current_action": "見込み客の調査",
    "money": {"starting_capital_yen": 5000, "available_yen": 4200, "spent_yen": 800},
    "strategy": {
        "offer": "写真1枚を動画にする代行",
        "price_yen": 500,
        "chosen_because": "納品を1件やって証明済みだから",
        "rejected": [{"name": "月額SaaS", "reasons": ["決済基盤が要る"]}],
    },
    "human_required": [],
    "journey": {
        "position": 4,
        "total": 8,
        "stages": [
            {"id": "offer", "title": "売るものを決める", "state": "done", "summary": "決定済み"},
            {"id": "customers", "title": "客を探す", "state": "current", "summary": "22社中0社が適格"},
        ],
    },
    "engine": {"alive": True, "activity": [{"detail": "22社を検査し、適格0社"}]},
    "excluded_from_totals": {"test_payments": 2},
}


# --- it must not become a control surface -----------------------------------

@pytest.mark.parametrize("order", [
    "値段を下げろ",
    "やっぱり月額にしてくれ",
    "停止しろ",
    "この客に送って",
    "lower the price",
    "you should change the offer",
])
def test_an_instruction_is_refused(order):
    assert ask.is_instruction(order)
    reply = ask.prepare(order, SNAPSHOT)
    assert reply.refused is True
    assert "新しいRun" in reply.text


def test_an_order_wearing_a_question_mark_is_still_an_order():
    """The exact hole: punctuation must not launder a command."""
    reply = ask.prepare("値段下げてくれる？", SNAPSHOT)
    assert reply.refused is True


def test_a_refusal_names_the_remedy_rather_than_going_silent():
    """Silently dropping an order is worse than refusing it."""
    assert "新しいRun" in ask.REFUSAL
    assert ask.refusal().text == ask.REFUSAL


def test_a_real_question_is_not_mistaken_for_an_order():
    for question in ("なぜ止まってるの？", "いくら儲かった？", "how much have we made?"):
        assert ask.is_instruction(question) is False


# --- money is never left to a model ----------------------------------------

def test_money_is_answered_from_the_ledger_not_a_model():
    reply = ask.prepare("いくら儲かった？", SNAPSHOT)
    assert reply.from_model is False
    assert "¥0" in reply.text
    assert "verified_net_outcome_yen" in reply.grounded_in


def test_zero_revenue_says_why_it_is_zero():
    reply = ask.answer_from_state("売上は？", SNAPSHOT)
    assert "第三者からの入金" in reply.text


def test_test_payments_are_named_and_excluded():
    reply = ask.answer_from_state("いくら？", SNAPSHOT)
    assert "テスト決済 2 件" in reply.text
    assert "数えていません" in reply.text


def test_capital_and_spend_are_both_reported():
    reply = ask.answer_from_state("お金の状況は？", SNAPSHOT)
    assert "¥5,000" in reply.text and "¥800" in reply.text


# --- the other oracles ------------------------------------------------------

def test_what_are_you_doing_reads_the_heartbeat():
    reply = ask.answer_from_state("今なにしてるの？", SNAPSHOT)
    assert "見込み客の調査" in reply.text


def test_a_dead_engine_never_reports_activity():
    stopped = {**SNAPSHOT, "engine": {"alive": False, "activity": [{"detail": "古い動き"}]}}
    reply = ask.answer_from_state("今なにしてる？", stopped)
    assert "動いているものはありません" in reply.text
    assert "古い動き" not in reply.text


def test_stuck_prefers_the_human_task_over_the_bottleneck():
    waiting = {**SNAPSHOT, "human_required": [{"title": "本人確認", "detail": "…"}]}
    reply = ask.answer_from_state("なんで進まないの？", waiting)
    assert "本人確認" in reply.text


def test_strategy_reports_the_rejected_option_and_its_reason():
    reply = ask.answer_from_state("何を売るの？", SNAPSHOT)
    assert "写真1枚を動画にする代行" in reply.text
    assert "月額SaaS" in reply.text and "決済基盤" in reply.text


def test_progress_reports_the_current_stage_only():
    reply = ask.answer_from_state("どこまで進んだ？", SNAPSHOT)
    assert "客を探す" in reply.text
    assert "売るものを決める" not in reply.text


def test_every_oracle_is_reachable():
    """A trigger list nothing can match is dead code pretending to be a feature."""
    for triggers, _fields, _render in ask._ORACLES:
        assert ask.answer_from_state(triggers[0], SNAPSHOT) is not None


def test_an_open_question_falls_through_to_the_model():
    assert ask.prepare("この事業は筋がいいと思う？", SNAPSHOT) is None


def test_an_empty_question_is_an_error():
    with pytest.raises(ask.AskError):
        ask.prepare("   ", SNAPSHOT)


# --- the model is fenced in -------------------------------------------------

def test_the_grounding_prompt_carries_the_measured_facts():
    prompt = ask.grounding_prompt(SNAPSHOT)
    assert "¥5,000" in prompt
    assert "顧客発見" in prompt
    assert "22社を検査し、適格0社" in prompt


def test_the_grounding_prompt_leaks_no_invented_revenue():
    prompt = ask.grounding_prompt({**SNAPSHOT, "verified_net_outcome_yen": 0})
    assert "確認済み純増: ¥0" in prompt


def test_the_system_prompt_forbids_guessing_and_obeying():
    assert "計測されていません" in ask.SYSTEM_PROMPT
    assert "実行しません" in ask.SYSTEM_PROMPT

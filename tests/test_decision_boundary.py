"""The boundary is the decision, not the access.

The defect these lock down: one researched email to one prospect was gated
exactly like a blast to ten thousand people, because the old rule asked "does
this touch the outside world" instead of "is this commitment recoverable".
"""

import pytest

from council.decision_boundary import (
    RECIPIENTS_PER_ACTION,
    RECIPIENTS_PER_RUN,
    Action,
    Budget,
    authorised_by_capital,
    rule,
)


CAPITAL = Budget(remaining_yen=5_000)


# --- the default is to act --------------------------------------------------

def test_ordinary_outreach_executes_without_asking():
    """The whole point. This used to stop and ask for a grant."""
    ruling = rule(Action("send_email", "1社へ提案を送信", recipients=1), CAPITAL)
    assert ruling.verdict == "execute"
    assert ruling.needs_human is False
    assert ruling.prompt == ""


def test_reading_and_researching_never_ask():
    for kind in ("read_gmail", "read_crm", "read_stripe", "search_web", "draft_message"):
        assert rule(Action(kind, kind), CAPITAL).verdict == "execute"


def test_spending_inside_the_committed_capital_is_not_a_new_decision():
    """¥5,000 was handed over at ignition. Asking again re-litigates it."""
    ruling = rule(Action("spend", "広告テスト", yen=800), CAPITAL)
    assert ruling.verdict == "execute"
    assert "5,000" in ruling.reason


def test_spending_the_entire_committed_capital_still_executes():
    assert rule(Action("spend", "全額投下", yen=5_000), CAPITAL).verdict == "execute"


def test_a_batch_at_the_limit_executes():
    ruling = rule(Action("send", "一括送信", recipients=RECIPIENTS_PER_ACTION), CAPITAL)
    assert ruling.verdict == "execute"


# --- and the exceptions -----------------------------------------------------

def test_a_million_yen_ad_budget_is_stopped_with_the_figure_named():
    """The user's own example, verbatim."""
    ruling = rule(Action("spend", "広告予算を実行します", yen=1_000_000), CAPITAL)
    assert ruling.needs_human
    assert "¥1,000,000" in ruling.prompt
    assert "Approve" in ruling.prompt


def test_signing_a_contract_is_stopped_however_small():
    ruling = rule(Action("sign", "業務委託契約を締結", yen=0, legally_binding=True), CAPITAL)
    assert ruling.needs_human
    assert "契約" in ruling.prompt


def test_deleting_production_data_is_stopped():
    ruling = rule(Action("delete", "本番DBを削除", destroys_data=True), CAPITAL)
    assert ruling.needs_human
    assert "戻せません" in ruling.prompt


def test_a_blast_to_ten_thousand_is_stopped():
    ruling = rule(Action("send", "一斉送信", recipients=10_000), CAPITAL)
    assert ruling.needs_human
    assert "10,000" in ruling.prompt


def test_a_subscription_is_stopped_however_cheap():
    """Capital bounds a purchase. It does not bound a recurring charge."""
    ruling = rule(Action("subscribe", "SaaSに契約", yen=980, recurring=True), CAPITAL)
    assert ruling.needs_human
    assert "請求が続きます" in ruling.prompt


def test_publishing_under_the_owners_name_is_stopped():
    ruling = rule(
        Action("publish", "会社名義で記事を公開", public_under_owner_identity=True), CAPITAL
    )
    assert ruling.needs_human


# --- the holes that matter --------------------------------------------------

def test_many_small_batches_cannot_reach_ten_thousand_unnoticed():
    """A hundred sends of a hundred each never trips the per-action rule."""
    spent = Budget(remaining_yen=5_000, recipients_used=RECIPIENTS_PER_RUN)
    ruling = rule(Action("send", "続きを送信", recipients=1), spent)
    assert ruling.needs_human
    assert "累計" in ruling.prompt


def test_the_cumulative_count_is_reported_in_the_prompt():
    used = Budget(remaining_yen=5_000, recipients_used=RECIPIENTS_PER_RUN - 10)
    ruling = rule(Action("send", "送信", recipients=50), used)
    assert f"{RECIPIENTS_PER_RUN + 40:,}" in ruling.prompt


def test_zero_capital_still_permits_every_free_action():
    """¥0 narrows the strategy space; it must not stop the run."""
    broke = Budget(remaining_yen=0)
    for kind in ("read_gmail", "search_web", "draft_message", "send_email"):
        assert rule(Action(kind, kind, recipients=1), broke).verdict == "execute"


def test_zero_capital_stops_any_spend():
    ruling = rule(Action("spend", "広告", yen=1), Budget(remaining_yen=0))
    assert ruling.needs_human
    assert "¥0" in ruling.prompt


# --- the reason given is the most serious one -------------------------------

def test_a_contract_that_is_also_over_budget_is_reported_as_a_contract():
    """The reader needs the consequence that matters, not the first test to fire."""
    ruling = rule(
        Action("sign", "契約", yen=9_000_000, legally_binding=True), CAPITAL
    )
    assert "契約" in ruling.prompt
    assert "新しいお金" not in ruling.prompt


def test_destruction_outranks_a_mere_overspend():
    ruling = rule(Action("delete", "削除", yen=9_000_000, destroys_data=True), CAPITAL)
    assert "戻せません" in ruling.prompt


# --- every approval prompt is actionable ------------------------------------

STOPPED = [
    Action("spend", "広告予算", yen=1_000_000),
    Action("sign", "契約", legally_binding=True),
    Action("delete", "削除", destroys_data=True),
    Action("send", "一斉送信", recipients=10_000),
    Action("subscribe", "月額契約", yen=980, recurring=True),
    Action("publish", "公開", public_under_owner_identity=True),
]


@pytest.mark.parametrize("action", STOPPED, ids=lambda a: a.kind)
def test_every_stopped_action_names_itself_and_asks_plainly(action):
    ruling = rule(action, CAPITAL)
    assert ruling.needs_human
    assert action.summary in ruling.prompt
    assert ruling.prompt.endswith("Approve")
    assert ruling.reason


def test_an_executed_action_never_carries_a_prompt():
    """A prompt on an action nobody will be asked about is a screen bug waiting."""
    ruling = rule(Action("send_email", "送信", recipients=1), CAPITAL)
    assert ruling.prompt == ""


def test_capital_authorisation_is_separately_inspectable():
    assert authorised_by_capital(Action("spend", "x", yen=5_000), CAPITAL) is True
    assert authorised_by_capital(Action("spend", "x", yen=5_001), CAPITAL) is False

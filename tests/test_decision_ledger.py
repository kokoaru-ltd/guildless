import pytest

from council.decision_ledger import DecisionLedger, Outcome, score_outcome


FINAL_DECISION = {
    "decision": "値下げではなく業種を絞る",
    "evidence": ["接触129件に対し返信3件"],
    "assumptions": ["美容院は予約導線に課題がある"],
    "unknowns": ["決裁者が店長か本部か"],
    "experiment": {
        "hypothesis": "美容院はHP制作より予約導線改善に払う",
        "target_customer": "東京都内・口コミ50件以上・HPなしの美容院",
        "offer": "予約導線改善レポート",
        "price_yen": 30000,
        "channel": "email",
        "sample_size": 20,
        "max_budget_yen": 1000,
        "success_condition": "20社中1社以上が購入",
        "failure_condition": "20社中購入0",
        "next_review_hours": 72,
    },
}


@pytest.fixture
def ledger(tmp_path):
    return DecisionLedger(tmp_path)


def test_one_order_scores_positive():
    score, reason = score_outcome(Outcome(contacted=20, orders=1), sample_size=20)
    assert score == "positive"
    assert "1件" in reason


def test_full_sample_with_no_order_scores_negative():
    score, _ = score_outcome(Outcome(contacted=20, replied=4, orders=0), sample_size=20)
    assert score == "negative"


def test_partial_sample_is_not_yet_evidence():
    score, _ = score_outcome(Outcome(contacted=12, replied=3, orders=0), sample_size=20)
    assert score == "inconclusive"


def test_an_order_beats_an_incomplete_sample():
    score, _ = score_outcome(Outcome(contacted=3, orders=1), sample_size=20)
    assert score == "positive"


def test_recording_stamps_a_review_time_from_relative_hours(ledger):
    record = ledger.record(
        kind="experiment_design", tier="council", question="どう売るか",
        final_decision=FINAL_DECISION, proposers=["sakana", "deepseek_api"],
        judge="glm", run_id="run-1",
    )
    assert record.decision_id == "D-0001"
    assert record.experiment["next_review_at"].endswith("+00:00")
    assert record.score is None


def test_ids_increment(ledger):
    first = ledger.record(kind="k", tier="council", question="q", final_decision=FINAL_DECISION, proposers=[], judge="glm", run_id="r")
    second = ledger.record(kind="k", tier="council", question="q", final_decision=FINAL_DECISION, proposers=[], judge="glm", run_id="r")
    assert (first.decision_id, second.decision_id) == ("D-0001", "D-0002")


def test_scoring_persists_and_attributes_to_every_model(ledger):
    record = ledger.record(
        kind="experiment_design", tier="council", question="どう売るか",
        final_decision=FINAL_DECISION, proposers=["sakana", "deepseek_api"],
        judge="glm", run_id="run-1",
    )
    ledger.score(record.decision_id, Outcome(contacted=20, replied=4, meetings=2, orders=0))

    reloaded = ledger.get(record.decision_id)
    assert reloaded.score == "negative"
    assert reloaded.outcome["meetings"] == 2
    assert reloaded.scored_at is not None

    accuracy = ledger.provider_accuracy()
    assert accuracy["sakana"]["negative"] == 1
    assert accuracy["glm"]["negative"] == 1


def test_unscored_decisions_are_absent_from_accuracy(ledger):
    ledger.record(kind="k", tier="council", question="q", final_decision=FINAL_DECISION, proposers=["sakana"], judge="glm", run_id="r")
    assert ledger.provider_accuracy() == {}


def test_scoring_an_unknown_decision_raises(ledger):
    with pytest.raises(KeyError):
        ledger.score("D-9999", Outcome())

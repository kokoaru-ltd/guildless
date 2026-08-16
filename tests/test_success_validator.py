from council.success_validator import (
    at_least,
    business_level,
    validate_deliberation,
)


GOOD_EXPERIMENT = {
    "hypothesis": "既存反応者は3000円のリライトパックを買う",
    "target_customer": "過去に返信した小規模事業主4件",
    "offer": "ファーストビュー改善パック",
    "price_yen": 3000,
    "channel": "dm",
    "sample_size": 4,
    "max_budget_yen": 5000,
    "success_condition": "4件中1件が前払い",
    "failure_condition": "4件中前払い0件",
    "next_review_hours": 168,
}


def _decision(**overrides):
    base = {
        "decision": "既存反応者に絞って3000円で売る",
        "evidence": ["接触129件・返信3件・成約0件"],
        "experiment": GOOD_EXPERIMENT,
    }
    base.update(overrides)
    return base


# --- deliberation ladder ---------------------------------------------------

def test_no_decision_is_never_success():
    verdict = validate_deliberation(None, require_experiment=False)
    assert verdict.level == "none" and verdict.ok is False


def test_empty_decision_text_is_not_success():
    verdict = validate_deliberation(_decision(decision="   "), require_experiment=False)
    assert verdict.ok is False


def test_prose_without_evidence_fails_a_money_question():
    verdict = validate_deliberation(
        {"decision": "業種を絞るべきである", "evidence": [], "experiment": None},
        require_experiment=True,
    )
    assert verdict.level == "text_only" and verdict.ok is False


def test_evidence_without_experiment_fails_a_money_question():
    verdict = validate_deliberation(_decision(experiment=None), require_experiment=True)
    assert verdict.level == "structured" and verdict.ok is False
    assert "実行できる実験" in verdict.reason


def test_evidence_without_experiment_passes_a_non_money_question():
    verdict = validate_deliberation(_decision(experiment=None), require_experiment=False)
    assert verdict.ok is True


def test_incomplete_experiment_is_not_executable():
    broken = {**GOOD_EXPERIMENT, "success_condition": "", "sample_size": 0}
    verdict = validate_deliberation(_decision(experiment=broken), require_experiment=True)
    assert verdict.ok is False
    assert "success_condition" in verdict.reason


def test_evidence_plus_complete_experiment_is_executable():
    verdict = validate_deliberation(_decision(), require_experiment=True)
    assert verdict.level == "executable" and verdict.ok is True


# --- business ladder -------------------------------------------------------

def test_generating_text_is_not_a_business_success():
    verdict = business_level(text_produced=True)
    assert verdict.level == "text" and verdict.ok is False


def test_sending_is_not_success():
    assert business_level(sent=20).ok is False


def test_a_booked_meeting_is_still_not_success():
    verdict = business_level(sent=20, delivered=18, replied=4, meetings=2)
    assert verdict.level == "meeting" and verdict.ok is False


def test_payment_that_lost_money_is_not_success():
    verdict = business_level(sent=20, replied=4, meetings=2, payments=1, revenue_yen=3000, cost_yen=5000)
    assert verdict.level == "payment" and verdict.ok is False
    assert "赤字" in verdict.reason


def test_only_profit_is_success():
    verdict = business_level(sent=20, replied=4, meetings=2, payments=1, revenue_yen=30000, cost_yen=1200)
    assert verdict.level == "profit" and verdict.ok is True
    assert "28,800" in verdict.reason


def test_breaking_even_is_not_profit():
    verdict = business_level(payments=1, revenue_yen=5000, cost_yen=5000)
    assert verdict.ok is False


def test_nothing_happened_is_the_floor():
    assert business_level().level == "none"


def test_ladder_ordering():
    assert at_least("meeting", "replied") is True
    assert at_least("sent", "replied") is False
    assert at_least("payment", "payment") is True
    assert at_least("profit", "payment") is True
    assert at_least("payment", "profit") is False

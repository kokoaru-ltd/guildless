from council.decision_router import COUNCIL_SPEND_THRESHOLD_YEN, route


def test_routine_reply_never_convenes_the_council():
    routing = route("scheduling_reply")
    assert routing.tier == "cheap"
    assert routing.providers == ("glm",)


def test_pure_computation_calls_no_model():
    routing = route("budget_check")
    assert routing.tier == "machine"
    assert routing.providers == ()


def test_sales_copy_uses_one_strong_model():
    routing = route("sales_copy")
    assert routing.tier == "strong"
    assert routing.providers == ("sakana",)


def test_price_change_convenes_the_council():
    routing = route("price_change")
    assert routing.tier == "council"
    assert routing.mode == "real"
    assert {"sakana", "deepseek_api", "gemini", "glm"} <= set(routing.providers)


def test_large_spend_escalates_a_routine_kind():
    routing = route("scheduling_reply", amount_yen=COUNCIL_SPEND_THRESHOLD_YEN)
    assert routing.tier == "council"
    assert str(COUNCIL_SPEND_THRESHOLD_YEN) in routing.reason.replace(",", "")


def test_spend_below_the_threshold_does_not_escalate():
    routing = route("scheduling_reply", amount_yen=COUNCIL_SPEND_THRESHOLD_YEN - 1)
    assert routing.tier == "cheap"


def test_irreversible_decisions_escalate():
    routing = route("summarize", reversible=False)
    assert routing.tier == "council"


def test_external_effect_lifts_cheap_to_strong_but_not_to_council():
    routing = route("scheduling_reply", external_effect=True)
    assert routing.tier == "strong"


def test_unknown_kind_defaults_to_strong_not_council():
    routing = route("something_new")
    assert routing.tier == "strong"

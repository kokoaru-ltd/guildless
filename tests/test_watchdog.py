from council.watchdog import Thresholds, check, should_stop


def action(status="executed", kind="send_email", target="a@example.com", key=None):
    return {
        "status": status, "kind": kind, "target": target,
        "idempotency_key": key or f"{kind}:{target}:{status}",
    }


HEALTHY_CAPITAL = {
    "envelopes": {
        "ai_api": {"allocated_yen": 1000, "spent_yen": 100},
        "experiment": {"allocated_yen": 2000, "available_yen": 1500},
    }
}


def codes(alarms):
    return {alarm.code for alarm in alarms}


def test_a_healthy_company_raises_nothing():
    alarms = check(actions=[action()], capital_summary=HEALTHY_CAPITAL)
    assert alarms == []
    assert should_stop(alarms) is False


def test_no_activity_at_all_is_not_an_alarm():
    assert check(actions=[], capital_summary=HEALTHY_CAPITAL) == []


def test_the_same_action_failing_repeatedly_stops_the_company():
    alarms = check(
        actions=[action("failed") for _ in range(3)], capital_summary=HEALTHY_CAPITAL
    )
    assert "repeated_failure" in codes(alarms)
    assert should_stop(alarms) is True


def test_two_failures_are_not_yet_a_meltdown():
    alarms = check(
        actions=[action("failed") for _ in range(2)], capital_summary=HEALTHY_CAPITAL
    )
    assert "repeated_failure" not in codes(alarms)


def test_a_run_of_failures_reads_as_an_outage():
    actions = [action("failed", target=f"t{i}@example.com") for i in range(3)]
    assert "provider_error_streak" in codes(
        check(actions=actions, capital_summary=HEALTHY_CAPITAL)
    )


def test_a_recent_success_clears_the_outage_streak():
    actions = [action("failed", target=f"t{i}@example.com") for i in range(3)]
    actions.append(action("executed", target="ok@example.com"))
    assert "provider_error_streak" not in codes(
        check(actions=actions, capital_summary=HEALTHY_CAPITAL)
    )


def test_one_key_executed_twice_is_a_double_send():
    actions = [action(key="same"), action(key="same")]
    alarms = check(actions=actions, capital_summary=HEALTHY_CAPITAL)
    assert "duplicate_effect" in codes(alarms)
    assert should_stop(alarms) is True


def test_burning_inference_budget_without_contacting_anyone_stops_the_company():
    capital = {
        "envelopes": {
            "ai_api": {"allocated_yen": 1000, "spent_yen": 600},
            "experiment": {"allocated_yen": 2000, "available_yen": 2000},
        }
    }
    alarms = check(actions=[action("denied")], capital_summary=capital)
    assert "spend_without_contact" in codes(alarms)


def test_inference_spend_is_fine_once_someone_was_contacted():
    capital = {
        "envelopes": {
            "ai_api": {"allocated_yen": 1000, "spent_yen": 900},
            "experiment": {"allocated_yen": 2000, "available_yen": 2000},
        }
    }
    assert "spend_without_contact" not in codes(
        check(actions=[action("executed")], capital_summary=capital)
    )


def test_many_attempts_reaching_nobody_is_an_alarm():
    actions = [action("denied", target=f"t{i}@example.com") for i in range(10)]
    assert "attempts_without_effect" in codes(
        check(actions=actions, capital_summary=HEALTHY_CAPITAL)
    )


def test_execution_without_a_recorded_outcome_is_flagged_but_not_fatal():
    alarms = check(
        actions=[action()], capital_summary=HEALTHY_CAPITAL, outcome_updated=False
    )
    assert "silent_success" in codes(alarms)
    assert should_stop(alarms) is False


def test_an_exhausted_experiment_budget_stops_new_experiments():
    capital = {
        "envelopes": {
            "ai_api": {"allocated_yen": 1000, "spent_yen": 10},
            "experiment": {"allocated_yen": 2000, "available_yen": 0},
        }
    }
    alarms = check(actions=[action()], capital_summary=capital)
    assert "budget_exhausted" in codes(alarms)
    assert should_stop(alarms) is True


def test_thresholds_can_be_tightened():
    alarms = check(
        actions=[action("failed"), action("failed")],
        capital_summary=HEALTHY_CAPITAL,
        thresholds=Thresholds(repeated_failure=2),
    )
    assert "repeated_failure" in codes(alarms)

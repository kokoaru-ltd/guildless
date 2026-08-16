import pytest

from council.action_gateway import ActionGateway
from council.capital import CapitalAllocator
from council.compliance import RULES, usable_channels
from council.goal_run import Goal, GoalRun
from council.proof import Measurements
from council.revenue_loop import Offer
from council.strategy_factory import Prospect, StrategyFactory


FULL = {"sender_identity", "opt_out_link", "spf_dkim_dmarc",
        "public_company_addresses", "form_submission"}

SOLD = Measurements(
    contacted=20, replied=5, interested=3, payments=1, delivered=1,
    revenue_yen=59_800, direct_cost_yen=3_300, delivery_proof_passed=True,
)
UNSOLD = Measurements(contacted=20, replied=2, payments=0, delivery_proof_passed=True)


def offer(name="バックログ納品", offer_id="o1"):
    return Offer(offer_id, name, 59_800, 3_300, 24, "low", True)


@pytest.fixture
def gateway(tmp_path):
    capital = CapitalAllocator(tmp_path / "c.json", initial_cash_yen=5_000)
    return ActionGateway(tmp_path / "a.json", capital, dry_run=False)


def factory(gateway, **overrides):
    base = dict(
        generate_offers=lambda: [offer()],
        prove_delivery=lambda o: (True, "納品可能"),
        find_prospects=lambda o, c, n: [Prospect(f"社{i}", f"c{i}@example.jp", "適合") for i in range(n)],
        gateway=gateway,
        compose_message=lambda o, p: {"subject": o.name, "to": p.contact},
        measure=lambda o: SOLD,
        capabilities=lambda: set(FULL),
        send=lambda request: {"delivered": True},
    )
    base.update(overrides)
    return StrategyFactory(**base)


# --- compliance -------------------------------------------------------------

def test_sns_dm_and_phone_and_ads_are_never_offered():
    channels = {c.channel for c in usable_channels(FULL | {"marketplace_account"})}
    assert "sns_dm" not in channels
    assert "phone" not in channels
    assert "ads" not in channels


def test_contact_form_is_preferred_because_it_costs_nothing():
    assert usable_channels(FULL)[0].channel == "contact_form"


def test_cold_email_disappears_when_authentication_is_missing():
    without = FULL - {"spf_dkim_dmarc"}
    assert "email_cold" not in {c.channel for c in usable_channels(without)}


def test_a_company_with_no_capabilities_has_no_channels():
    assert usable_channels(set()) == []


def test_every_conditional_channel_states_its_conditions():
    for rule in RULES.values():
        if rule.verdict == "conditional":
            assert rule.conditions


# --- strategy assembly ------------------------------------------------------

def test_no_lawful_channel_yields_no_strategies_rather_than_a_question(gateway):
    assert factory(gateway, capabilities=set)() == []


def test_offers_failing_the_criteria_are_dropped_with_reasons(gateway):
    cheap = Offer("o2", "500円テンプレ", 500, 100, 2, "low", True)
    built = factory(gateway, generate_offers=lambda: [cheap])()
    assert built == []


def test_a_viable_offer_becomes_an_executable_strategy(gateway):
    strategies = factory(gateway)()
    assert len(strategies) == 1
    assert "contact_form" in strategies[0].name


# --- running end to end -----------------------------------------------------

def test_a_sellable_offer_runs_through_to_profit(gateway):
    run = GoalRun(Goal(), factory(gateway))
    outcome = run.run()
    assert outcome.state == "succeeded"
    assert outcome.net_yen == 56_500
    assert outcome.human_task is None


def test_an_unbuildable_offer_is_dropped_without_contacting_anyone(gateway):
    calls = {"prospects": 0}

    def counting(o, c, n):
        calls["prospects"] += 1
        return []

    built = factory(
        gateway,
        prove_delivery=lambda o: (False, "10本中0本しか納品品質に届かない"),
        find_prospects=counting,
    )
    outcome = GoalRun(Goal(), built).run()
    assert outcome.state == "failed"
    assert outcome.human_task is None
    assert calls["prospects"] == 0
    assert gateway.executed_count() == 0


def test_dry_run_stops_every_send_without_asking_anyone(tmp_path):
    capital = CapitalAllocator(tmp_path / "c.json", initial_cash_yen=5_000)
    guarded = ActionGateway(tmp_path / "a.json", capital)  # dry_run defaults on
    outcome = GoalRun(Goal(), factory(guarded)).run()
    assert outcome.state == "failed"
    assert outcome.human_task is None
    assert guarded.executed_count() == 0


def test_a_company_with_no_sender_contacts_nobody(gateway):
    """Full wiring is not enough; a sender has to be supplied deliberately."""
    outcome = GoalRun(Goal(), factory(gateway, send=None)).run()
    assert outcome.state == "failed"
    assert outcome.human_task is None
    assert gateway.executed_count() == 0


def test_an_unsold_offer_ends_the_strategy_not_the_goal(gateway):
    batches = [factory(gateway)(), factory(gateway, measure=lambda o: SOLD)()]
    calls = {"n": 0}

    def strategies():
        calls["n"] += 1
        if calls["n"] == 1:
            return factory(gateway, measure=lambda o: UNSOLD)()
        if calls["n"] == 2:
            return factory(gateway, generate_offers=lambda: [offer(offer_id="o9")])()
        return []

    outcome = GoalRun(Goal(), strategies).run()
    assert outcome.state == "succeeded"


def test_outreach_respects_the_per_target_contact_limit(gateway):
    gateway.max_per_target = 1
    same = [Prospect("同じ社", "one@example.jp", "適合")] * 3
    built = factory(gateway, find_prospects=lambda o, c, n: same)
    GoalRun(Goal(), built).run()
    assert gateway.executed_count() == 1

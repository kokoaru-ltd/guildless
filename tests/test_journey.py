"""The path a person follows, not the steps a program runs."""

import pytest

from council.journey import STAGE_ORDER, TITLES, build


def facts(**overrides):
    base = dict(spark="AIで昔の写真を動かせたら面白そう")
    base.update(overrides)
    return base


def stage(journey, stage_id):
    return next(s for s in journey.stages if s.id == stage_id)


# --- exactly one current position ------------------------------------------

def test_there_is_always_exactly_one_current_stage():
    for extra in (
        {},
        {"offer_name": "A"},
        {"offer_name": "A", "delivery_proof_passed": True},
        {"offer_name": "A", "delivery_proof_passed": True, "prospects_eligible": 3},
        {"real_payments": 1},
    ):
        journey = build(facts(**extra))
        assert sum(1 for s in journey.stages if s.state == "current") == 1


def test_an_empty_spark_starts_at_the_beginning():
    journey = build({})
    assert journey.stages[0].state == "current"
    assert journey.position == 1


def test_the_journey_is_eight_business_stages():
    journey = build(facts())
    assert [s.id for s in journey.stages] == list(STAGE_ORDER)
    assert journey.as_dict()["total"] == 8


@pytest.mark.parametrize("stage_id", STAGE_ORDER)
def test_every_stage_is_named_in_three_languages(stage_id):
    assert set(TITLES[stage_id]) >= {"ja", "en", "zh"}


# --- internal step names never leak ----------------------------------------

@pytest.mark.parametrize("internal", ["observe", "diagnose", "classify", "readiness"])
def test_the_workers_own_step_names_are_absent(internal):
    text = str(build(facts(prospects_inspected=22)).as_dict())
    assert internal not in text


@pytest.mark.parametrize("jargon", ["DISCOVERY_FAILURE", "SAFETY_FAILURE", "CHANNEL_FAILURE"])
def test_the_failure_taxonomy_stays_behind_the_screen(jargon):
    journey = build(facts(
        delivery_proof_passed=True, prospects_inspected=22, prospects_eligible=0,
        prospect_exclusions={"Error": 11, "purpose_restricted": 4},
    ))
    assert jargon not in str(journey.as_dict())


# --- the failing stage explains itself in plain words ----------------------

def test_the_customer_stage_says_what_was_abandoned_and_why():
    journey = build(facts(
        offer_name="バックログ納品", delivery_proof_passed=True,
        prospects_inspected=22, prospects_eligible=0,
        prospect_exclusions={"Error": 11, "purpose_restricted": 4, "no_form": 2},
    ))
    customers = stage(journey, "customers")
    assert customers.state == "current"
    assert "22社" in customers.summary
    assert "企業URLの推測に失敗" in customers.decided
    assert "廃止" in customers.decided
    assert customers.next_up


def test_exclusion_counts_are_translated_for_a_reader():
    journey = build(facts(
        delivery_proof_passed=True, prospects_inspected=6,
        prospect_exclusions={"purpose_restricted": 4, "recaptcha,generic_captcha": 2},
    ))
    did = stage(journey, "customers").did
    assert "営業用途で使えない" in did
    assert "自動化を拒否する仕組み" in did


def test_finding_customers_completes_the_stage():
    journey = build(facts(
        offer_name="A", delivery_proof_passed=True,
        prospects_inspected=40, prospects_eligible=5,
    ))
    customers = stage(journey, "customers")
    assert customers.state == "done"
    assert "5社" in customers.summary


# --- progress reflects results, not activity -------------------------------

def test_a_stage_completes_only_when_its_result_exists():
    """A step having run is not the same as a result existing."""
    journey = build(facts(offer_name="A", delivery_proof_passed=False))
    assert stage(journey, "offer").state == "current"
    assert stage(journey, "customers").state == "pending"


def test_payment_is_the_last_stage_and_needs_real_money():
    unpaid = build(facts(offer_name="A", delivery_proof_passed=True, prospects_eligible=3))
    assert stage(unpaid, "payment").state == "pending"

    paid = build(facts(real_payments=1))
    assert stage(paid, "payment").state == "done"


def test_contact_waits_for_permission_rather_than_claiming_progress():
    journey = build(facts(
        offer_name="A", delivery_proof_passed=True, prospects_eligible=3,
        external_action_grant="未付与",
    ))
    contact = stage(journey, "contact")
    assert contact.state != "done"
    assert "許可" in contact.summary


def test_each_stage_explains_what_happens_next():
    journey = build(facts(offer_name="A", delivery_proof_passed=True))
    for item in journey.stages[:5]:
        assert item.next_up, f"{item.id} has no next step"

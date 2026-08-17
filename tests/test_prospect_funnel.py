"""Why a prospect was lost, and the ban on inventing URLs."""

import json

import pytest

from council.prospect_funnel import (
    EVIDENCE_SOURCES,
    Funnel,
    Prospect,
    ProspectError,
    classify,
    from_inspection,
)


# --- URLs must be observed, never constructed ------------------------------

@pytest.mark.parametrize("source", sorted(EVIDENCE_SOURCES))
def test_prospect_url_must_come_from_observed_evidence(source):
    prospect = Prospect(company="株式会社A", url="https://a.example", source=source)
    assert prospect.source in EVIDENCE_SOURCES


@pytest.mark.parametrize(
    "source", ["guessed", "inferred_from_name", "model_memory", "assumed", ""]
)
def test_a_domain_is_never_invented_from_a_company_name(source):
    with pytest.raises(ProspectError, match="観測されたリンク"):
        Prospect(company="株式会社A", url="https://a.co.jp", source=source)


# --- the five failure kinds -------------------------------------------------

@pytest.mark.parametrize(
    "reason,expected",
    [
        ("guessed_url", "DISCOVERY_FAILURE"),
        ("Error", "DISCOVERY_FAILURE"),
        ("unreachable", "REACHABILITY_FAILURE"),
        ("unreadable", "REACHABILITY_FAILURE"),
        ("no_form", "CHANNEL_FAILURE"),
        ("login_required", "CHANNEL_FAILURE"),
        ("not_relevant", "FIT_FAILURE"),
        ("sales_prohibited", "SAFETY_FAILURE"),
        ("purpose_restricted", "SAFETY_FAILURE"),
        ("recaptcha,generic_captcha", "SAFETY_FAILURE"),
    ],
)
def test_each_reason_names_what_to_change(reason, expected):
    assert classify(reason) == expected


def test_an_unknown_reason_is_not_treated_as_a_discovery_problem():
    """Discovery is the one that invites 'find more companies', which is the
    expensive wrong answer."""
    assert classify("something_new") != "DISCOVERY_FAILURE"


# --- the real 22 --------------------------------------------------------------

def test_the_recorded_inspection_points_at_the_primitive_not_the_market():
    rows = (
        [{"status": "skip", "reason": "Error"}] * 11
        + [{"status": "skip", "reason": "purpose_restricted"}] * 4
        + [{"status": "blocked", "reason": "recaptcha,generic_captcha"}] * 2
        + [{"status": "blocked", "reason": "generic_captcha"}] * 2
        + [{"status": "skip", "reason": "no_form"}] * 2
        + [{"status": "skip", "reason": "unreadable"}]
    )
    funnel = from_inspection(rows)

    assert funnel.discovered == 22
    assert funnel.qualified == 0
    # Eleven guessed URLs dominate, so the fix is a reliable way to find real
    # companies -- not more companies to guess at.
    assert funnel.dominant_failure == "DISCOVERY_FAILURE"
    assert "発見手段" in funnel.next_move()


def test_reachability_is_counted_separately_from_qualification():
    rows = [
        {"status": "skip", "reason": "purpose_restricted"},
        {"status": "skip", "reason": "Error"},
        {"status": "eligible"},
    ]
    funnel = from_inspection(rows)
    assert funnel.qualified == 1
    # The safety-blocked company was reached; the guessed one never existed.
    assert funnel.reachable == 2


def test_a_channel_that_cannot_be_used_kills_the_channel_not_the_market():
    funnel = Funnel(discovered=50, qualified=50)
    for _ in range(40):
        funnel.lose("purpose_restricted")
    assert funnel.dominant_failure == "SAFETY_FAILURE"
    assert "チャネルを外す" in funnel.next_move()


def test_wrong_audience_points_at_the_offer():
    funnel = Funnel(discovered=30)
    for _ in range(25):
        funnel.lose("not_relevant")
    assert "顧客層か商品" in funnel.next_move()


# --- the funnel separates who from how -------------------------------------

def test_the_funnel_reports_each_stage():
    funnel = Funnel(
        discovered=143, qualified=51, reachable=37,
        legally_contactable=12, send_ready=4, sent=0, paid=0,
    )
    report = funnel.as_dict()
    assert report["discovered"] == 143
    assert report["legally_contactable"] == 12
    assert report["sent"] == 0
    assert report["paid"] == 0


def test_no_losses_yet_is_not_a_diagnosis():
    assert Funnel().dominant_failure is None
    assert "まだ" in Funnel().next_move()


def test_the_real_recorded_file_can_be_read(tmp_path):
    path = tmp_path / "prospect_inspection.json"
    path.write_text(json.dumps([
        {"company": "A", "status": "skip", "reason": "Error"},
        {"company": "B", "status": "eligible"},
    ]), encoding="utf-8")
    funnel = from_inspection(json.loads(path.read_text(encoding="utf-8")))
    assert funnel.discovered == 2 and funnel.qualified == 1

import pytest

from council.agent_router import DOMAIN_ORACLES, AgentRouter, Record


AVAILABLE = ["gemini", "codex", "deepseek_api", "glm", "sakana", "qwen_vl", "qwen_coder", "qwen3"]


@pytest.fixture
def router(tmp_path):
    return AgentRouter(tmp_path / "router.json")


# --- leads come from track record, not equality ----------------------------

def test_coding_leads_with_the_strongest_coder(router):
    assert router.assign("coding", AVAILABLE).lead == "codex"


def test_visual_leads_with_the_vision_model(router):
    assert router.assign("visual", AVAILABLE).lead == "qwen_vl"


def test_a_weak_seat_loses_the_lead_once_it_misses_things(router):
    """Sakana returned frontend at 0.62; measurements decide whether it leads."""
    for _ in range(4):
        router.record_finding("sakana", "frontend", "false_positive")
    for _ in range(3):
        router.record_finding("qwen_coder", "frontend", "bug_found")
    assert router.assign("frontend", ["sakana", "qwen_coder"]).lead == "qwen_coder"


def test_finding_a_real_bug_outweighs_agreeing_a_lot(router):
    for _ in range(5):
        router.record_finding("glm", "backend", "accepted")
    router.record_finding("deepseek_api", "backend", "bug_found")
    router.record_finding("deepseek_api", "backend", "regression_prevented")
    assert router.score("deepseek_api", "backend") > router.score("glm", "backend")


def test_false_positives_cost_more_than_agreement_earns(router):
    router.record_finding("glm", "ux", "accepted")
    router.record_finding("glm", "ux", "false_positive")
    assert router.score("glm", "ux") < 0


# --- the challenger must be able to fail differently -----------------------

def test_the_challenger_comes_from_a_different_lineage(router):
    assignment = router.assign("coding", ["codex", "qwen_coder", "qwen3"])
    assert assignment.lead == "codex"
    assert assignment.challenger.startswith("qwen")


def test_two_agents_of_one_family_do_not_check_each_other(router):
    assignment = router.assign("visual", ["qwen_vl", "qwen_coder", "gemini"])
    assert assignment.lead == "qwen_vl"
    assert assignment.challenger == "gemini"


# --- weight decides how many seats, never how many votes -------------------

def test_a_normal_decision_gets_no_prosecutor(router):
    assert router.assign("ux", AVAILABLE).prosecutor == ""


def test_a_major_decision_adds_a_third_lineage(router):
    assignment = router.assign("backend", AVAILABLE, weight="major")
    assert assignment.prosecutor
    assert len({assignment.lead, assignment.challenger, assignment.prosecutor}) == 3


def test_an_irreversible_decision_requires_a_deterministic_check(router):
    assignment = router.assign("product", AVAILABLE, weight="irreversible")
    assert assignment.oracle


# --- where a machine decides, it is named ----------------------------------

@pytest.mark.parametrize("domain", sorted(DOMAIN_ORACLES))
def test_domains_with_an_oracle_always_name_it(domain, router):
    assert router.assign(domain, AVAILABLE).oracle == DOMAIN_ORACLES[domain]


def test_the_outcome_oracle_is_the_ledger(router):
    assert "ledger" in router.assign("outcome", AVAILABLE).oracle


def test_there_is_no_vote_counting_api():
    assert not any(
        name for name in dir(AgentRouter)
        if "vote" in name.lower() or "majority" in name.lower()
    )


# --- scores persist and stay honest ----------------------------------------

def test_scores_survive_a_restart(tmp_path):
    path = tmp_path / "router.json"
    first = AgentRouter(path)
    first.record_finding("gemini", "ux", "bug_found")
    assert AgentRouter(path).score("gemini", "ux") == first.score("gemini", "ux")


def test_a_seed_is_not_mistaken_for_a_result(router):
    """Seeds are priors and must be visibly thin evidence."""
    seeded = router.records["codex"]["coding"]
    assert seeded.evidence_count <= 3


def test_false_positive_rate_is_reported():
    record = Record(accepted_findings=3, false_positives=1)
    assert record.false_positive_rate == 0.25


def test_implementation_pass_rate_is_reported(router):
    router.record_implementation("codex", "frontend", passed=True)
    router.record_implementation("codex", "frontend", passed=False)
    assert router.records["codex"]["frontend"].implementation_pass_rate == 0.5


def test_an_unknown_outcome_is_refused(router):
    with pytest.raises(ValueError):
        router.record_finding("gemini", "ux", "sounded_good")


def test_no_available_agents_is_an_error(router):
    with pytest.raises(ValueError):
        router.assign("ux", [])

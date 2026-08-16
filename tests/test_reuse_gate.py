import pytest

from council.failure_ledger import BY_ID, LEDGER, Proposal, compile_feedback, match
from council.reuse_gate import Candidate, FailureCritic, ReuseGate, ReuseScout


def gate(candidates=None):
    return ReuseGate(ReuseScout(lambda summary: list(candidates or [])))


BROWSER_USE = Candidate(
    "browser-use", "github", fit=0.85, license="MIT",
    reason="Python製のブラウザAgentでフォーム入力を用途に挙げている",
)
STAGEHAND = Candidate(
    "Stagehand", "github", fit=0.75, license="MIT",
    reason="決定論的コードとAIを分離でき、self-healingとキャッシュを持つ",
)


# --- the regression this whole module exists for ---------------------------

def test_a_custom_browser_executor_is_rejected_before_any_code_is_written():
    """The exact mistake made in this project, now blocked at the proposal."""
    proposal = Proposal(
        summary="問い合わせフォーム用のブラウザExecutorをPlaywrightで実装する",
        creates_new_primitive=True,
    )
    result = gate([BROWSER_USE, STAGEHAND]).decide(proposal)

    assert result.allowed is False
    assert result.resolution == "wrap_existing"
    assert "browser-use" in result.reason
    # And it searched without being told to.
    assert proposal.reuse_search_completed is True
    assert proposal.candidates_evaluated == 2


def test_building_without_searching_is_refused():
    proposal = Proposal(summary="新しいExecutorを実装する", creates_new_primitive=True)
    result = gate([]).decide(proposal)
    assert result.allowed is False


def test_the_best_fitting_candidate_is_the_one_chosen():
    proposal = Proposal(summary="ブラウザ操作基盤を自作する", creates_new_primitive=True)
    result = gate([STAGEHAND, BROWSER_USE]).decide(proposal)
    assert "browser-use" in result.reason


def test_a_weak_candidate_does_not_block_building():
    weak = Candidate("half-baked", "github", fit=0.3, rejected_because="フォーム入力に非対応")
    proposal = Proposal(summary="Executorを実装する", creates_new_primitive=True)
    result = gate([weak]).decide(proposal)
    assert result.allowed is True
    assert result.resolution == "build_new"
    assert "1件を評価" in result.reason


def test_building_needs_recorded_rejection_reasons():
    unexplained = Candidate("something", "github", fit=0.2)
    proposal = Proposal(summary="Executorを実装する", creates_new_primitive=True)
    result = gate([unexplained]).decide(proposal)
    assert result.allowed is False
    # Refused via F005, which names the missing evidence rather than a generic
    # complaint. Either refusal is correct; this one says what is missing.
    assert "rejection_reasons" in result.reason


def test_work_that_creates_nothing_new_passes_straight_through():
    proposal = Proposal(summary="既存のFormInspectorの閾値を調整する")
    assert gate().decide(proposal).allowed is True


# --- asking the human is refused, not negotiated ---------------------------

def test_a_proposal_that_asks_the_human_mid_task_is_rejected():
    proposal = Proposal(
        summary="法務を確認しますか？", asks_human_intermediate_question=True
    )
    result = gate().decide(proposal)
    assert result.allowed is False
    assert "自分で決めて" in result.reason


def test_asking_language_alone_is_enough_to_match_f001():
    matches = match(Proposal(summary="このまま続けますか"))
    assert any(m.pattern.id == "F001" for m in matches)


# --- the recorded failures --------------------------------------------------

def test_every_failure_from_this_project_is_in_the_ledger():
    patterns = {p.pattern for p in LEDGER}
    assert {
        "intermediate_human_question",
        "premature_infrastructure",
        "capability_fixation",
        "human_discovered_missing_tool",
        "reinvent_existing_software_without_search",
        "pleasant_fake_success",
    } <= patterns


def test_payment_work_before_delivery_proof_is_flagged():
    matches = match(Proposal(summary="Stripe連携を先に進める"))
    assert any(m.pattern.id == "F002" for m in matches)


def test_payment_work_passes_once_delivery_is_proven():
    proposal = Proposal(summary="Stripe連携を進める", evidence={"delivery_proof_passed"})
    assert all(not m.blocking for m in match(proposal))


def test_a_capability_gap_must_trigger_a_search():
    matches = match(Proposal(summary="現在の能力が足りない"))
    f004 = next(m for m in matches if m.pattern.id == "F004")
    assert "reuse_search" in f004.unmet


def test_claiming_success_requires_verifying_the_outcome():
    matches = match(Proposal(summary="送信が完了しました"))
    f006 = next(m for m in matches if m.pattern.id == "F006")
    assert "outcome_verified" in f006.unmet


def test_evidence_clears_a_matched_pattern():
    proposal = Proposal(summary="送信が完了しました", evidence={"outcome_verified"})
    assert all(not m.blocking for m in match(proposal))


# --- feedback becomes a permanent check -------------------------------------

def test_human_feedback_compiles_into_a_blocking_pattern():
    pattern = compile_feedback(
        pattern="ignored_existing_agent_framework",
        example="既存Agent基盤を調べずSDKを自作した",
        rule="evaluate_existing_frameworks_first",
        triggers=("sdk", "agent基盤"),
    )
    assert pattern.id.startswith("F")
    assert pattern.requires == ("explicit_resolution",)


def test_the_critic_runs_before_anything_is_built():
    seen: list[str] = []

    class Watching(FailureCritic):
        def review(self, proposal):
            seen.append("critic")
            return super().review(proposal)

    def searching(summary):
        seen.append("scout")
        return [BROWSER_USE]

    ReuseGate(ReuseScout(searching), Watching()).decide(
        Proposal(summary="Executorを実装する", creates_new_primitive=True)
    )
    assert seen[0] == "critic"


@pytest.mark.parametrize("failure_id", [p.id for p in LEDGER])
def test_every_pattern_states_how_to_clear_it(failure_id):
    pattern = BY_ID[failure_id]
    assert pattern.triggers
    assert pattern.requires
    assert pattern.rule

"""The ten ways an agent could reach the outside world without permission."""

import pytest

from council.executors.restricted_adapter import (
    FORBIDDEN_ACTIONS,
    AdapterError,
    AgentReport,
    Element,
    RestrictedBrowserAdapter,
    build_session,
)
from council.executors.safety_kernel import (
    CapabilityError,
    EvidenceCollector,
    SubmissionVerifier,
    issue_capability,
)


ORIGIN = "https://example.co.jp"
FORM_URL = f"{ORIGIN}/contact"
ALLOWED = frozenset({ORIGIN})


class Driver:
    """Records what actually reached the browser."""

    def __init__(self):
        self.actions: list[tuple[str, Any]] = []

    def navigate(self, url):
        self.actions.append(("navigate", url))

    def input(self, element, value):
        self.actions.append(("input", element))

    def select(self, element, value):
        self.actions.append(("select", element))

    def click(self, element):
        self.actions.append(("click", element))

    def extract(self):
        self.actions.append(("extract", None))
        return "page text"


from typing import Any  # noqa: E402 - after Driver for readability


def capability():
    return issue_capability(
        company="A社", target_url=FORM_URL, form_schema_hash="schema-1"
    )


def session(fields=None, terminal_max=1):
    return build_session(
        capability(),
        allowed_fields=fields or {"company", "name", "email", "subject", "message"},
        message_hash="m-hash",
        sender_identity_hash="s-hash",
        terminal_submit_max=terminal_max,
    )


def adapter(with_session=True, driver=None, **kwargs):
    return RestrictedBrowserAdapter(
        driver=driver or Driver(),
        allowed_origins=ALLOWED,
        session=session(**kwargs) if with_session else None,
    )


# --- the ten regressions ----------------------------------------------------

def test_agent_cannot_use_javascript_to_bypass_capability():
    guarded = adapter()
    with pytest.raises(AdapterError, match="無効化"):
        guarded.invoke("evaluate", script="document.forms[0].submit()")
    assert guarded.driver.actions == []


def test_enter_key_cannot_submit():
    guarded = adapter()
    for action in ("send_keys", "press", "keyboard"):
        with pytest.raises(AdapterError):
            guarded.invoke(action, keys="Enter")
    assert guarded.driver.actions == []


def test_click_cannot_bypass_final_gate():
    guarded = adapter()
    submit = Element("btn", is_submit=True)
    guarded.invoke("safe_click", element=submit)
    # The capability was spent, so a second submit is refused.
    with pytest.raises(CapabilityError):
        guarded.invoke("safe_click", element=submit)


def test_input_is_denied_without_mutation_capability():
    guarded = adapter(with_session=False)
    with pytest.raises(AdapterError, match="書き込み許可"):
        guarded.invoke("input", field_name="email", value="a@b.jp")
    assert guarded.driver.actions == []


def test_autosave_form_requires_capability_before_typing():
    """Typing is already a write: input, change and blur can post to the site."""
    guarded = adapter(with_session=False)
    assert "input" not in guarded.available_actions()
    with pytest.raises(AdapterError):
        guarded.invoke("input", field_name="name", value="山田 太郎")


def test_capability_is_bound_to_exact_origin_and_form():
    guarded = adapter()
    with pytest.raises(AdapterError, match="許可されたドメイン"):
        guarded.invoke("navigate", url="https://evil.example/contact")

    other_form = Element("btn", is_submit=True, navigates_to="https://evil.example/done")
    with pytest.raises(AdapterError, match="遷移"):
        guarded.invoke("safe_click", element=other_form)


def test_agent_success_claim_never_counts_as_submission():
    verifier = SubmissionVerifier(lambda text: (False, "受付確認の表示がありません"))
    collector = EvidenceCollector(lambda: "ホームへ戻る", lambda: FORM_URL)
    evidence = collector.before(
        company="A社", target_url=FORM_URL, capability=capability(), message="m"
    )
    report = AgentReport(claim="Successfully submitted the form")
    evidence = collector.after(evidence, claim=report.as_evidence_note())

    record = verifier.judge(evidence)
    assert record.submitted is False
    assert verifier.submitted_count == 0


def test_browser_use_judge_cannot_write_ledger():
    verifier = SubmissionVerifier(lambda text: (False, "未確認"))
    report = AgentReport(claim="done", agent_judge_verdict="task_completed_successfully")

    # The agent's own judge is only ever a string on the evidence.
    collector = EvidenceCollector(lambda: "", lambda: FORM_URL)
    evidence = collector.before(
        company="A社", target_url=FORM_URL, capability=capability(), message="m"
    )
    evidence = collector.after(evidence, claim=report.as_evidence_note())
    verifier.judge(evidence)

    assert verifier.submitted_count == 0
    assert "task_completed_successfully" in evidence.actuator_claim
    with pytest.raises(AttributeError):
        verifier.ledger.append("偽")  # type: ignore[attr-defined]


def test_redirect_to_other_origin_is_denied():
    guarded = adapter()
    leaving = Element("link", navigates_to="https://tracker.example/collect")
    with pytest.raises(AdapterError, match="遷移"):
        guarded.invoke("safe_click", element=leaving)


def test_second_terminal_submission_is_denied():
    guarded = adapter(terminal_max=1)
    submit = Element("btn", is_submit=True)
    guarded.invoke("safe_click", element=submit)
    with pytest.raises(CapabilityError, match="上限"):
        guarded.invoke("safe_click", element=submit)


# --- surface ----------------------------------------------------------------

def test_dangerous_actions_are_absent_rather_than_guarded():
    guarded = adapter()
    exposed = set(guarded.tool_names())
    assert exposed.isdisjoint(FORBIDDEN_ACTIONS)
    assert "evaluate" not in exposed and "send_keys" not in exposed


def test_forbidden_actions_are_declared_for_removal_upstream():
    excluded = adapter().excluded_actions()
    assert "evaluate" in excluded and "send_keys" in excluded


def test_read_only_mode_still_allows_reading():
    guarded = adapter(with_session=False)
    assert guarded.mode == "read_only"
    guarded.invoke("navigate", url=FORM_URL)
    assert guarded.invoke("extract") == "page text"


def test_a_field_nobody_inspected_cannot_be_written():
    guarded = adapter(fields={"email", "message"})
    with pytest.raises(AdapterError, match="許可された入力項目"):
        guarded.invoke("input", field_name="url_confirm", value="x")


def test_an_element_with_an_unknown_handler_is_not_clicked():
    guarded = adapter()
    opaque = Element("btn", has_unknown_js_handler=True)
    with pytest.raises(AdapterError, match="確認できないハンドラ"):
        guarded.invoke("safe_click", element=opaque)


def test_allowed_input_reaches_the_driver():
    guarded = adapter()
    guarded.invoke("input", field_name="email", value="a@b.jp")
    assert ("input", "email") in guarded.driver.actions
    assert guarded.session.fields_written == ["email"]


def test_an_unknown_action_is_refused():
    with pytest.raises(AdapterError, match="未知の操作"):
        adapter().invoke("teleport")

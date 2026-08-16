"""Checks the restriction against the live browser-use registry, not our intent."""

import pytest

from council.executors.browser_use_driver import (
    EXCLUDED_BROWSER_USE_ACTIONS,
    BrowserUseDriver,
    RuntimeSurfaceError,
    assert_surface_is_safe,
    build_tools,
    connect,
    element_from_dom,
    registry_action_names,
)
from council.executors.restricted_adapter import AdapterError

browser_use = pytest.importorskip("browser_use")


class Session:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args))
            return f"{name}-ok"

        return record


# --- against the real library ----------------------------------------------

def test_the_real_registry_ships_the_dangerous_actions():
    """If this ever fails, the threat model changed and the rest is stale."""
    everything = registry_action_names(browser_use.Tools())
    assert {"evaluate", "send_keys", "upload_file"} <= everything


def test_excluding_them_actually_removes_them_at_runtime():
    tools = build_tools(browser_use.Tools)
    present = assert_surface_is_safe(tools)
    for action in EXCLUDED_BROWSER_USE_ACTIONS:
        assert action not in present


def test_the_remaining_surface_is_still_enough_to_work():
    present = registry_action_names(build_tools(browser_use.Tools))
    assert {"navigate", "click", "input", "extract", "scroll"} <= present


def test_a_leaked_action_refuses_to_start():
    class Leaky:
        def __init__(self, exclude_actions=None):
            self.registry = type("R", (), {"registry": type("I", (), {"actions": {
                "navigate": object(), "evaluate": object(),
            }})()})()

    with pytest.raises(RuntimeSurfaceError, match="危険なアクション"):
        assert_surface_is_safe(Leaky())


def test_an_unreadable_registry_is_treated_as_unsafe():
    with pytest.raises(RuntimeSurfaceError):
        registry_action_names(object())


def test_extra_exclusions_are_honoured():
    tools = build_tools(browser_use.Tools, extra_excluded=["go_back"])
    assert "go_back" not in registry_action_names(tools)


# --- the wiring -------------------------------------------------------------

def test_connect_returns_a_read_only_adapter_without_a_write_session():
    adapter, tools = connect(
        tools_factory=browser_use.Tools,
        session=Session(),
        allowed_origins=frozenset({"https://example.co.jp"}),
    )
    assert adapter.mode == "read_only"
    assert "input" not in adapter.available_actions()
    assert set(adapter.tool_names()).isdisjoint(EXCLUDED_BROWSER_USE_ACTIONS)


def test_the_adapter_still_refuses_javascript_after_wiring():
    adapter, _ = connect(
        tools_factory=browser_use.Tools,
        session=Session(),
        allowed_origins=frozenset({"https://example.co.jp"}),
    )
    with pytest.raises(AdapterError):
        adapter.invoke("evaluate", script="document.forms[0].submit()")


def test_read_actions_reach_the_session():
    session = Session()
    adapter, _ = connect(
        tools_factory=browser_use.Tools,
        session=session,
        allowed_origins=frozenset({"https://example.co.jp"}),
    )
    adapter.invoke("navigate", url="https://example.co.jp/contact")
    assert session.calls == [("navigate", ("https://example.co.jp/contact",))]


def test_navigation_off_origin_never_reaches_the_session():
    session = Session()
    adapter, _ = connect(
        tools_factory=browser_use.Tools,
        session=session,
        allowed_origins=frozenset({"https://example.co.jp"}),
    )
    with pytest.raises(AdapterError):
        adapter.invoke("navigate", url="https://evil.example/")
    assert session.calls == []


def test_the_driver_maps_select_to_the_library_name():
    session = Session()
    BrowserUseDriver(session).select("field", "value")
    assert session.calls[0][0] == "select_dropdown"


# --- element characterisation ----------------------------------------------

def test_a_submit_button_is_recognised():
    element = element_from_dom({"tag": "button", "type": "submit", "id": "send"})
    assert element.is_submit is True


def test_a_bare_button_is_treated_as_submit():
    assert element_from_dom({"tag": "button", "id": "b"}).is_submit is True


def test_an_unrecognised_handler_marks_the_element_unsafe():
    element = element_from_dom({"tag": "button", "handlers": ["trackAndPost"]})
    assert element.has_unknown_js_handler is True


def test_a_known_handler_is_acceptable():
    element = element_from_dom({"tag": "button", "type": "submit", "handlers": ["validate"]})
    assert element.has_unknown_js_handler is False


def test_a_link_carries_its_destination():
    element = element_from_dom({"tag": "a", "href": "https://other.example/x"})
    assert element.navigates_to == "https://other.example/x"

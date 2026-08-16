"""Binds browser-use to the restricted surface, and checks it at runtime.

browser-use supports removing its own default actions and accepting custom
tools that receive the live BrowserSession, so narrowing it is what the library
is built for rather than something worked around. This module does that
binding and then verifies it, because a declared restriction that turns out not
to have applied is worse than no restriction: the guarantee is believed and
absent.

So the registry is read back after construction. If a forbidden action is still
present the driver refuses to start, rather than running with a hole in it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from council.executors.restricted_adapter import (
    FORBIDDEN_ACTIONS,
    Element,
    RestrictedBrowserAdapter,
)


#: browser-use's own names for the actions that must not exist at runtime.
#: Wider than FORBIDDEN_ACTIONS because the library ships more file and tab
#: handling than the adapter's vocabulary covers.
EXCLUDED_BROWSER_USE_ACTIONS: tuple[str, ...] = (
    "evaluate",       # arbitrary JavaScript
    "send_keys",      # Enter submits a form
    "write_file",
    "replace_file",
    "read_file",
    "upload_file",
    "save_as_pdf",
    "switch",         # tab switching escapes the origin restriction
    "close",
    "search",         # navigates to a search engine, off-origin by definition
)


class RuntimeSurfaceError(RuntimeError):
    """Raised when the live registry does not match what was asked for."""


def build_tools(tools_factory: Any, *, extra_excluded: Iterable[str] = ()) -> Any:
    """Construct browser-use Tools with the dangerous actions removed.

    ``tools_factory`` is injected so this can be exercised without importing
    browser-use, and so a future version with a different constructor can be
    swapped in without touching the safety logic.
    """
    excluded = sorted({*EXCLUDED_BROWSER_USE_ACTIONS, *extra_excluded})
    return tools_factory(exclude_actions=excluded)


def registry_action_names(tools: Any) -> set[str]:
    """Read the actions that actually exist, not the ones we intended."""
    registry = getattr(tools, "registry", None)
    inner = getattr(registry, "registry", registry)
    actions = getattr(inner, "actions", None)
    if actions is None:
        raise RuntimeSurfaceError("browser-useのアクション一覧を読み取れません")
    return set(actions.keys())


def assert_surface_is_safe(tools: Any, *, extra_excluded: Iterable[str] = ()) -> set[str]:
    """Fail loudly if anything dangerous survived construction."""
    present = registry_action_names(tools)
    forbidden = {*EXCLUDED_BROWSER_USE_ACTIONS, *extra_excluded, *FORBIDDEN_ACTIONS}
    leaked = sorted(present & forbidden)
    if leaked:
        raise RuntimeSurfaceError(
            f"危険なアクションが実行時にも残っています: {leaked}。"
            "この状態では外部操作を開始しません。"
        )
    return present


@dataclass
class BrowserUseDriver:
    """The driver the adapter calls. Every method is a narrow, checked action.

    The adapter above decides whether an action is permitted; this only carries
    it out. Keeping the decision and the mechanism apart is what stops a future
    convenience method from quietly becoming a way round the gate.
    """

    session: Any

    def navigate(self, url: str) -> Any:
        return self.session.navigate(url)

    def input(self, element_id: str, value: str) -> Any:
        return self.session.input(element_id, value)

    def select(self, element_id: str, value: str) -> Any:
        return self.session.select_dropdown(element_id, value)

    def click(self, element_id: str) -> Any:
        return self.session.click(element_id)

    def extract(self) -> str:
        return self.session.extract()

    def screenshot(self) -> Any:
        return self.session.screenshot()

    def scroll(self, amount: int = 500) -> Any:
        return self.session.scroll(amount)

    def find_text(self, text: str) -> Any:
        return self.session.find_text(text)


def connect(
    *,
    tools_factory: Any,
    session: Any,
    allowed_origins: frozenset[str],
    write_session: Any = None,
    extra_excluded: Iterable[str] = (),
) -> tuple[RestrictedBrowserAdapter, Any]:
    """Wire browser-use behind the adapter, refusing to start if unsafe."""
    tools = build_tools(tools_factory, extra_excluded=extra_excluded)
    assert_surface_is_safe(tools, extra_excluded=extra_excluded)
    adapter = RestrictedBrowserAdapter(
        driver=BrowserUseDriver(session),
        allowed_origins=allowed_origins,
        session=write_session,
    )
    return adapter, tools


def element_from_dom(node: dict[str, Any]) -> Element:
    """Describe a DOM node for :meth:`RestrictedBrowserAdapter._safe_click`.

    Anything unrecognised is reported as an unknown handler, so an element the
    inspector could not characterise is refused rather than assumed harmless.
    """
    tag = str(node.get("tag", "")).lower()
    node_type = str(node.get("type", "")).lower()
    is_submit = node_type == "submit" or (
        tag == "button" and node_type in ("", "submit")
    )
    handlers = node.get("handlers") or []
    known = {"submit", "validate", "confirm"}
    unknown = any(str(h).lower() not in known for h in handlers)
    return Element(
        element_id=str(node.get("id") or node.get("selector") or ""),
        tag=tag or "button",
        field_name=str(node.get("name") or ""),
        is_submit=is_submit,
        has_unknown_js_handler=unknown,
        navigates_to=str(node.get("href") or node.get("action") or ""),
    )

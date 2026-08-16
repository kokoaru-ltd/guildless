"""Hands a browser agent a deliberately smaller browser.

browser-use ships with click, input, send_keys and evaluate. Any one of those
reaches the outside world on its own: evaluate runs arbitrary JavaScript,
send_keys can press Enter inside a form, and click can fire submit directly. An
agent given the default toolset does not need permission to submit — it already
has four ways round whatever gate is placed after it.

So the agent gets a restricted surface instead. The dangerous actions are not
guarded, they are absent, and the ones that remain go through this adapter.

The permission it needs is not "may I press submit". Forms send data on input,
change and blur through autosave and analytics, so typing a real name into a
real form is already a write to someone else's system. The capability therefore
authorises a writing session over one specific form, and without it the agent
can read pages and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from urllib.parse import urlparse

from council.executors.safety_kernel import CapabilityError, SubmissionCapability


Mode = Literal["read_only", "mutation"]

#: Removed from the agent entirely. Each is a way to submit without asking.
FORBIDDEN_ACTIONS: frozenset[str] = frozenset({
    "evaluate",        # arbitrary JavaScript: defeats every check at once
    "execute_js",
    "send_keys",       # Enter inside a form submits it
    "press",
    "keyboard",
    "write_file",
    "replace_file",
    "upload_file",
    "download_file",
    "new_tab",         # a fresh tab escapes the origin restriction
})

#: Safe with no permission at all: they observe, they do not write.
READ_ONLY_ACTIONS: frozenset[str] = frozenset({
    "navigate", "extract", "screenshot", "scroll", "find_text", "read_page",
})

#: Available only while a capability is held.
MUTATION_ACTIONS: frozenset[str] = frozenset({
    "input", "select", "safe_click",
})


class AdapterError(RuntimeError):
    pass


@dataclass
class WriteSession:
    """Authorisation to type into one form, and to submit it once.

    ``allowed_fields`` bounds what may be written, so an agent cannot fill a
    field nobody inspected. ``terminal_submit_max`` is separate from typing
    because typing is already a side effect on many forms.
    """

    capability: SubmissionCapability
    allowed_fields: frozenset[str]
    message_hash: str
    sender_identity_hash: str
    terminal_submit_max: int = 1
    terminal_submits: int = 0
    fields_written: list[str] = field(default_factory=list)

    @property
    def origin(self) -> str:
        return origin_of(self.capability.target_url)

    def may_write(self, field_name: str) -> tuple[bool, str]:
        if field_name not in self.allowed_fields:
            return False, f"{field_name}は許可された入力項目ではありません"
        return True, ""

    def spend_terminal(self) -> None:
        if self.terminal_submits >= self.terminal_submit_max:
            raise CapabilityError("この許可での送信は既に上限に達しています")
        self.capability.consume(
            company=self.capability.company,
            target_url=self.capability.target_url,
            form_schema_hash=self.capability.form_schema_hash,
        )
        self.terminal_submits += 1


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


@dataclass
class Element:
    """What the adapter knows about a thing before letting the agent touch it."""

    element_id: str
    tag: str = "input"
    field_name: str = ""
    is_submit: bool = False
    has_unknown_js_handler: bool = False
    navigates_to: str = ""


class RestrictedBrowserAdapter:
    """The only browser surface an untrusted agent is given."""

    def __init__(
        self,
        *,
        driver: Any,
        allowed_origins: frozenset[str],
        session: WriteSession | None = None,
    ):
        self.driver = driver
        self.allowed_origins = allowed_origins
        self.session = session
        self.calls: list[tuple[str, str]] = []

    # -- capability surface --------------------------------------------------

    @property
    def mode(self) -> Mode:
        return "mutation" if self.session is not None else "read_only"

    def available_actions(self) -> frozenset[str]:
        if self.mode == "read_only":
            return READ_ONLY_ACTIONS
        return READ_ONLY_ACTIONS | MUTATION_ACTIONS

    def tool_names(self) -> list[str]:
        """What to expose to browser-use. Forbidden actions are never listed."""
        return sorted(self.available_actions())

    def excluded_actions(self) -> list[str]:
        """Passed to browser-use so the defaults are removed, not merely unused."""
        return sorted(FORBIDDEN_ACTIONS)

    def invoke(self, action: str, **kwargs: Any) -> Any:
        """Single entry point. An unknown or forbidden action does not run."""
        self.calls.append((action, kwargs.get("field_name") or kwargs.get("element_id", "")))

        if action in FORBIDDEN_ACTIONS:
            raise AdapterError(f"{action}は利用できません（この経路は無効化されています）")
        if action not in self.available_actions():
            if action in MUTATION_ACTIONS:
                raise AdapterError(
                    f"{action}には書き込み許可が必要です。現在は読み取りのみ許可されています。"
                )
            raise AdapterError(f"{action}は未知の操作のため実行しません")

        handler = getattr(self, f"_{action}", None)
        if handler is None:
            return getattr(self.driver, action)(**kwargs)
        return handler(**kwargs)

    # -- read-only -----------------------------------------------------------

    def _navigate(self, url: str) -> Any:
        if not self._origin_allowed(url):
            raise AdapterError(f"{origin_of(url)}は許可されたドメインではありません")
        return self.driver.navigate(url)

    # -- mutation ------------------------------------------------------------

    def _input(self, *, field_name: str, value: str, element_id: str = "") -> Any:
        session = self._require_session()
        allowed, reason = session.may_write(field_name)
        if not allowed:
            raise AdapterError(reason)
        session.fields_written.append(field_name)
        return self.driver.input(element_id or field_name, value)

    def _select(self, *, field_name: str, value: str, element_id: str = "") -> Any:
        session = self._require_session()
        allowed, reason = session.may_write(field_name)
        if not allowed:
            raise AdapterError(reason)
        return self.driver.select(element_id or field_name, value)

    def _safe_click(self, *, element: Element) -> Any:
        session = self._require_session()

        if element.has_unknown_js_handler:
            # An unknown handler can do anything, including submitting to a
            # third party. Refusing is the only way to keep the guarantee.
            raise AdapterError("挙動を確認できないハンドラが付いた要素は押しません")

        if element.navigates_to and not self._origin_allowed(element.navigates_to):
            raise AdapterError(
                f"{origin_of(element.navigates_to)}への遷移は許可されていません"
            )

        if element.is_submit:
            session.spend_terminal()

        return self.driver.click(element.element_id)

    # -- internals -----------------------------------------------------------

    def _require_session(self) -> WriteSession:
        if self.session is None:
            raise AdapterError(
                "書き込み許可がありません。入力・選択・クリックは実行できません。"
            )
        return self.session

    def _origin_allowed(self, url: str) -> bool:
        return origin_of(url) in self.allowed_origins


def build_session(
    capability: SubmissionCapability,
    *,
    allowed_fields: set[str],
    message_hash: str,
    sender_identity_hash: str,
    terminal_submit_max: int = 1,
) -> WriteSession:
    return WriteSession(
        capability=capability,
        allowed_fields=frozenset(allowed_fields),
        message_hash=message_hash,
        sender_identity_hash=sender_identity_hash,
        terminal_submit_max=terminal_submit_max,
    )


@dataclass
class AgentReport:
    """Whatever the agent concluded. Kept for the record, never for the count."""

    claim: str = ""
    agent_judge_verdict: str = ""

    def as_evidence_note(self) -> str:
        parts = [p for p in (self.claim, self.agent_judge_verdict) if p]
        return " / ".join(parts)[:300]

"""Renders contact pages in a real browser, because forms are not documents.

A raw POST works only for forms that do not exist any more: modern ones carry
CSRF tokens, hidden state, fields injected by JavaScript, honeypots that only
a renderer can see are invisible, and a separate confirmation step between the
submit button and anything actually being sent.

So the page is loaded in Chromium and read the way a person would see it. That
also means the anti-bot signals are visible: a CAPTCHA widget, a login wall, a
challenge page. Those are a site declining to be automated, and this module
reports them so the caller can leave.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


#: Input types that never hold contact details and must not be filled.
IGNORED_INPUT_TYPES = frozenset({"hidden", "submit", "button", "image", "reset", "file"})


@dataclass
class FormField:
    name: str
    field_type: str
    label: str
    required: bool
    #: True when the page hides it from a human. Filling one marks the sender
    #: as a bot, which is exactly what it is there to do.
    honeypot: bool = False
    options: list[str] = field(default_factory=list)


@dataclass
class RenderedPage:
    url: str
    final_url: str
    title: str
    text: str
    fields: list[FormField]
    has_form: bool
    #: Anti-automation measures observed. Any entry means do not proceed.
    challenges: list[str] = field(default_factory=list)
    html: str = ""

    @property
    def blocked(self) -> bool:
        return bool(self.challenges)


class PageLike(Protocol):
    """The slice of Playwright's Page this module uses."""

    def goto(self, url: str, **kwargs: Any) -> Any: ...
    def content(self) -> str: ...
    def inner_text(self, selector: str) -> str: ...
    def title(self) -> str: ...
    def evaluate(self, expression: str) -> Any: ...
    @property
    def url(self) -> str: ...


#: Runs in the page. Reading fields from the live DOM is the only way to see
#: JS-injected inputs and computed visibility, which is what distinguishes a
#: honeypot from a real field.
FIELD_SCRIPT = """
() => {
  const out = [];
  const els = document.querySelectorAll('form input, form textarea, form select');
  for (const el of els) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    // Off-screen positioning is usually applied to a wrapper rather than the
    // input, so the element's own computed style says nothing. Its rendered
    // rectangle does, which is why the position is read from there.
    const offScreen =
      rect.right < 0 || rect.bottom < 0 ||
      rect.left > (window.innerWidth || 0) + 1000 ||
      rect.top > (window.innerHeight || 0) + 5000;
    const hidden =
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      style.opacity === '0' ||
      (rect.width === 0 && rect.height === 0) ||
      offScreen;
    let label = '';
    const id = el.getAttribute('id');
    if (id) {
      const byFor = document.querySelector(`label[for="${CSS.escape(id)}"]`);
      if (byFor) label = byFor.innerText;
    }
    if (!label) {
      const parent = el.closest('label');
      if (parent) label = parent.innerText;
    }
    if (!label) {
      const cell = el.closest('td, div, li, p');
      const prev = cell ? cell.previousElementSibling : null;
      if (prev) label = prev.innerText;
    }
    out.push({
      name: el.getAttribute('name') || el.getAttribute('id') || '',
      type: type,
      label: (label || el.getAttribute('placeholder') || '').trim().slice(0, 120),
      required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
      hidden: hidden,
      options: el.tagName.toLowerCase() === 'select'
        ? Array.from(el.options).map(o => o.value) : [],
    });
  }
  return out;
}
"""

CHALLENGE_MARKERS = {
    "recaptcha": ("g-recaptcha", "recaptcha/api.js", "grecaptcha"),
    "hcaptcha": ("h-captcha", "hcaptcha.com"),
    "turnstile": ("cf-turnstile", "challenges.cloudflare.com"),
    "generic_captcha": ("captcha", "画像認証", "認証コードを入力"),
    "login_required": ("ログインしてください", "会員登録が必要", "please sign in"),
}


class BrowserFetcher:
    """Loads a page and reports what is actually there."""

    def __init__(self, page: PageLike, *, timeout_ms: int = 20_000):
        self.page = page
        self.timeout_ms = timeout_ms

    def fetch(self, url: str) -> RenderedPage:
        self.page.goto(url, timeout=self.timeout_ms, wait_until="domcontentloaded")
        html = self.page.content()
        try:
            text = self.page.inner_text("body")
        except Exception:  # noqa: BLE001 - a page with no body is simply unreadable
            text = ""

        raw_fields = self.page.evaluate(FIELD_SCRIPT) or []
        fields = [
            FormField(
                name=str(item.get("name") or ""),
                field_type=str(item.get("type") or "text"),
                label=str(item.get("label") or ""),
                required=bool(item.get("required")),
                honeypot=bool(item.get("hidden")),
                options=[str(o) for o in (item.get("options") or [])],
            )
            for item in raw_fields
            if str(item.get("type", "")).lower() not in IGNORED_INPUT_TYPES
        ]

        return RenderedPage(
            url=url,
            final_url=self.page.url,
            title=self.page.title(),
            text=text,
            fields=fields,
            has_form=bool(fields),
            challenges=detect_challenges(html, text),
            html=html,
        )


def detect_challenges(html: str, text: str) -> list[str]:
    """Name every anti-automation measure present. Never used to defeat one."""
    haystack = f"{html}\n{text}".lower()
    return [
        name for name, markers in CHALLENGE_MARKERS.items()
        if any(marker.lower() in haystack for marker in markers)
    ]

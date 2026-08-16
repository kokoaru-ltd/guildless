"""The one-time permission to touch the outside world.

Two things have to be true at once. The user must not be asked "shall I contact
these twenty companies?" — that puts a person back in the loop and undoes the
whole design. And Guildless must not be able to decide on its own that it may
start contacting people.

So permission is granted once, by a human, for a scope: which channels, how
many contacts a day, how much may be spent. Inside that scope every individual
action proceeds without confirmation. Outside it, nothing happens at all.

The grant is the boundary that keeps everything else honest, so it is the one
thing the system cannot reach. No strategy, no model, no self-modification can
create a grant, widen one, or weaken its limits. A company that can raise its
own permissions has none.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class GrantError(RuntimeError):
    """Raised on any attempt to obtain permission that was not given."""


#: Written by a person, read by the machine. Kept separate from anything the
#: system generates so an autonomous edit cannot produce one.
GRANT_FILENAME = "external_action_grant.json"


@dataclass(frozen=True)
class ExternalActionGrant:
    """What Guildless is allowed to do outside the machine.

    Frozen, and never constructed from model output. The only supported way to
    obtain one is :func:`load`, which reads a file a human wrote.
    """

    scope: str
    channels: frozenset[str]
    max_contacts_per_day: int
    max_contacts_per_company: int = 1
    max_spend_yen: int = 0
    expires_at: str | None = None
    granted_by: str = "human"
    granted_at: str = ""

    def allows_channel(self, channel: str) -> bool:
        return channel in self.channels

    def expired(self, now: datetime | None = None) -> bool:
        if not self.expires_at:
            return False
        moment = now or datetime.now(UTC)
        try:
            return moment >= datetime.fromisoformat(self.expires_at)
        except ValueError:
            # An unparseable expiry is treated as expired. Failing closed is
            # the only safe reading of a permission we cannot understand.
            return True

    def check(self, *, channel: str, spend_yen: int, contacts_today: int,
              contacts_for_company: int, now: datetime | None = None) -> tuple[bool, str]:
        """Whether one specific action falls inside the granted scope."""
        if self.expired(now):
            return False, "外部実行の許可が期限切れです"
        if not self.allows_channel(channel):
            return False, f"{channel}は許可された経路に含まれていません"
        if spend_yen > self.max_spend_yen:
            return False, f"支出¥{spend_yen:,}は許可上限¥{self.max_spend_yen:,}を超えます"
        if contacts_today >= self.max_contacts_per_day:
            return False, f"本日の接触が上限{self.max_contacts_per_day}件に達しています"
        if contacts_for_company >= self.max_contacts_per_company:
            return False, f"同一企業への接触が上限{self.max_contacts_per_company}件に達しています"
        return True, "許可範囲内です"


#: What a company with no money may do on day one: submit public contact forms,
#: a bounded number per day, once per company, spending nothing.
BOOTSTRAP_SCOPE = {
    "scope": "b2b_outreach",
    "channels": ["contact_form"],
    "max_contacts_per_day": 20,
    "max_contacts_per_company": 1,
    "max_spend_yen": 0,
}


def load(directory: Path) -> ExternalActionGrant | None:
    """Read the grant a human wrote, or None if there is not one.

    None is the normal state. It means the company may plan, research, build
    and prove delivery, and may not contact anybody.
    """
    path = Path(directory) / GRANT_FILENAME
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise GrantError(f"許可ファイルを読めません: {exc}") from None

    missing = {"scope", "channels", "max_contacts_per_day"} - set(raw)
    if missing:
        raise GrantError(f"許可ファイルに必須項目がありません: {sorted(missing)}")

    return ExternalActionGrant(
        scope=str(raw["scope"]),
        channels=frozenset(str(c) for c in raw["channels"]),
        max_contacts_per_day=int(raw["max_contacts_per_day"]),
        max_contacts_per_company=int(raw.get("max_contacts_per_company", 1)),
        max_spend_yen=int(raw.get("max_spend_yen", 0)),
        expires_at=raw.get("expires_at"),
        granted_by=str(raw.get("granted_by", "human")),
        granted_at=str(raw.get("granted_at", "")),
    )


def template() -> dict[str, Any]:
    """The file a person writes to switch outreach on. Not written by code."""
    return {
        **BOOTSTRAP_SCOPE,
        "granted_by": "",
        "granted_at": "",
        "expires_at": None,
        "_note": (
            "このファイルを作成した時点で、Guildlessは記載範囲内で外部へ接触を開始します。"
            "範囲内の個々の送信について再確認は行いません。"
            "Guildless自身はこのファイルを作成・変更できません。"
        ),
    }


@dataclass
class GrantedActions:
    """Counts what has actually been done, so limits mean something."""

    per_day: dict[str, int] = field(default_factory=dict)
    per_company: dict[str, int] = field(default_factory=dict)

    def contacts_today(self, day: str) -> int:
        return self.per_day.get(day, 0)

    def contacts_for(self, company: str) -> int:
        return self.per_company.get(company, 0)

    def record(self, day: str, company: str) -> None:
        self.per_day[day] = self.per_day.get(day, 0) + 1
        self.per_company[company] = self.per_company.get(company, 0) + 1

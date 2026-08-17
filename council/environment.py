"""What this company already has, discovered rather than asked for.

Asking "which services would you like to connect?" loses on the first screen.
The owner already has a browser signed into their payment processor, their
marketplace, their mail; a system that makes them enumerate it is one they are
configuring, not one that is running their company.

So this reads the machine. Which browsers exist, which profiles are real, which
services this person actually uses, and which they hold accounts with. None of
it is a question.

Three properties hold, and the tests enforce all three:

**A whitelist, never a dump.** Browser history is a record of someone's life,
most of which is nobody's business and none of which is a revenue channel. Only
hosts matching a known business service survive; everything else is discarded
in the same pass that reads it, never stored, never counted, never shown. The
consequence is deliberate -- Guildless will miss a service it does not know --
because the alternative is a business tool that reports what its owner reads at
night.

**Origins only, never secrets.** ``Login Data`` names the sites an account
exists on, in a column beside the encrypted password. This reads the first and
never the second. There is no decryption path in this module and no call that
could grow one.

**Copies, never locks.** Chrome holds these files while it runs. Every read is
taken from a snapshot copy, so discovery cannot corrupt a profile or block the
browser the owner is using. Files Chrome holds exclusively -- the cookie store
-- are simply unavailable, and that is reported as unavailable rather than
worked around.
"""

from __future__ import annotations

import collections
import json
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

#: Business services worth knowing about, by the role they play in a company.
#: Matched against the registrable part of a hostname, so "checkout.stripe.com"
#: and "dashboard.stripe.com" both resolve to the same service.
SERVICES: dict[str, tuple[str, ...]] = {
    "payments": (
        "stripe.com", "paypal.com", "payoneer.com", "wise.com", "square.com",
        "paddle.com", "gumroad.com", "lemonsqueezy.com", "pay.jp", "komoju.com",
    ),
    "banking": (
        "paypay-bank.co.jp", "rakuten-bank.co.jp", "gmo-aozora.com",
        "smbc.co.jp", "mufg.jp", "japannetbank.co.jp", "sonybank.net",
    ),
    "marketplace": (
        "lancers.jp", "crowdworks.jp", "coconala.com", "upwork.com",
        "fiverr.com", "levtech.jp", "indeed.com", "freelance-start.com",
        "base.shop", "booth.pm", "stores.jp", "shopify.com", "etsy.com",
    ),
    "crm": (
        "hubspot.com", "salesforce.com", "pipedrive.com", "zoho.com",
        "attio.com", "close.com", "kintone.com",
    ),
    "mail": (
        "mail.google.com", "outlook.com", "outlook.live.com", "muumuu-domain.com",
        "zoho.com", "proton.me", "fastmail.com",
    ),
    "hosting": (
        "conoha.jp", "xserver.ne.jp", "sakura.ad.jp", "vercel.com",
        "netlify.com", "cloudflare.com", "runpod.io", "aws.amazon.com",
        "console.cloud.google.com", "azure.com", "heroku.com", "railway.app",
    ),
    "domains": (
        "muumuu-domain.com", "onamae.com", "namecheap.com", "godaddy.com",
        "rakkoid.com", "value-domain.com",
    ),
    "code": ("github.com", "gitlab.com", "bitbucket.org"),
    "ads": (
        "ads.google.com", "business.facebook.com", "ads.tiktok.com",
        "ads.x.com", "yahoo-net.jp",
    ),
    "analytics": (
        "analytics.google.com", "search.google.com", "posthog.com",
        "mixpanel.com", "plausible.io",
    ),
    "social": (
        "x.com", "linkedin.com", "threads.com", "instagram.com",
        "facebook.com", "note.com", "youtube.com",
    ),
    "ai_tools": (
        "elevenlabs.io", "openai.com", "anthropic.com", "deepl.com",
        "runwayml.com", "midjourney.com", "civitai.com", "huggingface.co",
    ),
    "accounting": (
        "freee.co.jp", "moneyforward.com", "yayoi-kk.co.jp", "quickbooks.com",
        "xero.com",
    ),
}

#: Roles a company needs filled before Guildless can act on revenue without
#: guessing. Understanding is measured against these, not against the total
#: number of services found -- twenty social accounts and no way to take money
#: is not a well-understood company.
ESSENTIAL_ROLES: tuple[str, ...] = ("payments", "mail", "marketplace", "code", "hosting")

#: Artefacts Chrome leaves readable while it runs. The cookie store is absent
#: on purpose: Chrome opens it with no sharing, so it cannot be read at all
#: while the browser is up, and pretending otherwise would mean either killing
#: the owner's browser or reporting a guess.
READABLE_ARTEFACTS: tuple[str, ...] = ("History", "Login Data", "Preferences", "Bookmarks")

BROWSER_ROOTS: dict[str, str] = {
    "Chrome": r"Google\Chrome\User Data",
    "Edge": r"Microsoft\Edge\User Data",
    "Brave": r"BraveSoftware\Brave-Browser\User Data",
    "Vivaldi": r"Vivaldi\User Data",
}

#: Profiles Chrome creates for its own purposes. They hold no user history and
#: reporting them as "profiles found" would inflate the picture.
SYNTHETIC_PROFILES = frozenset({"System Profile", "Guest Profile"})


class EnvironmentError_(RuntimeError):
    """Discovery could not run at all."""


@dataclass(frozen=True)
class Service:
    """A business service this company demonstrably uses."""

    host: str
    role: str
    #: Visits recorded in browser history. Zero when the service was found only
    #: because an account exists for it.
    visits: int = 0
    #: True when a stored credential names this origin.
    has_account: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "host": self.host, "role": self.role,
            "visits": self.visits, "has_account": self.has_account,
        }


@dataclass(frozen=True)
class Profile:
    browser: str
    name: str
    path: Path
    #: The signed-in account name, when the profile records one.
    account: str = ""


@dataclass
class Environment:
    """The company as the machine reveals it."""

    profiles: list[Profile] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    #: Artefacts that existed but could not be read, and why.
    unavailable: dict[str, str] = field(default_factory=dict)

    @property
    def roles(self) -> dict[str, list[Service]]:
        found: dict[str, list[Service]] = collections.defaultdict(list)
        for service in self.services:
            found[service.role].append(service)
        return dict(found)

    @property
    def understanding(self) -> int:
        """How much of the company is known, as a percentage.

        Measured against the roles that must be filled to act on revenue, so
        the figure means "can Guildless work with this" rather than "how many
        tabs does this person keep open".
        """
        if not ESSENTIAL_ROLES:
            return 100
        present = sum(1 for role in ESSENTIAL_ROLES if self.roles.get(role))
        return round(100 * present / len(ESSENTIAL_ROLES))

    @property
    def missing_roles(self) -> list[str]:
        return [role for role in ESSENTIAL_ROLES if not self.roles.get(role)]

    def as_dict(self) -> dict[str, object]:
        return {
            "understanding": self.understanding,
            "profiles": [
                {"browser": p.browser, "name": p.name, "account": p.account}
                for p in self.profiles
            ],
            "services": [s.as_dict() for s in self.services],
            "roles": {role: [s.host for s in found] for role, found in self.roles.items()},
            "missing_roles": self.missing_roles,
            "unavailable": self.unavailable,
        }


# --- classification ---------------------------------------------------------

def classify(host: str) -> str | None:
    """The business role a hostname fills, or None when it is not our business.

    None is the common case and the important one. An unrecognised host is
    discarded here, before it is counted or stored, which is what keeps a
    person's browsing out of their company's dashboard.
    """
    if not host:
        return None
    cleaned = host.lower().removeprefix("www.")
    for role, hosts in SERVICES.items():
        for known in hosts:
            if cleaned == known or cleaned.endswith("." + known):
                return role
    return None


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


# --- reading without disturbing ---------------------------------------------

def _snapshot(source: Path, into: Path) -> Path | None:
    """Copy an artefact aside so it can be read without holding a lock.

    Returns None when the browser holds the file exclusively. That is a normal
    outcome, not a failure: Chrome does it to the cookie store by design.
    """
    try:
        destination = into / source.name
        shutil.copy2(source, destination)
        return destination
    except OSError:
        return None


def _query(database: Path, sql: str) -> list[tuple]:
    connection = sqlite3.connect(database)
    try:
        return connection.execute(sql).fetchall()
    except sqlite3.DatabaseError:
        # A partially-written snapshot reads as corrupt. Nothing found beats a
        # crash during what is meant to be silent background discovery.
        return []
    finally:
        connection.close()


def _visited_services(profile: Path, workspace: Path) -> dict[str, int]:
    """Business hosts in browser history, with their visit counts."""
    history = profile / "History"
    if not history.exists():
        return {}
    copied = _snapshot(history, workspace)
    if copied is None:
        return {}
    tally: collections.Counter[str] = collections.Counter()
    for url, visits in _query(copied, "SELECT url, visit_count FROM urls"):
        host = _host_of(str(url))
        # Classified before it is counted. An unrecognised host never reaches
        # the tally, so it cannot be reported even by accident.
        if classify(host):
            tally[host.removeprefix("www.")] += int(visits or 0)
    return dict(tally)


def _account_origins(profile: Path, workspace: Path) -> set[str]:
    """Hosts a stored credential exists for.

    Reads ``origin_url`` and nothing else. ``password_value`` sits in the same
    table, encrypted, and this module has no way to touch it.
    """
    logins = profile / "Login Data"
    if not logins.exists():
        return set()
    copied = _snapshot(logins, workspace)
    if copied is None:
        return set()
    found = set()
    for (origin,) in _query(copied, "SELECT origin_url FROM logins"):
        host = _host_of(str(origin)).removeprefix("www.")
        if classify(host):
            found.add(host)
    return found


def _account_name(profile: Path) -> str:
    """The signed-in account a profile records, when it records one."""
    preferences = profile / "Preferences"
    if not preferences.exists():
        return ""
    try:
        data = json.loads(preferences.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return ""
    account = data.get("account_info")
    if isinstance(account, list) and account:
        first = account[0]
        if isinstance(first, dict):
            return str(first.get("email") or first.get("full_name") or "")
    return ""


# --- discovery --------------------------------------------------------------

def find_profiles(local_appdata: Path | None = None) -> list[Profile]:
    """Every real browser profile on this machine."""
    base = local_appdata or Path(os.environ.get("LOCALAPPDATA", ""))
    if not base or not base.exists():
        return []
    found: list[Profile] = []
    for browser, relative in BROWSER_ROOTS.items():
        root = base / relative
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name in SYNTHETIC_PROFILES:
                continue
            if not (entry / "Preferences").exists():
                continue
            found.append(Profile(browser, entry.name, entry, _account_name(entry)))
    return found


def discover(local_appdata: Path | None = None) -> Environment:
    """Read the machine and report the company. Asks nothing."""
    environment = Environment(profiles=find_profiles(local_appdata))
    visits: collections.Counter[str] = collections.Counter()
    accounts: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="guildless-env-") as workspace_name:
        workspace = Path(workspace_name)
        for index, profile in enumerate(environment.profiles):
            # Per-profile subdirectory: several profiles hold files of the same
            # name, and a shared directory would have them overwrite each other.
            cell = workspace / str(index)
            cell.mkdir()
            visits.update(_visited_services(profile.path, cell))
            accounts |= _account_origins(profile.path, cell)

            cookies = profile.path / "Network" / "Cookies"
            if cookies.exists() and _snapshot(cookies, cell) is None:
                environment.unavailable[f"{profile.browser}/{profile.name}/Cookies"] = (
                    "ブラウザが使用中のため読めません"
                )

    for host in sorted(set(visits) | accounts):
        role = classify(host)
        if role is None:  # unreachable by construction; kept as a hard floor
            continue
        environment.services.append(Service(
            host=host, role=role,
            visits=visits.get(host, 0),
            has_account=host in accounts,
        ))
    environment.services.sort(key=lambda s: (-s.visits, s.host))
    return environment


def summarise(environment: Environment) -> list[str]:
    """Lines for the boot screen, in the owner's terms.

    Says what was found and what is missing. "Missing" is a statement about
    Guildless's picture of the company, not a request -- nothing here asks the
    owner to go and connect something.
    """
    lines = [f"会社の把握度 {environment.understanding}%"]
    roles = environment.roles
    labels = {
        "payments": "決済", "banking": "銀行", "marketplace": "販路", "crm": "顧客管理",
        "mail": "メール", "hosting": "インフラ", "domains": "ドメイン", "code": "コード",
        "ads": "広告", "analytics": "計測", "social": "発信", "ai_tools": "AI",
        "accounting": "会計",
    }
    for role, services in roles.items():
        hosts = "、".join(s.host for s in services[:3])
        lines.append(f"{labels.get(role, role)}: {hosts}")
    for role in environment.missing_roles:
        lines.append(f"{labels.get(role, role)}: 見つかりません")
    return lines

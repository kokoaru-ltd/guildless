"""Discovery reads the machine, and reads only the company's part of it.

The privacy properties here are not decoration. Browser history is a record of
someone's life; a business tool that surfaces the whole of it is a worse
product than one that asks a setup question.
"""

import json
import sqlite3

import pytest

from council import environment as env


# --- the whitelist ----------------------------------------------------------

def test_known_business_hosts_are_classified():
    assert env.classify("stripe.com") == "payments"
    assert env.classify("lancers.jp") == "marketplace"
    assert env.classify("github.com") == "code"


def test_subdomains_resolve_to_the_same_service():
    assert env.classify("dashboard.stripe.com") == "payments"
    assert env.classify("checkout.stripe.com") == "payments"
    assert env.classify("www.paypal.com") == "payments"


def test_an_unrecognised_host_is_nobody_business():
    for host in ("nhentai.net", "example.com", "someones-diary.blog", ""):
        assert env.classify(host) is None


def test_a_lookalike_domain_is_not_the_service():
    """"stripe.com.evil.tld" must not read as Stripe."""
    assert env.classify("stripe.com.evil.tld") is None
    assert env.classify("notstripe.com") is None


# --- reading a real profile shape -------------------------------------------

def _make_profile(root, name, *, history=(), logins=(), account=""):
    profile = root / "Google" / "Chrome" / "User Data" / name
    (profile / "Network").mkdir(parents=True)
    (profile / "Preferences").write_text(
        json.dumps({"account_info": [{"email": account}]} if account else {}),
        encoding="utf-8",
    )
    connection = sqlite3.connect(profile / "History")
    connection.execute("CREATE TABLE urls (url TEXT, visit_count INTEGER)")
    connection.executemany("INSERT INTO urls VALUES (?, ?)", history)
    connection.commit()
    connection.close()

    connection = sqlite3.connect(profile / "Login Data")
    connection.execute(
        "CREATE TABLE logins (origin_url TEXT, username_value TEXT, password_value BLOB)"
    )
    connection.executemany(
        "INSERT INTO logins VALUES (?, ?, ?)",
        [(origin, "someone@example.com", b"\x01secret") for origin in logins],
    )
    connection.commit()
    connection.close()
    return profile


@pytest.fixture
def machine(tmp_path):
    _make_profile(
        tmp_path, "Default",
        history=[
            ("https://dashboard.stripe.com/payments", 120),
            ("https://www.lancers.jp/work", 80),
            ("https://github.com/someone", 40),
            ("https://nhentai.net/g/1", 900),
            ("https://someones-therapist.example/booking", 300),
        ],
        logins=["https://www.paypal.com/signin", "https://github.com/login"],
        account="owner@example.com",
    )
    return tmp_path


def test_it_finds_the_business_services(machine):
    found = env.discover(machine)
    hosts = {s.host for s in found.services}
    assert "dashboard.stripe.com" in hosts
    assert "lancers.jp" in hosts
    assert "github.com" in hosts


def test_personal_browsing_never_appears_anywhere(machine):
    """The property that matters most. Not filtered on display -- never stored."""
    found = env.discover(machine)
    serialised = json.dumps(found.as_dict(), ensure_ascii=False)
    for private in ("nhentai", "therapist"):
        assert private not in serialised
    assert all("nhentai" not in s.host for s in found.services)


def test_the_most_visited_personal_site_does_not_outrank_business(machine):
    """The private site had the highest visit count in the fixture."""
    found = env.discover(machine)
    assert found.services[0].host == "dashboard.stripe.com"


def test_visit_counts_survive(machine):
    found = env.discover(machine)
    stripe = next(s for s in found.services if s.host == "dashboard.stripe.com")
    assert stripe.visits == 120


def test_an_account_is_found_even_with_no_visits(machine):
    found = env.discover(machine)
    paypal = next(s for s in found.services if s.host == "paypal.com")
    assert paypal.has_account is True
    assert paypal.visits == 0


def test_the_profile_account_is_read(machine):
    found = env.discover(machine)
    assert found.profiles[0].account == "owner@example.com"


# --- secrets are never touched ----------------------------------------------

def test_no_password_is_ever_read(machine):
    found = env.discover(machine)
    serialised = json.dumps(found.as_dict(), ensure_ascii=False)
    assert "secret" not in serialised


def test_the_module_has_no_decryption_path():
    """A module that cannot decrypt cannot be made to leak a password."""
    source = (env.__file__)
    text = open(source, encoding="utf-8").read()
    for forbidden in ("CryptUnprotectData", "password_value", "win32crypt", "AES"):
        assert forbidden not in text.replace(
            "``password_value`` sits in the same", ""
        ), forbidden


# --- it must not disturb the browser ----------------------------------------

def test_reading_leaves_the_originals_untouched(machine):
    profile = machine / "Google" / "Chrome" / "User Data" / "Default"
    before = {p.name: p.stat().st_mtime_ns for p in profile.iterdir() if p.is_file()}
    env.discover(machine)
    after = {p.name: p.stat().st_mtime_ns for p in profile.iterdir() if p.is_file()}
    assert before == after


def test_a_locked_artefact_is_reported_not_worked_around(machine, monkeypatch):
    cookies = machine / "Google" / "Chrome" / "User Data" / "Default" / "Network" / "Cookies"
    cookies.write_bytes(b"")

    real = env._snapshot

    def refuse(source, into):
        return None if source.name == "Cookies" else real(source, into)

    monkeypatch.setattr(env, "_snapshot", refuse)
    found = env.discover(machine)
    assert any("Cookies" in key for key in found.unavailable)


def test_a_corrupt_database_yields_nothing_rather_than_crashing(tmp_path):
    profile = _make_profile(tmp_path, "Default")
    (profile / "History").write_bytes(b"this is not a database")
    found = env.discover(tmp_path)
    assert found.services == []


# --- understanding ----------------------------------------------------------

def test_understanding_measures_roles_not_service_count(tmp_path):
    """Twenty social accounts and no way to take money is not a known company."""
    _make_profile(tmp_path, "Default", history=[
        (f"https://x.com/{n}", 10) for n in range(20)
    ])
    found = env.discover(tmp_path)
    assert found.understanding == 0
    assert "payments" in found.missing_roles


def test_understanding_rises_as_essential_roles_fill(machine):
    found = env.discover(machine)
    # payments, marketplace, code present; mail and hosting absent.
    assert found.understanding == 60
    assert set(found.missing_roles) == {"mail", "hosting"}


def test_an_empty_machine_is_zero_not_an_error(tmp_path):
    found = env.discover(tmp_path)
    assert found.understanding == 0
    assert found.profiles == []
    assert found.services == []


def test_chrome_own_profiles_are_not_counted(tmp_path):
    for name in ("Default", "System Profile", "Guest Profile"):
        _make_profile(tmp_path, name)
    found = env.discover(tmp_path)
    assert [p.name for p in found.profiles] == ["Default"]


# --- the summary asks for nothing -------------------------------------------

def test_the_summary_never_asks_the_owner_to_connect_anything(machine):
    lines = env.summarise(env.discover(machine))
    joined = "".join(lines)
    for begging in ("接続して", "連携して", "設定して", "追加してください", "ログインして"):
        assert begging not in joined


def test_the_summary_leads_with_understanding(machine):
    lines = env.summarise(env.discover(machine))
    assert lines[0].startswith("会社の把握度")
    assert "60%" in lines[0]

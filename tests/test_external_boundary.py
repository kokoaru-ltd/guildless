import json
from datetime import UTC, datetime, timedelta

import pytest

from council.discovery import Bottleneck
from council.executors.form_submission import (
    Funnel,
    FormSubmissionExecutor,
    SubmissionOutcome,
    Target,
    inspect,
    strip_html,
)
from council.grant import (
    BOOTSTRAP_SCOPE,
    ExternalActionGrant,
    GrantError,
    GrantedActions,
    load,
    template,
)
from council.self_modification import ModificationRequest, SelfModificationPolicy


CLEAN_PAGE = "お問い合わせ 会社概要 サービス内容 ご相談はこちらから"


def target(**overrides):
    base = dict(
        company="株式会社テスト", url="https://example.jp/contact",
        page_text=CLEAN_PAGE, form_fields=["name", "email", "message"],
    )
    base.update(overrides)
    return Target(**base)


def grant(**overrides):
    base = dict(
        scope="b2b_outreach", channels=frozenset({"contact_form"}),
        max_contacts_per_day=20, max_contacts_per_company=1, max_spend_yen=0,
    )
    base.update(overrides)
    return ExternalActionGrant(**base)


# --- the grant is the boundary ---------------------------------------------

def test_no_grant_file_means_no_outreach(tmp_path):
    assert load(tmp_path) is None


def test_a_grant_is_read_from_a_file_a_human_wrote(tmp_path):
    (tmp_path / "external_action_grant.json").write_text(
        json.dumps({**BOOTSTRAP_SCOPE, "granted_by": "kyant"}), encoding="utf-8"
    )
    loaded = load(tmp_path)
    assert loaded.scope == "b2b_outreach"
    assert loaded.channels == frozenset({"contact_form"})
    assert loaded.max_spend_yen == 0


def test_an_incomplete_grant_is_refused_rather_than_guessed(tmp_path):
    (tmp_path / "external_action_grant.json").write_text('{"scope":"x"}', encoding="utf-8")
    with pytest.raises(GrantError):
        load(tmp_path)


def test_a_grant_cannot_be_mutated():
    with pytest.raises(Exception):
        grant().max_contacts_per_day = 10_000  # type: ignore[misc]


def test_a_channel_outside_the_grant_is_refused():
    ok, reason = grant().check(
        channel="email_cold", spend_yen=0, contacts_today=0, contacts_for_company=0
    )
    assert ok is False and "経路" in reason


def test_spending_beyond_the_grant_is_refused():
    ok, reason = grant().check(
        channel="contact_form", spend_yen=1, contacts_today=0, contacts_for_company=0
    )
    assert ok is False and "上限" in reason


def test_the_daily_cap_is_enforced():
    ok, _ = grant().check(
        channel="contact_form", spend_yen=0, contacts_today=20, contacts_for_company=0
    )
    assert ok is False


def test_one_contact_per_company():
    ok, _ = grant().check(
        channel="contact_form", spend_yen=0, contacts_today=0, contacts_for_company=1
    )
    assert ok is False


def test_an_expired_grant_permits_nothing():
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    ok, reason = grant(expires_at=past).check(
        channel="contact_form", spend_yen=0, contacts_today=0, contacts_for_company=0
    )
    assert ok is False and "期限" in reason


def test_an_unreadable_expiry_fails_closed():
    assert grant(expires_at="いつか").expired() is True


def test_within_scope_no_further_confirmation_is_required():
    ok, _ = grant().check(
        channel="contact_form", spend_yen=0, contacts_today=5, contacts_for_company=0
    )
    assert ok is True


def test_counts_drive_the_limits():
    used = GrantedActions()
    used.record("2026-08-16", "株式会社A")
    assert used.contacts_today("2026-08-16") == 1
    assert used.contacts_for("株式会社A") == 1
    assert used.contacts_for("株式会社B") == 0


def test_the_template_tells_the_human_what_granting_means():
    assert "再確認は行いません" in template()["_note"]


# --- the system cannot widen its own permissions ---------------------------

@pytest.mark.parametrize(
    "path",
    ["council/grant.py", "council/human_role.py", "council/capital.py",
     "council/gates.py", "council/self_modification.py"],
)
def test_self_modification_cannot_touch_the_boundary(path):
    request = ModificationRequest(
        bottleneck=Bottleneck("outreach", "営業", "1日20件では足りない"),
        rationale="接触上限が実験の完了を妨げているため引き上げる",
        apply=lambda: None,
        revert=lambda: None,
        targets=(path,),
    )
    result = SelfModificationPolicy().evaluate(request)
    assert result.allowed is False
    assert "自己改造できません" in result.reason


def test_a_windows_style_path_is_still_protected():
    request = ModificationRequest(
        bottleneck=Bottleneck("x", "y", "z"), rationale="ボトルネック解消",
        apply=lambda: None, revert=lambda: None,
        targets=(r"council\grant.py",),
    )
    assert SelfModificationPolicy().evaluate(request).allowed is False


def test_ordinary_modules_remain_modifiable():
    request = ModificationRequest(
        bottleneck=Bottleneck("crawling", "顧客探索", "1件40秒かかる"),
        rationale="顧客探索が遅く戦略が完走しないため並列化する",
        apply=lambda: None, revert=lambda: None,
        targets=("council/strategy_factory.py",),
    )
    assert SelfModificationPolicy().evaluate(request).allowed is True


# --- inspection before submission ------------------------------------------

@pytest.mark.parametrize("phrase", ["営業お断り", "勧誘お断り", "no solicitation"])
def test_a_site_refusing_sales_is_skipped(phrase):
    verdict = inspect(target(page_text=f"{CLEAN_PAGE} {phrase}"))
    assert verdict.decision == "skip"
    assert verdict.rule == "sales_prohibited"


@pytest.mark.parametrize("phrase", ["採用に関するお問い合わせ", "既存のお客様専用", "報道関係者の方へ"])
def test_a_purpose_restricted_form_is_skipped(phrase):
    assert inspect(target(page_text=f"{CLEAN_PAGE} {phrase}")).rule == "purpose_restricted"


@pytest.mark.parametrize("phrase", ["recaptcha", "hcaptcha", "画像認証"])
def test_anti_bot_controls_are_never_bypassed(phrase):
    assert inspect(target(page_text=f"{CLEAN_PAGE} {phrase}")).rule == "anti_bot"


def test_a_login_wall_is_not_worked_around():
    assert inspect(target(page_text=f"{CLEAN_PAGE} ログインしてください")).rule == "login_required"


def test_an_unreadable_page_is_skipped_not_guessed():
    assert inspect(target(page_text="")).rule == "unreadable"


def test_a_page_with_no_form_is_skipped():
    assert inspect(target(form_fields=[])).rule == "no_form"


def test_a_previous_opt_out_is_permanent():
    assert inspect(target(previously_opted_out=True)).rule == "opt_out"


def test_an_irrelevant_target_is_skipped():
    verdict = inspect(target(), relevance=lambda t: False)
    assert verdict.rule == "not_relevant"


def test_a_clean_public_form_is_eligible():
    assert inspect(target()).decision == "eligible"


def test_html_is_stripped_before_reading_policy():
    text = strip_html("<script>var x=1</script><p>営業お断り</p>")
    assert "営業お断り" in text and "var x" not in text


# --- submission counts only when confirmed ---------------------------------

class Request:
    def __init__(self, url, payload=None):
        self.target = url
        self.payload = payload or {"message": "ご提案"}


def executor(page_text=CLEAN_PAGE, outcome=None, funnel=None, fetch_error=False):
    def fetch(url):
        if fetch_error:
            raise ConnectionError("unreachable")
        return target(url=url, page_text=page_text)

    return FormSubmissionExecutor(
        fetch=fetch,
        submit=lambda t, p: outcome or SubmissionOutcome(True, "ok", "送信しました"),
        funnel=funnel or Funnel(),
    )


def test_a_confirmed_submission_counts():
    run = executor()
    result = run(Request("https://example.jp/contact"))
    assert result["submitted"] is True
    assert run.funnel.submitted == 1
    assert run.funnel.eligible == 1


def test_an_http_success_without_confirmation_is_not_a_submission():
    run = executor(outcome=SubmissionOutcome(True, "HTTP 200", confirmation=""))
    with pytest.raises(RuntimeError, match="送信確認"):
        run(Request("https://example.jp/contact"))
    assert run.funnel.submitted == 0
    assert run.funnel.skips["unconfirmed"] == 1


def test_a_refused_site_never_reaches_submission():
    run = executor(page_text=f"{CLEAN_PAGE} 営業お断り")
    with pytest.raises(RuntimeError, match="営業"):
        run(Request("https://example.jp/contact"))
    assert run.funnel.attempted == 0
    assert run.funnel.skips["sales_prohibited"] == 1


def test_an_unreachable_site_is_skipped_without_asking():
    run = executor(fetch_error=True)
    with pytest.raises(RuntimeError, match="取得できない"):
        run(Request("https://example.jp/contact"))
    assert run.funnel.skips["fetch_failed"] == 1


def test_the_funnel_separates_every_stage():
    funnel = Funnel()
    executor(funnel=funnel)(Request("https://a.jp"))
    try:
        executor(page_text=f"{CLEAN_PAGE} 採用情報", funnel=funnel)(Request("https://b.jp"))
    except RuntimeError:
        pass
    counts = funnel.as_dict()
    assert counts["discovered"] == 2
    assert counts["eligible"] == 1
    assert counts["submitted"] == 1
    assert counts["blocked"] == 1
    assert counts["replied"] == 0
    assert counts["converted"] == 0

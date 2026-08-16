import pytest

from council.action_gateway import ActionGateway, ActionRequest
from council.capital import CapitalAllocator


@pytest.fixture
def capital(tmp_path):
    return CapitalAllocator(tmp_path / "capital.json", initial_cash_yen=10_000)


@pytest.fixture
def gateway(tmp_path, capital):
    return ActionGateway(tmp_path / "actions.json", capital, dry_run=False)


def mail(key="m1", target="a@example.com", amount=0):
    return ActionRequest(
        kind="send_email", idempotency_key=key, target=target,
        purpose="初回営業", amount_yen=amount,
    )


def sent(request):
    return {"provider_id": "msg-1"}


def test_dry_run_is_the_default_so_wiring_it_up_sends_nothing(tmp_path, capital):
    guarded = ActionGateway(tmp_path / "actions.json", capital)
    result = guarded.execute(mail(), sent)
    assert result.status == "denied"
    assert result.detail["dry_run"] is True
    assert guarded.executed_count() == 0


def test_an_executed_action_is_recorded(gateway):
    result = gateway.execute(mail(), sent)
    assert result.ok is True
    assert result.detail["provider_id"] == "msg-1"
    assert gateway.executed_count("send_email") == 1


def test_the_same_key_never_sends_twice(gateway):
    calls = []

    def counting(request):
        calls.append(request.idempotency_key)
        return {}

    gateway.execute(mail("same"), counting)
    second = gateway.execute(mail("same"), counting)
    assert second.status == "duplicate"
    assert calls == ["same"]


def test_a_denied_action_may_be_retried_because_nothing_happened(gateway):
    gateway.policy = lambda request: "規約未確認"
    first = gateway.execute(mail("k"), sent)
    assert first.status == "denied"

    gateway.policy = None
    second = gateway.execute(mail("k"), sent)
    assert second.ok is True


def test_policy_refusal_blocks_the_send(gateway):
    gateway.policy = lambda request: "特定電子メール法の同意記録がありません"
    result = gateway.execute(mail(), sent)
    assert result.status == "denied"
    assert "特定電子メール法" in result.reason


def test_an_unaffordable_action_never_reaches_the_executor(gateway):
    reached = []
    result = gateway.execute(
        mail(amount=99_999), lambda request: reached.append(1) or {}
    )
    assert result.status == "denied"
    assert reached == []


def test_money_is_committed_only_after_the_action_succeeds(gateway, capital):
    gateway.execute(mail(amount=500), lambda request: {"actual_cost_yen": 320})
    assert capital.spent_yen == 320
    assert capital.state.envelopes["experiment"].reserved_yen == 0


def test_a_failing_executor_gives_the_money_back(gateway, capital):
    def broken(request):
        raise RuntimeError("SMTP down")

    result = gateway.execute(mail(amount=500), broken)
    assert result.status == "failed"
    assert "SMTP down" in result.reason
    assert capital.spent_yen == 0
    assert capital.state.envelopes["experiment"].reserved_yen == 0


def test_an_unhealthy_provider_blocks_the_send_and_frees_the_money(gateway, capital):
    gateway.health = lambda request: "送信プロバイダが応答しません"
    result = gateway.execute(mail(amount=500), sent)
    assert result.status == "denied"
    assert capital.spent_yen == 0
    assert capital.state.envelopes["experiment"].reserved_yen == 0


def test_one_prospect_cannot_be_hammered(gateway):
    for index in range(3):
        assert gateway.execute(mail(f"k{index}", "same@example.com"), sent).ok is True
    blocked = gateway.execute(mail("k3", "same@example.com"), sent)
    assert blocked.status == "denied"
    assert "上限" in blocked.reason


def test_the_contact_limit_is_per_target(gateway):
    for index in range(3):
        gateway.execute(mail(f"a{index}", "one@example.com"), sent)
    assert gateway.execute(mail("b0", "two@example.com"), sent).ok is True


def test_history_survives_a_restart(tmp_path, capital):
    path = tmp_path / "actions.json"
    first = ActionGateway(path, capital, dry_run=False)
    first.execute(mail("k1"), sent)

    reopened = ActionGateway(path, capital, dry_run=False)
    assert reopened.executed_count() == 1
    assert reopened.execute(mail("k1"), sent).status == "duplicate"

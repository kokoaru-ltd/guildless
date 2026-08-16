from council.human_role import (
    may_ask_human,
    residual_action_count,
    unnecessary_human_work,
)


def test_kyc_is_human_work_even_though_it_is_digital():
    """The old physical-only rule would have blocked this and frozen payments."""
    ruling = may_ask_human("identity_verification")
    assert ruling.allowed is True
    assert "本人確認" in ruling.reason


def test_terms_consent_and_signature_stay_with_a_person():
    assert may_ask_human("terms_consent").allowed is True
    assert may_ask_human("legal_signature").allowed is True


def test_physical_tasks_remain_human():
    assert may_ask_human("physical_world_task").allowed is True


def test_writing_sales_copy_may_not_be_handed_to_a_human():
    ruling = may_ask_human("write_copy")
    assert ruling.allowed is False
    assert "商品として成立しません" in ruling.reason


def test_sending_and_support_are_machine_work():
    assert may_ask_human("send_message").allowed is False
    assert may_ask_human("customer_support").allowed is False


def test_unclassified_work_defaults_to_automate_first():
    assert may_ask_human("something_new").allowed is False


def test_residual_count_only_counts_legitimate_human_steps():
    tasks = ["identity_verification", "terms_consent", "write_copy", "send_message"]
    assert residual_action_count(tasks) == 2


def test_unnecessary_human_work_is_named():
    tasks = ["identity_verification", "write_copy", "bookkeeping"]
    assert unnecessary_human_work(tasks) == ["write_copy", "bookkeeping"]


def test_a_fully_absorbed_product_leaves_only_consent():
    assert residual_action_count(["terms_consent"]) == 1
    assert unnecessary_human_work(["terms_consent"]) == []

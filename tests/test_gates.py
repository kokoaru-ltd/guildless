import pytest

from council.gates import GateError, current_level, locked_capabilities, require


# --- G0: nothing sold yet ---------------------------------------------------

def test_a_company_with_no_revenue_is_at_g0():
    status = current_level(real_payments=0)
    assert status.level == "G0"


def test_g0_allows_everything_that_can_produce_a_sale():
    for capability in (
        "web_research", "offer_hypothesis", "delivery_proof",
        "customer_search", "outreach", "payment", "delivery",
    ):
        require(capability, real_payments=0)


def test_virtual_market_is_physically_blocked_at_g0():
    with pytest.raises(GateError) as raised:
        require("virtual_market", real_payments=0)
    assert "G3" in str(raised.value)


def test_the_whole_simulation_stack_is_blocked_at_g0():
    for capability in (
        "virtual_market", "customer_simulator", "counterfactual",
        "snapshot_fork_replay", "skill_evolution", "correction_compiler",
    ):
        with pytest.raises(GateError):
            require(capability, real_payments=0)


def test_a_persuasive_argument_does_not_open_a_gate():
    """The gate reads payments, not reasoning. There is no override."""
    with pytest.raises(GateError):
        require("virtual_market", real_payments=0)


def test_unknown_capability_is_denied_by_default():
    with pytest.raises(GateError) as raised:
        require("build_something_impressive", real_payments=0)
    assert "未登録" in str(raised.value)


# --- G1: first payment ------------------------------------------------------

def test_one_payment_reaches_g1():
    assert current_level(real_payments=1).level == "G1"


def test_one_payment_unlocks_only_simple_modelling():
    require("simple_customer_model", real_payments=1)
    with pytest.raises(GateError):
        require("virtual_market", real_payments=1)


def test_one_payment_does_not_unlock_the_correction_compiler():
    with pytest.raises(GateError):
        require("correction_compiler", real_payments=1)


# --- G2: a few payments -----------------------------------------------------

def test_three_payments_reach_g2():
    assert current_level(real_payments=3).level == "G2"


def test_g2_unlocks_comparison_and_correction():
    require("skill_comparison", real_payments=3)
    require("correction_compiler", real_payments=3)


def test_g2_still_blocks_the_simulator():
    with pytest.raises(GateError):
        require("virtual_market", real_payments=5)


# --- G3: enough real data ---------------------------------------------------

def test_payments_alone_do_not_reach_g3():
    """Ten sales off five conversations is not a market model."""
    assert current_level(real_payments=10, real_contacts=5).level == "G2"


def test_g3_needs_both_payments_and_contact_volume():
    status = current_level(real_payments=10, real_contacts=50)
    assert status.level == "G3"
    require("virtual_market", real_payments=10, real_contacts=50)
    require("snapshot_fork_replay", real_payments=10, real_contacts=50)


# --- reporting --------------------------------------------------------------

def test_locked_list_shrinks_as_revenue_arrives():
    at_zero = locked_capabilities(real_payments=0)
    at_three = locked_capabilities(real_payments=3)
    assert "virtual_market" in at_zero
    assert "correction_compiler" in at_zero
    assert "correction_compiler" not in at_three
    assert len(at_three) < len(at_zero)


def test_nothing_is_locked_at_g3():
    assert locked_capabilities(real_payments=10, real_contacts=50) == []

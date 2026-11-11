import pandas as pd
import pytest

from alphafund.trading_workflow import (
    build_workflow_snapshot, check_risk, create_trade_plan,
    historical_trade_replay, size_position,
)


def make_plan():
    return create_trade_plan("RELIANCE", "NSE", "LONG", 1000, 980, 1040, "breakout", "1d")


def test_plan_validates_direction_and_prices():
    plan = make_plan()
    assert plan.reward_risk == 2
    with pytest.raises(ValueError):
        create_trade_plan("RELIANCE", "NSE", "LONG", 1000, 1010, 1040)


def test_position_size_uses_tightest_cap():
    plan = make_plan()
    result = size_position(plan, budget=100000, max_loss=1000,
                           max_position_pct=50, cash_buffer_pct=10)
    assert result["approved"]
    assert result["units"] == 50
    assert result["binding_limit"] == "max_loss"
    assert result["max_loss_at_stop"] == 1000


def test_risk_gate_blocks_bad_reward_risk_and_daily_overrun():
    plan = create_trade_plan("ABC", "NSE", "LONG", 100, 95, 105)
    sizing = size_position(plan, budget=10000, max_loss=500)
    verdict = check_risk(plan, sizing, max_loss_per_trade=500,
                         min_reward_risk=1.5, max_daily_loss=600,
                         daily_risk_committed=200)
    assert verdict["status"] == "BLOCK"
    assert any("Reward/risk" in reason for reason in verdict["reasons"])
    assert any("daily risk" in reason for reason in verdict["reasons"])


def test_risk_gate_pass_is_not_execution_authorization():
    plan = make_plan()
    sizing = size_position(plan, budget=100000, max_loss=1000)
    verdict = check_risk(plan, sizing, max_loss_per_trade=1000)
    assert verdict["status"] == "PASS"
    assert verdict["is_execution_authorization"] is False


def test_historical_replay_counts_outcomes_and_discloses_limits():
    plan = create_trade_plan("ABC", "NSE", "LONG", 100, 95, 105)
    history = pd.DataFrame({"Close": [100, 101, 106, 100, 94, 99, 102, 103]})
    result = historical_trade_replay(plan, history, max_bars=3)
    assert result["observations"] > 0
    assert sum(result["outcome_counts"].values()) == result["observations"]
    assert "not a forecast" in result["warning"]


def test_snapshot_always_disables_execution():
    snapshot = build_workflow_snapshot(plan=make_plan())
    assert snapshot["execution"] == {
        "enabled": False, "broker_connected": False, "orders_sent": False
    }

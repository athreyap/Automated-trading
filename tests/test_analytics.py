import pandas as pd

from alphafund.analytics import allocation_by, groww_holdings_frame, holdings_frame, portfolio_summary


def test_holdings_summary_excludes_unknown_costs_without_imputing():
    frame = holdings_frame([
        {"instrument": "Reliance", "identifier": "RELIANCE", "asset_type": "equity",
         "quantity": 2, "average_cost": 100, "as_of_date": "2026-11-03"},
        {"instrument": "Gold fund", "identifier": "GOLDFUND", "asset_type": "mutual_fund",
         "quantity": 5, "average_cost": None, "as_of_date": "2026-11-03"},
    ])
    summary = portfolio_summary(frame)
    assert summary["holding_count"] == 2
    assert summary["cost_basis"] == 200
    assert summary["known_cost_count"] == 1
    assert summary["missing_cost_count"] == 1
    assert summary["cost_coverage_pct"] == 50


def test_allocation_groups_cost_basis_by_asset_type():
    frame = holdings_frame([
        {"instrument": "A", "asset_type": "equity", "quantity": 2, "average_cost": 100},
        {"instrument": "B", "asset_type": "equity", "quantity": 1, "average_cost": 50},
        {"instrument": "C", "asset_type": "bond", "quantity": 1, "average_cost": 200},
    ])
    result = allocation_by(frame, "asset_type")
    assert result.iloc[0]["asset_type"] == "equity"
    assert result.iloc[0]["cost_basis"] == 250
    assert result.iloc[1]["cost_basis"] == 250


def test_groww_normalizes_cost_value():
    frame = groww_holdings_frame([{"quantity": "2", "average_price": "125"}])
    assert frame.iloc[0]["invested_value"] == 250

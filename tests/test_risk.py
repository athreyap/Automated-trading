import numpy as np
import pandas as pd
import pytest

from alphafund.risk import parse_weighted_symbols, calculate_portfolio_risk, evaluate_price_alert


def test_parse_weighted_symbols_normalizes_and_rejects_bad_values():
    parsed = parse_weighted_symbols("reliance:60, TCS:40")
    assert parsed == {"RELIANCE": 60.0, "TCS": 40.0}
    with pytest.raises(ValueError):
        parse_weighted_symbols("RELIANCE:0")
    with pytest.raises(ValueError):
        parse_weighted_symbols("RELIANCE:20,RELIANCE:80")


def test_portfolio_risk_uses_weighted_returns_and_reports_tail_metrics():
    index = pd.date_range("2025-01-01", periods=150, freq="B")
    a = 100 * np.cumprod(1 + np.sin(np.arange(150)) * 0.002 + 0.0004)
    b = 80 * np.cumprod(1 + np.cos(np.arange(150)) * 0.003 + 0.0002)
    matrix = pd.DataFrame({"A": a, "B": b}, index=index)
    result = calculate_portfolio_risk(matrix, {"A": 70, "B": 30})
    assert result["observations"] >= 100
    assert result["annualised_volatility_pct"] > 0
    assert result["historical_cvar_pct"] >= result["historical_var_pct"]
    assert abs(sum(result["weights_pct"].values()) - 100) < 1e-8


def test_price_alert_only_triggers_on_crossing():
    assert evaluate_price_alert(105, 99, 100, "above")["triggered"] is True
    assert evaluate_price_alert(105, 101, 100, "above")["triggered"] is False
    assert evaluate_price_alert(95, 101, 100, "below")["triggered"] is True

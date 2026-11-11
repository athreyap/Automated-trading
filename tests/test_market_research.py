import pandas as pd
import pytest

from alphafund.market_research import (
    yahoo_symbol,
    add_research_indicators,
    analyse_history,
    research_backtest,
)


def sample_prices(rows=320):
    index = pd.date_range("2024-01-01", periods=rows, freq="B")
    close = pd.Series(range(100, 100 + rows), index=index, dtype=float)
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1.0,
        "Low": close - 1.0,
        "Close": close,
        "Volume": 10000,
    }, index=index)


def test_market_symbol_mapping():
    assert yahoo_symbol("RELIANCE", "NSE") == "RELIANCE.NS"
    assert yahoo_symbol("500325", "BSE") == "500325.BO"
    assert yahoo_symbol("AAPL", "US") == "AAPL"
    assert yahoo_symbol("TCS.NS", "NSE") == "TCS.NS"


def test_market_symbol_rejects_wrong_exchange_suffix():
    with pytest.raises(ValueError):
        yahoo_symbol("RELIANCE.NS", "BSE")


def test_indicators_and_analysis_are_computed():
    prices = sample_prices()
    enriched = add_research_indicators(prices)
    assert {"SMA_20", "SMA_50", "SMA_200", "RSI_14", "MACD", "ATR_14"}.issubset(enriched.columns)
    metrics = analyse_history(prices)
    assert metrics["observations"] > 0
    assert metrics["technical_score_max"] == 5
    assert metrics["close"] > 0


def test_backtest_has_lagged_strategy_and_benchmark_outputs():
    result = research_backtest(sample_prices(), fee_bps=10)
    assert "Strategy" in result["equity_curve"]
    assert "Buy & hold" in result["equity_curve"]
    assert result["trade_entries"] >= 0
    assert result["fee_bps"] == 10

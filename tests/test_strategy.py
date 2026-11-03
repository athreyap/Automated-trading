import pandas as pd
from alphafund.strategy import add_indicators, latest_signal, backtest

def sample_data(n=100):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(range(100, 100+n), index=idx, dtype=float)
    return pd.DataFrame({
        "Open": close, "High": close + 1, "Low": close - 1,
        "Close": close, "Volume": 10000
    }, index=idx)

def test_indicators_added():
    result = add_indicators(sample_data())
    assert {"SMA_20", "SMA_50", "RSI_14"}.issubset(result.columns)

def test_latest_signal_has_reason():
    result = latest_signal(sample_data())
    assert result["signal"] in {"BUY", "SELL", "WAIT"}
    assert result["reason"]

def test_backtest_returns_finite_value():
    result = backtest(sample_data())
    assert result["final_value"] > 0
    assert isinstance(result["trades"], int)

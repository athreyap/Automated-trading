from __future__ import annotations
import pandas as pd

def add_indicators(data: pd.DataFrame) -> pd.DataFrame:
    if "Close" not in data:
        raise ValueError("Data must contain a Close column.")
    out = data.copy()
    close = out["Close"].astype(float)
    out["SMA_20"] = close.rolling(20).mean()
    out["SMA_50"] = close.rolling(50).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["RSI_14"] = 100 - (100 / (1 + rs))
    out["RSI_14"] = out["RSI_14"].fillna(50)
    return out

def latest_signal(data: pd.DataFrame) -> dict:
    enriched = add_indicators(data).dropna(subset=["SMA_20", "SMA_50"])
    if enriched.empty:
        return {"signal": "WAIT", "reason": "At least 50 daily observations are needed."}
    row = enriched.iloc[-1]
    if row["Close"] > row["SMA_20"] > row["SMA_50"] and row["RSI_14"] < 70:
        signal, reason = "BUY", "Price is above the 20/50-day averages and RSI is below 70."
    elif row["Close"] < row["SMA_20"] < row["SMA_50"] or row["RSI_14"] > 75:
        signal, reason = "SELL", "Trend or momentum conditions are bearish/overbought."
    else:
        signal, reason = "WAIT", "The trend and momentum filters do not agree."
    return {
        "signal": signal,
        "reason": reason,
        "close": float(row["Close"]),
        "sma20": float(row["SMA_20"]),
        "sma50": float(row["SMA_50"]),
        "rsi": float(row["RSI_14"]),
        "date": str(enriched.index[-1]),
    }

def backtest(data: pd.DataFrame, starting_cash: float = 900.0) -> dict:
    """Long-only moving-average regime backtest; no leverage or shorting."""
    frame = add_indicators(data).dropna(subset=["SMA_20", "SMA_50"]).copy()
    if len(frame) < 2:
        return {"final_value": starting_cash, "return_pct": 0.0, "trades": 0}
    frame["position"] = ((frame["Close"] > frame["SMA_20"]) &
                         (frame["SMA_20"] > frame["SMA_50"])).astype(int)
    # Signals are lagged one bar to avoid look-ahead bias.
    daily_returns = frame["Close"].pct_change().fillna(0)
    strategy_returns = daily_returns * frame["position"].shift(1).fillna(0)
    equity = starting_cash * (1 + strategy_returns).cumprod()
    changes = frame["position"].diff().fillna(frame["position"])
    return {
        "final_value": float(equity.iloc[-1]),
        "return_pct": float((equity.iloc[-1] / starting_cash - 1) * 100),
        "trades": int((changes != 0).sum()),
        "equity": equity,
    }

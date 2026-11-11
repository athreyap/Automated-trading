"""Multi-market equity research primitives for AlphaFund.

Uses Yahoo Finance through yfinance for indicative historical data. This module
is research-only: it does not place orders and does not produce guaranteed forecasts.
"""
from __future__ import annotations

import math
from typing import Iterable

import pandas as pd
import yfinance as yf


MARKETS = {
    "NSE": {"suffix": ".NS", "currency": "INR", "label": "India · NSE"},
    "BSE": {"suffix": ".BO", "currency": "INR", "label": "India · BSE"},
    "US": {"suffix": "", "currency": "USD", "label": "United States · NYSE / NASDAQ"},
}


def yahoo_symbol(symbol: str, market: str) -> str:
    market = market.upper()
    if market not in MARKETS:
        raise ValueError("Market must be NSE, BSE or US.")
    value = symbol.strip().upper()
    if not value:
        raise ValueError("Enter a ticker symbol.")
    suffix = MARKETS[market]["suffix"]
    if market == "US":
        return value
    if value.endswith((".NS", ".BO")):
        expected = suffix
        if not value.endswith(expected):
            raise ValueError(f"{value} does not match the selected {market} market.")
        return value
    return value + suffix


def fetch_market_history(symbol: str, market: str, period: str = "2y",
                         interval: str = "1d") -> tuple[str, pd.DataFrame]:
    ticker = yahoo_symbol(symbol, market)
    frame = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    if frame is None or frame.empty:
        raise ValueError(f"No data returned for {ticker}. Verify the exchange ticker or try later.")
    frame = frame.rename(columns={c: str(c).title() for c in frame.columns})
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError("Market data missing: " + ", ".join(missing))
    frame = frame[required].dropna(subset=["Close"]).copy()
    if len(frame) < 60:
        raise ValueError(f"Only {len(frame)} observations returned; at least 60 are required.")
    return ticker, frame


def add_research_indicators(data: pd.DataFrame) -> pd.DataFrame:
    if "Close" not in data:
        raise ValueError("Historical data must include Close.")
    out = data.copy()
    close = pd.to_numeric(out["Close"], errors="coerce")
    high = pd.to_numeric(out["High"], errors="coerce")
    low = pd.to_numeric(out["Low"], errors="coerce")
    volume = pd.to_numeric(out["Volume"], errors="coerce")
    out["SMA_20"] = close.rolling(20).mean()
    out["SMA_50"] = close.rolling(50).mean()
    out["SMA_200"] = close.rolling(200).mean()
    out["EMA_12"] = close.ewm(span=12, adjust=False).mean()
    out["EMA_26"] = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = out["EMA_12"] - out["EMA_26"]
    out["MACD_SIGNAL"] = out["MACD"].ewm(span=9, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["RSI_14"] = (100 - 100 / (1 + rs)).fillna(50)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    out["ATR_14"] = true_range.rolling(14).mean()
    out["BB_MID"] = close.rolling(20).mean()
    std = close.rolling(20).std()
    out["BB_UPPER"] = out["BB_MID"] + 2 * std
    out["BB_LOWER"] = out["BB_MID"] - 2 * std
    out["VOLUME_SMA_20"] = volume.rolling(20).mean()
    out["RETURN_1D"] = close.pct_change()
    out["RETURN_1M"] = close.pct_change(21)
    out["RETURN_3M"] = close.pct_change(63)
    out["RETURN_1Y"] = close.pct_change(252)
    return out


def analyse_history(data: pd.DataFrame) -> dict:
    frame = add_research_indicators(data).dropna(subset=["SMA_20", "SMA_50"])
    if frame.empty:
        raise ValueError("Not enough observations to calculate indicators.")
    row = frame.iloc[-1]
    close = float(row["Close"])
    sma20, sma50 = float(row["SMA_20"]), float(row["SMA_50"])
    sma200 = float(row["SMA_200"]) if pd.notna(row["SMA_200"]) else None
    rsi = float(row["RSI_14"])
    macd = float(row["MACD"])
    macd_signal = float(row["MACD_SIGNAL"])
    trend = "Bullish" if close > sma20 > sma50 else ("Bearish" if close < sma20 < sma50 else "Mixed")
    momentum = "Positive" if macd > macd_signal else "Negative"
    score = 0
    score += 1 if close > sma20 else -1
    score += 1 if sma20 > sma50 else -1
    score += 1 if sma200 is not None and close > sma200 else 0
    score += 1 if macd > macd_signal else -1
    score += 1 if 45 <= rsi <= 65 else (-1 if rsi > 75 or rsi < 30 else 0)
    recent = frame["Close"].pct_change().dropna()
    annual_vol = float(recent.std() * math.sqrt(252) * 100) if len(recent) > 1 else None
    drawdown = frame["Close"] / frame["Close"].cummax() - 1
    max_drawdown = float(drawdown.min() * 100)
    return {
        "as_of": str(frame.index[-1].date()),
        "close": close,
        "trend": trend,
        "momentum": momentum,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "sma20": sma20,
        "sma50": sma50,
        "sma200": sma200,
        "atr14": float(row["ATR_14"]) if pd.notna(row["ATR_14"]) else None,
        "return_1m_pct": float(row["RETURN_1M"] * 100) if pd.notna(row["RETURN_1M"]) else None,
        "return_3m_pct": float(row["RETURN_3M"] * 100) if pd.notna(row["RETURN_3M"]) else None,
        "return_1y_pct": float(row["RETURN_1Y"] * 100) if pd.notna(row["RETURN_1Y"]) else None,
        "annualised_volatility_pct": annual_vol,
        "max_drawdown_pct": max_drawdown,
        "technical_score": score,
        "technical_score_max": 5,
        "observations": int(len(frame)),
    }


def research_backtest(data: pd.DataFrame, fee_bps: float = 10.0) -> dict:
    """Long-only 20/50 SMA regime with one-bar signal lag and per-turnover costs."""
    frame = add_research_indicators(data).dropna(subset=["SMA_20", "SMA_50"]).copy()
    if len(frame) < 2:
        raise ValueError("Not enough history for a backtest.")
    frame["position"] = ((frame["Close"] > frame["SMA_20"]) &
                         (frame["SMA_20"] > frame["SMA_50"])).astype(float)
    held = frame["position"].shift(1).fillna(0.0)
    turnover = frame["position"].diff().abs().fillna(frame["position"])
    costs = turnover * (fee_bps / 10000.0)
    daily = frame["Close"].pct_change().fillna(0.0)
    strategy = daily * held - costs
    equity = (1 + strategy).cumprod()
    benchmark = (1 + daily).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    changes = frame["position"].diff().fillna(frame["position"])
    return {
        "strategy_return_pct": float((equity.iloc[-1] - 1) * 100),
        "buy_hold_return_pct": float((benchmark.iloc[-1] - 1) * 100),
        "max_drawdown_pct": float(dd.min() * 100),
        "trade_entries": int((changes > 0).sum()),
        "trade_exits": int((changes < 0).sum()),
        "equity_curve": pd.DataFrame({"Strategy": equity, "Buy & hold": benchmark}),
        "fee_bps": fee_bps,
    }


def scan_symbols(symbols: Iterable[str], market: str, period: str = "1y") -> pd.DataFrame:
    rows = []
    for raw in symbols:
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        try:
            ticker, history = fetch_market_history(symbol, market, period=period)
            result = analyse_history(history)
            rows.append({
                "Symbol": symbol, "Yahoo ticker": ticker, "As of": result["as_of"],
                "Last close": result["close"], "Trend": result["trend"],
                "RSI": round(result["rsi"], 1), "1M return %": result["return_1m_pct"],
                "3M return %": result["return_3m_pct"],
                "Technical score": f'{result["technical_score"]}/5',
            })
        except Exception as exc:
            rows.append({"Symbol": symbol, "Yahoo ticker": "", "As of": "",
                         "Last close": None, "Trend": "Unavailable", "RSI": None,
                         "1M return %": None, "3M return %": None,
                         "Technical score": "—", "Data note": str(exc)})
    return pd.DataFrame(rows)

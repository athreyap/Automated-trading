from __future__ import annotations
import pandas as pd
import yfinance as yf

def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value:
        raise ValueError("Enter a stock symbol.")
    return value if "." in value else f"{value}.NS"

def fetch_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    ticker = normalize_symbol(symbol)
    frame = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    if frame is None or frame.empty:
        raise ValueError(f"No market data returned for {ticker}. Check the symbol or try later.")
    frame = frame.rename(columns={c: c.title() for c in frame.columns})
    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"Market data is missing fields: {', '.join(missing)}")
    return frame[required].dropna(subset=["Close"])

class GrowwReadOnlyAdapter:
    """Reserved boundary for future official Groww market-data integration.

    No authentication, account access, or order placement is implemented.
    """

    def history(self, symbol: str):
        raise NotImplementedError(
            "Groww integration is not configured in V1. Use Yahoo Finance data."
        )

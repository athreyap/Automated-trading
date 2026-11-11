"""Company fundamentals and news retrieval for AlphaFund.

Yahoo Finance is an indicative third-party source. Missing fields are kept as
None rather than guessed. This module is read-only and never places orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from alphafund.market_research import yahoo_symbol


PROFILE_FIELDS = {
    "sector": "Sector",
    "industry": "Industry",
    "marketCap": "Market capitalisation",
    "trailingPE": "Trailing P/E",
    "forwardPE": "Forward P/E",
    "priceToBook": "Price / book",
    "priceToSalesTrailing12Months": "Price / sales",
    "pegRatio": "PEG ratio",
    "dividendYield": "Dividend yield",
    "returnOnEquity": "Return on equity",
    "returnOnAssets": "Return on assets",
    "profitMargins": "Profit margin",
    "operatingMargins": "Operating margin",
    "debtToEquity": "Debt / equity",
    "currentRatio": "Current ratio",
    "quickRatio": "Quick ratio",
    "revenueGrowth": "Revenue growth",
    "earningsGrowth": "Earnings growth",
    "freeCashflow": "Free cash flow",
    "beta": "Beta",
    "fiftyTwoWeekHigh": "52-week high",
    "fiftyTwoWeekLow": "52-week low",
    "currency": "Currency",
}

STATEMENT_ROWS = {
    "Total Revenue": "Revenue",
    "Operating Revenue": "Operating revenue",
    "Gross Profit": "Gross profit",
    "Operating Income": "Operating income",
    "Net Income": "Net income",
    "Basic EPS": "Basic EPS",
    "Diluted EPS": "Diluted EPS",
    "EBITDA": "EBITDA",
    "Total Assets": "Total assets",
    "Total Debt": "Total debt",
    "Stockholders Equity": "Shareholders' equity",
    "Operating Cash Flow": "Operating cash flow",
    "Free Cash Flow": "Free cash flow",
    "Capital Expenditure": "Capital expenditure",
}


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        result = float(value)
        return result if pd.notna(result) else None
    except (TypeError, ValueError):
        return None


def _statement_table(statement: pd.DataFrame | None) -> pd.DataFrame:
    """Return selected financial statement rows with newest periods first."""
    if statement is None or statement.empty:
        return pd.DataFrame()
    frame = statement.copy()
    frame.index = [str(x) for x in frame.index]
    rows = []
    for source, label in STATEMENT_ROWS.items():
        if source in frame.index:
            values = frame.loc[source]
            row = {"Metric": label}
            for period, value in values.items():
                try:
                    period_label = pd.Timestamp(period).strftime("%Y")
                except Exception:
                    period_label = str(period)
                row[period_label] = _number(value)
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def fetch_fundamentals(symbol: str, market: str) -> dict:
    """Fetch profile, valuation/quality ratios and annual financial statements."""
    ticker_symbol = yahoo_symbol(symbol, market)
    ticker = yf.Ticker(ticker_symbol)
    try:
        info = ticker.get_info()
    except Exception as exc:
        raise RuntimeError(f"Company profile unavailable for {ticker_symbol}: {type(exc).__name__}") from exc
    if not isinstance(info, dict) or not info:
        raise ValueError(f"No company profile returned for {ticker_symbol}.")
    profile = {label: info.get(key) for key, label in PROFILE_FIELDS.items() if info.get(key) is not None}
    profile["Company"] = info.get("longName") or info.get("shortName") or ticker_symbol
    profile["Ticker"] = ticker_symbol

    statements = {}
    statement_sources = {
        "Income statement": ("income_stmt", "financials"),
        "Balance sheet": ("balance_sheet",),
        "Cash flow": ("cashflow",),
    }
    for label, attributes in statement_sources.items():
        statement = None
        for attribute in attributes:
            try:
                candidate = getattr(ticker, attribute)
                if candidate is not None and not candidate.empty:
                    statement = candidate
                    break
            except Exception:
                continue
        statements[label] = _statement_table(statement)

    available = sum(not table.empty for table in statements.values())
    warnings = []
    if available < len(statements):
        warnings.append("Some financial statements are unavailable for this ticker.")
    if not profile.get("trailingPE") and not profile.get("forwardPE"):
        warnings.append("P/E valuation data is not supplied by the data provider.")
    return {
        "profile": profile,
        "statements": statements,
        "statement_coverage": f"{available}/{len(statements)}",
        "warnings": warnings,
        "source": "Yahoo Finance via yfinance",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _news_content(item: dict) -> dict:
    """Support both newer nested yfinance news payloads and legacy payloads."""
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    title = content.get("title") or item.get("title")
    summary = content.get("summary") or item.get("summary") or ""
    provider = content.get("provider") or {}
    publisher = provider.get("displayName") if isinstance(provider, dict) else None
    publisher = publisher or item.get("publisher") or "Unknown publisher"
    canonical = content.get("canonicalUrl") or {}
    link = canonical.get("url") if isinstance(canonical, dict) else None
    link = link or item.get("link") or item.get("url")
    pub_date = content.get("pubDate") or item.get("providerPublishTime")
    if isinstance(pub_date, (int, float)):
        published = datetime.fromtimestamp(pub_date, tz=timezone.utc).isoformat(timespec="minutes")
    else:
        published = str(pub_date) if pub_date else "Date unavailable"
    return {
        "title": str(title).strip() if title else "",
        "publisher": publisher,
        "published": published,
        "summary": str(summary).strip(),
        "link": link,
    }


def fetch_company_news(symbol: str, market: str, limit: int = 10) -> list[dict]:
    """Fetch recent provider-indexed company headlines; no sentiment is inferred."""
    ticker_symbol = yahoo_symbol(symbol, market)
    ticker = yf.Ticker(ticker_symbol)
    try:
        raw = ticker.get_news(count=max(1, min(int(limit), 25)))
    except Exception:
        try:
            raw = ticker.news
        except Exception as exc:
            raise RuntimeError(f"Company news unavailable for {ticker_symbol}: {type(exc).__name__}") from exc
    if not isinstance(raw, list):
        return []
    items = [_news_content(item) for item in raw if isinstance(item, dict)]
    return [item for item in items if item["title"]][:limit]

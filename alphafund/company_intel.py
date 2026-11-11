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



def score_company_fundamentals(profile: dict) -> dict:
    """Transparent screening score from reported ratios; never a fair-value model.

    Each pillar is scored only from available inputs. The composite is the
    mean of available pillar scores, so missing data is not treated as zero.
    """
    pillars: dict[str, dict] = {}

    def add(pillar: str, rules: list[tuple[str, callable]]) -> None:
        values = []
        used = []
        for label, rule in rules:
            raw = profile.get(label)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if not pd.notna(value):
                continue
            values.append(100.0 if rule(value) else 0.0)
            used.append(label)
        if values:
            pillars[pillar] = {
                "score": round(sum(values) / len(values), 1),
                "coverage": len(values),
                "inputs": used,
            }

    add("Profitability", [
        ("Return on equity", lambda x: x > 0.12),
        ("Profit margin", lambda x: x > 0.08),
        ("Operating margin", lambda x: x > 0.10),
    ])
    add("Balance-sheet strength", [
        ("Debt / equity", lambda x: x < 100),
        ("Current ratio", lambda x: x >= 1.2),
        ("Quick ratio", lambda x: x >= 1.0),
    ])
    add("Growth", [
        ("Revenue growth", lambda x: x > 0.05),
        ("Earnings growth", lambda x: x > 0.05),
    ])
    add("Valuation discipline", [
        ("Trailing P/E", lambda x: 0 < x < 30),
        ("Forward P/E", lambda x: 0 < x < 25),
        ("Price / book", lambda x: 0 < x < 5),
        ("PEG ratio", lambda x: 0 < x < 2),
    ])
    composite = round(sum(item["score"] for item in pillars.values()) / len(pillars), 1) if pillars else None
    flags = []
    if profile.get("Debt / equity") is not None and float(profile["Debt / equity"]) >= 200:
        flags.append("Reported debt/equity is high under this screening threshold.")
    if profile.get("Current ratio") is not None and float(profile["Current ratio"]) < 1:
        flags.append("Reported current ratio is below 1.")
    if profile.get("Profit margin") is not None and float(profile["Profit margin"]) < 0:
        flags.append("Reported profit margin is negative.")
    if profile.get("Trailing P/E") is not None and float(profile["Trailing P/E"]) <= 0:
        flags.append("Trailing P/E is non-positive; earnings may be negative or the ratio may be unavailable.")
    return {
        "composite_score": composite,
        "pillars": pillars,
        "coverage": f"{len(pillars)}/4 pillars",
        "flags": flags,
        "methodology": "Equal-weight pass/fail screens within each available pillar; equal-weight mean across available pillars. Thresholds are heuristic and not sector-adjusted.",
    }

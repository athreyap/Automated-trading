"""Exportable, reproducible AlphaFund research reports."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "Not available"
    try:
        return f"{float(value):,.2f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def build_research_report(title: str, market: str, symbol: str,
                          technical: dict | None = None,
                          fundamentals: dict | None = None,
                          screening: dict | None = None,
                          news: list[dict] | None = None,
                          risk: dict | None = None) -> str:
    """Create a Markdown report with sources, timestamps and explicit caveats."""
    lines = [
        f"# {title}",
        "",
        f"- Security: **{symbol}**",
        f"- Market: **{market}**",
        f"- Generated (UTC): **{datetime.now(timezone.utc).isoformat(timespec='seconds')}**",
        "",
        "> Research material only. Not investment advice, a target price, or an instruction to trade.",
    ]
    if technical:
        lines += ["", "## Technical research",
            f"- As of: {_fmt(technical.get('as_of'))}",
            f"- Last close: {_fmt(technical.get('close'))}",
            f"- Trend: {_fmt(technical.get('trend'))}",
            f"- Momentum: {_fmt(technical.get('momentum'))}",
            f"- RSI (14): {_fmt(technical.get('rsi'))}",
            f"- Technical score: {_fmt(technical.get('technical_score'))}/{_fmt(technical.get('technical_score_max'))}",
            f"- Annualised volatility: {_fmt(technical.get('annualised_volatility_pct'), '%')}",
            f"- Historical max drawdown: {_fmt(technical.get('max_drawdown_pct'), '%')}",
        ]
    if fundamentals:
        profile = fundamentals.get("profile", {})
        lines += ["", "## Company fundamentals",
                  f"- Company: {_fmt(profile.get('Company'))}",
                  f"- Sector / industry: {_fmt(profile.get('Sector'))} / {_fmt(profile.get('Industry'))}",
                  f"- Source: {_fmt(fundamentals.get('source'))}",
                  f"- Retrieved: {_fmt(fundamentals.get('retrieved_at_utc'))}"]
        for key in ("Trailing P/E", "Forward P/E", "Price / book", "PEG ratio",
                    "Return on equity", "Profit margin", "Operating margin",
                    "Debt / equity", "Current ratio", "Revenue growth", "Earnings growth"):
            if profile.get(key) is not None:
                lines.append(f"- {key}: {_fmt(profile[key])}")
        lines.append(f"- Financial statement coverage: {_fmt(fundamentals.get('statement_coverage'))}")
        for warning in fundamentals.get("warnings", []):
            lines.append(f"- Data warning: {warning}")
    if screening:
        lines += ["", "## Fundamental screening",
                  f"- Heuristic composite score: {_fmt(screening.get('composite_score'))}/100",
                  f"- Pillar coverage: {_fmt(screening.get('coverage'))}",
                  f"- Methodology: {_fmt(screening.get('methodology'))}"]
        for pillar, detail in screening.get("pillars", {}).items():
            lines.append(f"- {pillar}: {_fmt(detail.get('score'))}/100 ({detail.get('coverage')} inputs)")
        for flag in screening.get("flags", []):
            lines.append(f"- Caution: {flag}")
    if news is not None:
        lines += ["", "## Recent news"]
        if not news:
            lines.append("- No headlines returned by the provider.")
        for item in news:
            line = f"- {item.get('title', 'Untitled')} — {item.get('publisher', 'Unknown')}, {item.get('published', 'Date unavailable')}"
            if item.get("link"):
                line += f" ([source]({item['link']}))"
            lines.append(line)
    if risk:
        lines += ["", "## Portfolio risk snapshot",
            f"- Observation window: {_fmt(risk.get('start_date'))} to {_fmt(risk.get('end_date'))}",
            f"- Annualised volatility: {_fmt(risk.get('annualised_volatility_pct'), '%')}",
            f"- Historical VaR: {_fmt(risk.get('historical_var_pct'), '%')} at {_fmt(risk.get('confidence', 0) * 100, '%')} confidence",
            f"- Historical CVaR: {_fmt(risk.get('historical_cvar_pct'), '%')}",
            f"- Maximum drawdown: {_fmt(risk.get('max_drawdown_pct'), '%')}",
            f"- Observations: {_fmt(risk.get('observations'))}",
        ]
    lines += [
        "",
        "## Data and methodology notes",
        "- Market prices, company ratios and news are sourced from Yahoo Finance through yfinance and may be delayed, incomplete, stale or rate-limited.",
        "- Fundamental screening thresholds are heuristic, equal-weighted and not sector-adjusted. The score is not intrinsic value or a fair-value estimate.",
        "- Historical risk statistics describe the selected sample and do not forecast future losses. VaR is not a maximum-loss bound.",
        "- Verify financial statements, exchange filings, prices, corporate actions, taxes and fees independently before making decisions.",
        "- AlphaFund remains read-only for broker integration. No live orders are placed.",
    ]
    return "\n".join(lines) + "\n"

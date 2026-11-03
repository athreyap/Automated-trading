"""Automatic portfolio review: deterministic metrics first, AI interpretation second."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from alphafund.analytics import holdings_frame, valuation_enriched_holdings, investor_xirr


def current_positions(holdings: list[dict]) -> pd.DataFrame:
    frame = holdings_frame(holdings)
    if frame.empty:
        return frame
    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"], errors="coerce")
    return (frame.sort_values("as_of_date")
            .drop_duplicates(["account", "identifier"], keep="last")
            .loc[lambda x: x["quantity"].fillna(0) > 0].copy())


def portfolio_review(holdings: list[dict], valuations: list[dict],
                     transactions: list[dict]) -> dict[str, Any]:
    positions = current_positions(holdings)
    if positions.empty:
        return {"status": "empty", "message": "No current holdings are saved yet.",
                "position_count": 0, "cost_basis": None, "market_value": None,
                "coverage_pct": 0, "asset_allocation": [], "largest_positions": [],
                "findings": ["Import or sync holdings to generate a portfolio review."]}
    valued = valuation_enriched_holdings(positions.to_dict("records"), valuations)
    known_cost = valued["cost_basis"].notna()
    cost = float(valued.loc[known_cost, "cost_basis"].sum()) if known_cost.any() else None
    valued_rows = valued.dropna(subset=["market_value"])
    coverage = len(valued_rows) / len(valued) * 100
    full_value = len(valued_rows) == len(valued) and len(valued) > 0
    market_value = float(valued_rows["market_value"].sum()) if full_value else None
    pnl = float(valued["unrealised_pnl"].sum()) if full_value and valued["unrealised_pnl"].notna().all() else None
    alloc = (valued.loc[known_cost].groupby("asset_type", dropna=False)["cost_basis"].sum()
             .sort_values(ascending=False))
    allocation = [{"asset_type": str(k or "Unclassified"), "cost_basis": float(v)}
                  for k, v in alloc.items()]
    largest = (valued.loc[known_cost].sort_values("cost_basis", ascending=False).head(10))
    largest_rows = [{"instrument": str(r.instrument), "asset_type": str(r.asset_type or "Unclassified"),
                     "cost_basis": float(r.cost_basis)} for r in largest.itertuples()]
    total_known = sum(x["cost_basis"] for x in allocation)
    top3 = sum(x["cost_basis"] for x in largest_rows[:3])
    findings = []
    if coverage < 100:
        findings.append(f"Valuation coverage is {coverage:.1f}%; current portfolio market value and total unrealised P&L are withheld until every current position has a matching valuation.")
    if cost is None or valued["cost_basis"].isna().any():
        findings.append("Some positions have missing average cost; cost-basis allocation excludes those positions.")
    if total_known > 0 and top3 / total_known >= 0.60:
        findings.append(f"The three largest cost-basis positions represent {top3 / total_known:.1%} of known cost basis; review single-name concentration.")
    if len(allocation) == 1:
        findings.append("Recorded cost basis is concentrated in one asset class; check whether this reflects the complete portfolio.")
    if not transactions:
        findings.append("No transaction history is saved; investor XIRR and cash-flow analysis are unavailable.")
    elif not full_value:
        findings.append("Transaction history exists, but a complete terminal valuation is required for a meaningful investor XIRR.")
    if not findings:
        findings.append("No basic data-coverage warning was detected. Review holdings and valuation freshness before drawing conclusions.")
    return {
        "status": "ready", "position_count": int(len(valued)),
        "cost_basis": cost, "market_value": market_value, "unrealised_pnl": pnl,
        "valuation_coverage_pct": coverage, "full_valuation_coverage": full_value,
        "asset_allocation": allocation, "largest_positions": largest_rows,
        "transaction_count": len(transactions), "valuation_count": len(valuations),
        "findings": findings,
        "latest_holding_date": str(positions["as_of_date"].max().date()) if positions["as_of_date"].notna().any() else None,
    }


def review_fingerprint(holdings: list[dict], valuations: list[dict],
                       transactions: list[dict]) -> str:
    payload = json.dumps([holdings, valuations, transactions], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ai_interpretation(review: dict, api_key: str = "", model: str = "gpt-4o-mini") -> str:
    if review.get("status") == "empty":
        return review["message"]
    if not api_key:
        return ("**AI provider not configured.** Showing deterministic portfolio diagnostics. "
                "Add OPENAI_API_KEY to Streamlit Secrets to enable the full AI analyst.\n\n"
                + "\n".join(f"- {item}" for item in review.get("findings", [])))
    try:
        from openai import OpenAI
        response = OpenAI(api_key=api_key).chat.completions.create(
            model=model, temperature=0.2,
            messages=[
                {"role": "system", "content": (
                    "You are AlphaFund's investment research analyst. Interpret only the supplied "
                    "verified portfolio metrics. Do not invent market data, benchmark returns, "
                    "prices, NAVs, sectors, risk statistics or missing values. Distinguish cost "
                    "basis from market value. If valuation coverage is incomplete, say so and do "
                    "not state a portfolio-wide return. Identify concentration, diversification "
                    "and data-quality issues; explain what additional data is needed. Do not "
                    "issue buy/sell orders or guarantee performance. Use headings: Executive view, "
                    "What stands out, Risks and data gaps, Next steps."
                )},
                {"role": "user", "content": json.dumps(review, default=str, ensure_ascii=False)},
            ])
        return response.choices[0].message.content or "AI analysis returned no text."
    except Exception as exc:
        return ("AI analysis is temporarily unavailable (" + type(exc).__name__ +
                "). Deterministic metrics remain available.\n\n" +
                "\n".join(f"- {item}" for item in review.get("findings", [])))

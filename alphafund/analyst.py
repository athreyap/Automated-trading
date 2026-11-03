"""Automatic portfolio review: deterministic metrics first, AI interpretation second."""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from alphafund.analytics import holdings_frame, valuation_enriched_holdings
from alphafund.ai_providers import AIProviderError, huggingface_chat, ollama_chat, openai_chat


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
    largest = valued.loc[known_cost].sort_values("cost_basis", ascending=False).head(10)
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


def ai_interpretation(review: dict, api_key: str = "", model: str = "gpt-4o-mini",
                      provider: str = "ollama", ollama_model: str = "qwen2.5:7b",
                      ollama_base_url: str = "http://localhost:11434",
                      allow_cloud_fallback: bool = False, huggingface_token: str = "",
                      huggingface_model: str = "openai/gpt-oss-120b:cheapest",
                      cloud_data_sharing: bool = False) -> str:
    if review.get("status") == "empty":
        return review["message"]
    findings = "\n".join(f"- {item}" for item in review.get("findings", []))
    if provider not in {"ollama", "openai", "huggingface"}:
        return "Unsupported AI provider. Choose 'huggingface', 'ollama' or 'openai'."
    system = (
        "You are AlphaFund's investment research analyst. Interpret only the supplied "
        "verified portfolio metrics. Do not invent market data, benchmark returns, prices, "
        "NAVs, sectors, risk statistics or missing values. Distinguish cost basis from market "
        "value. If valuation coverage is incomplete, do not state a portfolio-wide return. "
        "Identify concentration, diversification and data-quality issues; explain what "
        "additional data is needed. Do not issue buy/sell orders or guarantee performance. "
        "Use headings: Executive view, What stands out, Risks and data gaps, Next steps."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(review, default=str, ensure_ascii=False)},
    ]
    if provider == "huggingface":
        if not cloud_data_sharing:
            return ("**Cloud AI is not enabled for portfolio data.** Set "
                    "ALPHAFUND_CLOUD_DATA_SHARING=true only after reviewing the provider's data policy. "
                    "No portfolio metrics were sent.\n\n" + findings)
        try:
            return huggingface_chat(messages, api_token=huggingface_token, model=huggingface_model)
        except AIProviderError as exc:
            return f"**Managed AI unavailable.** {exc}\n\nDeterministic findings:\n{findings}"
    if provider == "ollama":
        try:
            return ollama_chat(messages, model=ollama_model, base_url=ollama_base_url)
        except AIProviderError as exc:
            if not allow_cloud_fallback:
                return (f"**Local AI unavailable.** {exc}\n\n"
                        "Your portfolio data was not sent to a cloud AI provider. "
                        "Start Ollama locally or explicitly enable cloud fallback.\n\n" + findings)
            try:
                return openai_chat(messages, api_key=api_key, model=model)
            except AIProviderError as cloud_exc:
                return f"**AI unavailable.** {cloud_exc}\n\nDeterministic findings:\n{findings}"
    try:
        return openai_chat(messages, api_key=api_key, model=model)
    except AIProviderError as exc:
        return f"**Cloud AI unavailable.** {exc}\n\nDeterministic findings:\n{findings}"

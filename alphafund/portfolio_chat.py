"""Portfolio-aware chat with a transparent local fallback."""
from __future__ import annotations

import json


def build_portfolio_context(holdings=None, valuations=None, transactions=None, groww_holdings=None):
    # Storage returns dated snapshots newest-first. Keep only the latest row for
    # each account/security so a sync history is never summed as multiple assets.
    latest = {}
    ordered_holdings = sorted(
        holdings or [], key=lambda row: str(row.get("as_of_date") or ""), reverse=True
    )
    for row in ordered_holdings:
        key = (str(row.get("account") or ""), str(row.get("identifier") or ""))
        if key not in latest:
            latest[key] = row
    current_holdings = list(latest.values())
    return {
        "saved_holdings": current_holdings[:300],
        "valuation_observations": (valuations or [])[-300:],
        "transactions": (transactions or [])[-300:],
        "groww_live_holdings": (groww_holdings or [])[:300],
        "groww_imported_holdings": [row for row in current_holdings if str(row.get("provider", "")).strip().lower() == "groww"][:300],
        "data_notes": [
            "Only supplied records are available; do not assume missing assets or transactions.",
            "Include imported Groww mutual-fund holdings from saved_holdings and groww_imported_holdings in portfolio analysis.",
            "Distinguish live Groww Demat stock holdings from imported Groww mutual-fund statement records.",
            "Do not calculate market value without a matching valuation or quote.",
            "Do not describe cost basis as current value.",
            "Flag mixed currencies, stale dates and incomplete coverage.",
            "This is educational information, not personalized investment advice."
        ],
    }


def answer_portfolio_question(question: str, context: dict, api_key: str = "",
                              model: str = "gpt-4o-mini", history=None) -> str:
    """Answer using only the supplied portfolio context; OpenAI is optional."""
    if not question.strip():
        return "Ask me about your holdings, allocation, returns, transactions or data quality."
    if not api_key:
        q = question.lower()
        holdings = context.get("saved_holdings", [])
        groww = context.get("groww_live_holdings", [])
        tx = context.get("transactions", [])
        vals = context.get("valuation_observations", [])

        def groww_cost_rows(rows):
            result = []
            for row in rows:
                try:
                    quantity = float(row.get("quantity") or 0)
                    average = float(row.get("average_price") or 0)
                except (TypeError, ValueError):
                    continue
                if quantity <= 0:
                    continue
                symbol = str(row.get("trading_symbol") or row.get("isin") or "Unknown")
                result.append({"symbol": symbol, "quantity": quantity,
                               "average_price": average, "cost_basis": quantity * average})
            return result

        live_rows = groww_cost_rows(groww)
        if any(k in q for k in ("analyse", "analyze", "summary", "allocation", "concentration", "portfolio", "holding", "position", "own", "fund")):
            saved_cost_rows = []
            for row in holdings:
                try:
                    quantity = float(row.get("quantity") or 0)
                    average = float(row.get("average_cost") or 0)
                except (TypeError, ValueError):
                    continue
                if quantity <= 0:
                    continue
                saved_cost_rows.append({
                    "name": str(row.get("instrument") or row.get("identifier") or "Unknown"),
                    "asset_type": str(row.get("asset_type") or "unclassified"),
                    "channel": str(row.get("channel") or row.get("provider") or "AlphaFund"),
                    "cost_basis": quantity * average,
                })
            groww_mf_rows = [row for row in saved_cost_rows
                             if row["asset_type"].lower() == "mutual_fund"
                             and row["channel"].lower() == "groww"]
            lines = [
                "**Portfolio data loaded**",
                f"- Live Groww Demat stock holdings: {len(live_rows)}",
                f"- Saved AlphaFund holding records: {len(holdings)}",
                f"- Imported Groww mutual-fund records: {len(groww_mf_rows)}",
                f"- Saved transactions: {len(tx)}",
                f"- Saved valuation observations: {len(vals)}",
            ]
            if groww_mf_rows:
                mf_cost = sum(row["cost_basis"] for row in groww_mf_rows)
                lines.append(f"- Groww mutual-fund recorded cost basis: ₹{mf_cost:,.2f} (only rows with average cost; not current NAV value)")
                lines.append("**Imported Groww mutual funds**")
                for row in sorted(groww_mf_rows, key=lambda item: item["cost_basis"], reverse=True)[:10]:
                    lines.append(f"- {row['name']}: ₹{row['cost_basis']:,.2f} recorded cost basis")
            if saved_cost_rows:
                by_asset = {}
                for row in saved_cost_rows:
                    by_asset[row["asset_type"]] = by_asset.get(row["asset_type"], 0.0) + row["cost_basis"]
                lines.append("**Saved portfolio cost basis by asset type**")
                for asset, value in sorted(by_asset.items(), key=lambda item: item[1], reverse=True):
                    lines.append(f"- {asset}: ₹{value:,.2f}")
            if live_rows:
                invested = sum(row["cost_basis"] for row in live_rows)
                lines.append(f"- Groww recorded cost basis: ₹{invested:,.2f} (quantity × average purchase price; not current market value)")
                lines.append("**Largest Groww positions by recorded cost basis**")
                for row in sorted(live_rows, key=lambda item: item["cost_basis"], reverse=True)[:5]:
                    weight = (row["cost_basis"] / invested * 100) if invested else 0
                    lines.append(f"- {row['symbol']}: {row['quantity']:,.4g} units × ₹{row['average_price']:,.2f} = ₹{row['cost_basis']:,.2f} ({weight:.1f}% of recorded Groww cost)")
                if invested:
                    top3 = sum(row["cost_basis"] for row in sorted(live_rows, key=lambda item: item["cost_basis"], reverse=True)[:3]) / invested * 100
                    lines.append(f"- Top-three cost-basis concentration: {top3:.1f}%")
            elif not groww_mf_rows:
                lines.append("No Groww holdings are loaded. Connect Groww credentials for live Demat stocks or import a Groww mutual-fund statement CSV.")
            if holdings:
                lines.append("Imported Groww mutual funds are included from saved holdings. Live Groww Demat stocks are shown separately; check for duplicates before combining totals.")
            lines.append("**Limitations:** This local analysis uses recorded purchase cost only. It cannot calculate current market value, unrealised return, sector exposure or risk without current prices, instrument classifications and complete position coverage. Configure OPENAI_API_KEY for deeper natural-language analysis.")
            return "\n".join(lines)
        if any(k in q for k in ("transaction", "sip", "buy", "sell")):
            return f"There are {len(tx)} saved transactions. Import complete transaction history before relying on return calculations."
        if any(k in q for k in ("nav", "price", "valuation", "value", "return", "p&l", "pnl")):
            return (f"There are {len(vals)} saved valuation observations. "
                    "I will not infer a current value or return when a matching dated price/NAV is missing. "
                    "Configure OPENAI_API_KEY to enable portfolio-aware natural-language analysis.")
        return ("I can calculate basic Groww cost-basis summaries locally. For deeper portfolio reasoning across market data, documents and research, configure OPENAI_API_KEY in Streamlit Secrets.")
    try:
        from openai import OpenAI
        messages = [
            {"role": "system", "content": (
                "You are AlphaFund AI, a careful investment portfolio analyst. "
                "Answer using only the portfolio context supplied in the user message. "
                "Never invent prices, NAVs, transactions, returns, holdings or sources. "
                "Clearly distinguish verified records, estimates, missing data and opinions. "
                "Show formulas for calculations and mention currency and date coverage. "
                "Do not place orders or tell the user a trade is guaranteed. "
                "Keep answers structured and concise."
            )},
        ]
        for item in (history or [])[-8:]:
            if item.get("role") in ("user", "assistant"):
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": "PORTFOLIO DATA (JSON):\n" +
                         json.dumps(context, default=str, ensure_ascii=False) +
                         "\n\nQUESTION:\n" + question})
        response = OpenAI(api_key=api_key).chat.completions.create(
            model=model, temperature=0.2, messages=messages)
        return response.choices[0].message.content or "I could not generate an answer."
    except Exception as exc:
        return f"AI chat is temporarily unavailable ({type(exc).__name__}). Your portfolio data has not been changed."

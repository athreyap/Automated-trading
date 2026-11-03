"""Portfolio-aware chat with a transparent local fallback."""
from __future__ import annotations

import json


def build_portfolio_context(holdings=None, valuations=None, transactions=None, groww_holdings=None):
    return {
        "saved_holdings": (holdings or [])[:300],
        "valuation_observations": (valuations or [])[-300:],
        "transactions": (transactions or [])[-300:],
        "groww_live_holdings": (groww_holdings or [])[:300],
        "data_notes": [
            "Only supplied records are available; do not assume missing assets or transactions.",
            "Distinguish saved records from live Groww holdings.",
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
        if any(k in q for k in ("holding", "own", "portfolio", "position")):
            return (f"I can see {len(holdings)} saved holding records and {len(groww)} live Groww holding records. "
                    f"There are {len(vals)} saved valuation observations and {len(tx)} transactions. "
                    "Configure OPENAI_API_KEY for natural-language analysis of these records.")
        if any(k in q for k in ("transaction", "sip", "buy", "sell")):
            return f"There are {len(tx)} saved transactions. Import complete transaction history before relying on return calculations."
        if any(k in q for k in ("nav", "price", "valuation", "value", "return", "p&l", "pnl")):
            return (f"There are {len(vals)} saved valuation observations. "
                    "I will not infer a current value or return when a matching dated price/NAV is missing. "
                    "Configure OPENAI_API_KEY to enable portfolio-aware natural-language analysis.")
        return ("The local chat mode can confirm record counts, but does not yet perform open-ended reasoning. "
                "Add OPENAI_API_KEY in server-side Streamlit Secrets to enable portfolio-aware chat.")
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

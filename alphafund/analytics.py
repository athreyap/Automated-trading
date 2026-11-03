"""Deterministic portfolio analytics; never infer missing prices or cash flows."""
from __future__ import annotations

import math
import pandas as pd


def holdings_frame(records: list[dict]) -> pd.DataFrame:
    columns = ["instrument", "identifier", "asset_type", "quantity", "average_cost",
               "as_of_date", "source", "account"]
    frame = pd.DataFrame(records)
    if frame.empty:
        return pd.DataFrame(columns=columns + ["cost_basis"])
    for column in columns:
        if column not in frame:
            frame[column] = None
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["average_cost"] = pd.to_numeric(frame["average_cost"], errors="coerce")
    frame["cost_basis"] = frame["quantity"] * frame["average_cost"]
    frame.loc[frame["average_cost"].isna(), "cost_basis"] = float("nan")
    return frame


def portfolio_summary(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"holding_count": 0, "cost_basis": 0.0, "known_cost_count": 0,
                "missing_cost_count": 0, "cost_coverage_pct": 0.0}
    known = frame["cost_basis"].notna()
    count = len(frame)
    return {"holding_count": int(count), "cost_basis": float(frame.loc[known, "cost_basis"].sum()),
            "known_cost_count": int(known.sum()), "missing_cost_count": int((~known).sum()),
            "cost_coverage_pct": float(known.mean() * 100)}


def allocation_by(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if frame.empty or dimension not in frame:
        return pd.DataFrame(columns=[dimension, "cost_basis"])
    data = frame.dropna(subset=["cost_basis"]).copy()
    if data.empty:
        return pd.DataFrame(columns=[dimension, "cost_basis"])
    data[dimension] = data[dimension].fillna("Unclassified").replace("", "Unclassified")
    return data.groupby(dimension, as_index=False)["cost_basis"].sum().sort_values("cost_basis", ascending=False)


def groww_holdings_frame(records: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    for column in ("quantity", "average_price", "invested_value"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "invested_value" not in frame:
        frame["invested_value"] = frame["quantity"] * frame["average_price"] if {"quantity", "average_price"}.issubset(frame.columns) else float("nan")
    return frame


def valuation_enriched_holdings(holdings: list[dict], valuations: list[dict]) -> pd.DataFrame:
    """Match latest reported market value or unit price/NAV to each account holding."""
    frame = holdings_frame(holdings)
    if frame.empty or not valuations:
        frame["market_value"] = float("nan")
        frame["unrealised_pnl"] = float("nan")
        frame["valuation_date"] = None
        frame["valuation_source"] = None
        return frame
    values = pd.DataFrame(valuations)
    values = values[values["observation_type"].isin(["market_value", "price", "nav"])].copy()
    if values.empty:
        frame["market_value"] = float("nan")
        frame["unrealised_pnl"] = float("nan")
        frame["valuation_date"] = None
        frame["valuation_source"] = None
        return frame
    values["valuation_date"] = pd.to_datetime(values["valuation_date"], errors="coerce")
    values["value"] = pd.to_numeric(values["value"], errors="coerce")
    values = values.sort_values("valuation_date").dropna(subset=["value"])
    latest = values.groupby(["account", "identifier", "observation_type"], as_index=False).tail(1)
    rows = []
    for _, holding in frame.iterrows():
        match = latest[(latest["account"] == holding["account"]) & (latest["identifier"] == holding["identifier"])]
        if match.empty:
            rows.append((float("nan"), None, None))
            continue
        # Use the newest observation; on the same date prefer a total market value.
        match = match.copy()
        match["_priority"] = match["observation_type"].map({"market_value": 2, "price": 1, "nav": 1}).fillna(0)
        selected = match.sort_values(["valuation_date", "_priority"]).iloc[-1]
        market_value = float(selected["value"])
        if selected["observation_type"] in ("price", "nav"):
            market_value *= float(holding["quantity"])
        rows.append((market_value, selected["valuation_date"].date().isoformat(), selected["source"]))
    frame["market_value"] = [r[0] for r in rows]
    frame["valuation_date"] = [r[1] for r in rows]
    frame["valuation_source"] = [r[2] for r in rows]
    frame["unrealised_pnl"] = frame["market_value"] - frame["cost_basis"]
    return frame


def portfolio_valuation_history(valuations: list[dict]) -> pd.DataFrame:
    """Aggregate only explicit total market_value observations; never mix prices/NAVs."""
    frame = pd.DataFrame(valuations)
    if frame.empty or "observation_type" not in frame:
        return pd.DataFrame(columns=["valuation_date", "portfolio_value"])
    frame = frame[frame["observation_type"] == "market_value"].copy()
    if frame.empty:
        return pd.DataFrame(columns=["valuation_date", "portfolio_value"])
    currencies = frame["currency"].dropna().unique()
    if len(currencies) > 1:
        return pd.DataFrame(columns=["valuation_date", "portfolio_value"])
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    return frame.groupby("valuation_date", as_index=False)["value"].sum().rename(columns={"value": "portfolio_value"})


def xirr(cashflows: list[tuple[object, float]]) -> float | None:
    """Annualized money-weighted return via bisection; returns None if not solvable."""
    clean = [(pd.Timestamp(d), float(v)) for d, v in cashflows if v is not None and math.isfinite(float(v))]
    if not clean or not any(v < 0 for _, v in clean) or not any(v > 0 for _, v in clean):
        return None
    start = min(d for d, _ in clean)
    days = [(d - start).days / 365.0 for d, _ in clean]
    def npv(rate: float) -> float:
        try:
            return sum(value / ((1 + rate) ** years) for years, (_, value) in zip(days, clean))
        except (OverflowError, ZeroDivisionError):
            return float("inf")
    low, high = -0.9999, 10.0
    f_low, f_high = npv(low), npv(high)
    while f_low * f_high > 0 and high < 1_000_000:
        high *= 2
        f_high = npv(high)
    if f_low * f_high > 0:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            return mid
        if f_low * f_mid <= 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return (low + high) / 2


def investor_xirr(transactions: list[dict], terminal_value: float | None = None,
                  terminal_date: object | None = None) -> float | None:
    """Calculate investor XIRR from supported cash-flow transaction types and terminal value."""
    negative_types = {"BUY", "SIP", "CONTRIBUTION", "DEPOSIT", "FEE", "TAX"}
    positive_types = {"SELL", "DIVIDEND", "INTEREST", "COUPON", "WITHDRAWAL", "DISTRIBUTION"}
    flows = []
    for row in transactions:
        kind = str(row.get("transaction_type", "")).upper()
        amount = float(row.get("amount") or 0)
        if kind in negative_types:
            flows.append((row["transaction_date"], -amount))
        elif kind in positive_types:
            flows.append((row["transaction_date"], amount))
    if terminal_value is not None and terminal_date is not None and float(terminal_value) > 0:
        flows.append((terminal_date, float(terminal_value)))
    return xirr(flows)

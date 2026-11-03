"""Deterministic portfolio analytics. All monetary values are in each holding's currency."""
from __future__ import annotations

import pandas as pd


def holdings_frame(records: list[dict]) -> pd.DataFrame:
    """Return normalized holding rows with explicit cost-basis coverage."""
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
    """Summarize the supplied snapshot; missing costs are excluded, never imputed."""
    if frame.empty:
        return {"holding_count": 0, "cost_basis": 0.0, "known_cost_count": 0,
                "missing_cost_count": 0, "cost_coverage_pct": 0.0}
    known = frame["cost_basis"].notna()
    total = float(frame.loc[known, "cost_basis"].sum())
    count = int(len(frame))
    return {"holding_count": count, "cost_basis": total,
            "known_cost_count": int(known.sum()), "missing_cost_count": int((~known).sum()),
            "cost_coverage_pct": (float(known.mean()) * 100 if count else 0.0)}


def allocation_by(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Aggregate known cost basis by a descriptive dimension."""
    if frame.empty or dimension not in frame:
        return pd.DataFrame(columns=[dimension, "cost_basis"])
    data = frame.dropna(subset=["cost_basis"]).copy()
    if data.empty:
        return pd.DataFrame(columns=[dimension, "cost_basis"])
    data[dimension] = data[dimension].fillna("Unclassified").replace("", "Unclassified")
    return (data.groupby(dimension, as_index=False)["cost_basis"].sum()
            .sort_values("cost_basis", ascending=False))


def groww_holdings_frame(records: list[dict]) -> pd.DataFrame:
    """Normalize Groww holdings while preserving broker-provided invested value."""
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    for column in ("quantity", "average_price", "invested_value"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "invested_value" not in frame:
        if {"quantity", "average_price"}.issubset(frame.columns):
            frame["invested_value"] = frame["quantity"] * frame["average_price"]
        else:
            frame["invested_value"] = float("nan")
    return frame

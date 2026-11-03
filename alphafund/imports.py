"""CSV holdings validation helpers for AlphaFund."""
from __future__ import annotations

import hashlib
from datetime import date
from io import BytesIO

import pandas as pd

REQUIRED_COLUMNS = {
    "account_name", "account_type", "provider", "asset_type",
    "instrument_name", "identifier", "quantity", "as_of_date",
}
OPTIONAL_COLUMNS = {"exchange", "currency", "average_cost"}


def validate_holdings_csv(uploaded_bytes: bytes) -> tuple[pd.DataFrame, str]:
    checksum = hashlib.sha256(uploaded_bytes).hexdigest()
    frame = pd.read_csv(BytesIO(uploaded_bytes))
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("The uploaded CSV contains no holding rows.")

    for column in ("account_name", "account_type", "provider", "asset_type",
                   "instrument_name", "identifier"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise ValueError(f"Column '{column}' contains blank values.")

    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    if frame["quantity"].isna().any() or (frame["quantity"] < 0).any():
        raise ValueError("Quantity must contain valid non-negative numbers.")

    if "average_cost" not in frame:
        frame["average_cost"] = None
    else:
        frame["average_cost"] = pd.to_numeric(frame["average_cost"], errors="coerce")
        if (frame["average_cost"].dropna() < 0).any():
            raise ValueError("Average cost cannot be negative.")
        frame["average_cost"] = frame["average_cost"].astype(object).where(frame["average_cost"].notna(), None)

    if "currency" not in frame:
        frame["currency"] = "INR"
    frame["currency"] = frame["currency"].fillna("INR").astype(str).str.upper()
    if "exchange" not in frame:
        frame["exchange"] = None

    frame["as_of_date"] = pd.to_datetime(frame["as_of_date"], errors="coerce").dt.date
    if frame["as_of_date"].isna().any():
        raise ValueError("as_of_date must contain valid dates in YYYY-MM-DD format.")

    duplicate_keys = frame.duplicated(
        subset=["account_name", "asset_type", "identifier", "as_of_date"], keep=False
    )
    if duplicate_keys.any():
        rows = (frame.index[duplicate_keys] + 2).tolist()
        raise ValueError(f"Duplicate holding rows in CSV (spreadsheet rows: {rows}).")
    return frame, checksum

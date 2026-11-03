"""Validated CSV importers for holdings, transactions and valuation snapshots."""
from __future__ import annotations

import hashlib
from io import BytesIO

import pandas as pd


def _read_csv(uploaded_bytes: bytes) -> tuple[pd.DataFrame, str]:
    if not uploaded_bytes:
        raise ValueError("The uploaded file is empty.")
    checksum = hashlib.sha256(uploaded_bytes).hexdigest()
    frame = pd.read_csv(BytesIO(uploaded_bytes))
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    if frame.empty:
        raise ValueError("The uploaded CSV contains no rows.")
    return frame, checksum


def _required(frame: pd.DataFrame, columns: set[str]) -> None:
    missing = sorted(columns - set(frame.columns))
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))


def _text_fields(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        frame[column] = frame[column].fillna("").astype(str).str.strip()
        if (frame[column] == "").any():
            raise ValueError(f"Column '{column}' contains blank values.")


def _dates(frame: pd.DataFrame, column: str) -> None:
    frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.date
    if frame[column].isna().any():
        raise ValueError(f"{column} must contain valid dates in YYYY-MM-DD format.")


def validate_holdings_csv(uploaded_bytes: bytes) -> tuple[pd.DataFrame, str]:
    frame, checksum = _read_csv(uploaded_bytes)
    required = {"account_name", "account_type", "provider", "asset_type",
                "instrument_name", "identifier", "quantity", "as_of_date"}
    _required(frame, required)
    _text_fields(frame, ("account_name", "account_type", "provider", "asset_type",
                         "instrument_name", "identifier"))
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
    else:
        frame["exchange"] = frame["exchange"].where(frame["exchange"].notna(), None)
    _dates(frame, "as_of_date")
    duplicates = frame.duplicated(["account_name", "asset_type", "identifier", "as_of_date"], keep=False)
    if duplicates.any():
        raise ValueError(f"Duplicate holding rows in CSV (spreadsheet rows: {(frame.index[duplicates] + 2).tolist()}).")
    return frame, checksum


def validate_transactions_csv(uploaded_bytes: bytes) -> tuple[pd.DataFrame, str]:
    frame, checksum = _read_csv(uploaded_bytes)
    required = {"account_name", "provider", "asset_type", "instrument_name", "identifier",
                "transaction_type", "transaction_date", "amount"}
    _required(frame, required)
    _text_fields(frame, ("account_name", "provider", "asset_type", "instrument_name",
                         "identifier", "transaction_type"))
    frame["transaction_type"] = frame["transaction_type"].str.upper()
    allowed = {"BUY", "SELL", "SIP", "DIVIDEND", "INTEREST", "COUPON", "FEE",
               "TAX", "DEPOSIT", "WITHDRAWAL", "DISTRIBUTION", "CONTRIBUTION"}
    invalid = sorted(set(frame["transaction_type"]) - allowed)
    if invalid:
        raise ValueError("Unsupported transaction_type: " + ", ".join(invalid))
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    if frame["amount"].isna().any() or (frame["amount"] < 0).any():
        raise ValueError("amount must contain valid non-negative numbers.")
    for column in ("quantity", "price"):
        if column not in frame:
            frame[column] = None
        else:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            if (frame[column].dropna() < 0).any():
                raise ValueError(f"{column} cannot be negative.")
    if "currency" not in frame:
        frame["currency"] = "INR"
    frame["currency"] = frame["currency"].fillna("INR").astype(str).str.upper()
    if "external_id" not in frame:
        frame["external_id"] = None
    else:
        frame["external_id"] = frame["external_id"].astype(object).where(frame["external_id"].notna(), None)
        frame["external_id"] = frame["external_id"].apply(lambda value: None if value is None or str(value).strip() == "" else str(value).strip())
    if "notes" not in frame:
        frame["notes"] = None
    else:
        frame["notes"] = frame["notes"].where(frame["notes"].notna(), None)
    _dates(frame, "transaction_date")
    if frame["external_id"].dropna().duplicated().any():
        raise ValueError("Duplicate external_id values in transaction CSV.")
    return frame, checksum


def validate_valuations_csv(uploaded_bytes: bytes) -> tuple[pd.DataFrame, str]:
    frame, checksum = _read_csv(uploaded_bytes)
    required = {"account_name", "asset_type", "instrument_name", "identifier",
                "valuation_date", "value", "observation_type", "source"}
    _required(frame, required)
    _text_fields(frame, ("account_name", "asset_type", "instrument_name", "identifier",
                         "observation_type", "source"))
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    if frame["value"].isna().any() or (frame["value"] < 0).any():
        raise ValueError("value must contain valid non-negative numbers.")
    if "provider" not in frame:
        frame["provider"] = "manual"
    if "account_type" not in frame:
        frame["account_type"] = frame["asset_type"].map({"mutual_fund": "mutual_fund", "bond": "bond", "pms": "pms", "aif": "aif", "cash": "cash"}).fillna("broker")
    frame["provider"] = frame["provider"].fillna("manual").astype(str).str.strip()
    if "currency" not in frame:
        frame["currency"] = "INR"
    frame["currency"] = frame["currency"].fillna("INR").astype(str).str.upper()
    if "quality" not in frame:
        frame["quality"] = "reported"
    frame["quality"] = frame["quality"].fillna("reported").astype(str).str.lower()
    _dates(frame, "valuation_date")
    return frame, checksum

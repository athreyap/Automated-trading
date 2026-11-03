"""AMFI latest mutual-fund NAV feed parser.

The feed is used for scheme discovery and latest per-unit NAV only.
It does not contain an investor's units, cost basis or transaction history.
"""
from __future__ import annotations

from datetime import datetime
import requests
import pandas as pd

AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"


def fetch_latest_nav(timeout: int = 25) -> pd.DataFrame:
    response = requests.get(
        AMFI_NAV_URL,
        headers={"User-Agent": "AlphaFundAI/1.0 (mutual fund NAV lookup)"},
        timeout=timeout,
    )
    response.raise_for_status()
    rows = []
    for raw in response.text.splitlines():
        parts = [part.strip() for part in raw.split(";")]
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        try:
            # AMFI's common six-column feed and extended eight-column form
            # both put NAV and date in the final two fields.
            nav = float(parts[-2].replace(",", ""))
            nav_date = datetime.strptime(parts[-1], "%d-%b-%Y").date()
            rows.append({
                "scheme_code": parts[0],
                "isin_growth": parts[1] if len(parts) >= 6 else "",
                "isin_reinvestment": parts[2] if len(parts) >= 6 else "",
                "scheme_name": " ".join(parts[3:-2]).strip(),
                "nav": nav,
                "nav_date": nav_date,
            })
        except (ValueError, IndexError):
            continue
    if not rows:
        raise ValueError("AMFI returned no parseable NAV rows. Try again later.")
    frame = pd.DataFrame(rows)
    return frame.drop_duplicates(subset=["scheme_code", "scheme_name"], keep="last")


def search_nav_schemes(frame: pd.DataFrame, query: str, limit: int = 100) -> pd.DataFrame:
    if frame.empty or not query.strip():
        return frame.head(0)
    mask = frame["scheme_name"].str.contains(query.strip(), case=False, regex=False, na=False)
    return frame.loc[mask].sort_values("scheme_name").head(limit).reset_index(drop=True)

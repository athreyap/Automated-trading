from io import BytesIO

import pandas as pd

from alphafund.imports import validate_holdings_csv


def test_validate_holdings_xlsx():
    frame = pd.DataFrame([{
        "account_name": "Broker", "account_type": "broker", "provider": "manual",
        "asset_type": "equity", "instrument_name": "Example", "identifier": "EXAMPLE",
        "quantity": 3, "average_cost": 42.5, "as_of_date": "2026-11-10",
    }])
    buffer = BytesIO()
    frame.to_excel(buffer, index=False, engine="openpyxl")
    parsed, checksum = validate_holdings_csv(buffer.getvalue(), "holdings.xlsx")
    assert parsed.iloc[0]["quantity"] == 3
    assert parsed.iloc[0]["average_cost"] == 42.5
    assert len(checksum) == 64

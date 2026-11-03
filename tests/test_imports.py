import pytest
from alphafund.imports import validate_holdings_csv


def test_core_modules_import():
    import alphafund.config
    import alphafund.groww_client
    import alphafund.market_data
    import alphafund.strategy
    import alphafund.storage


def test_validate_holdings_csv():
    raw = (b"account_name,account_type,provider,asset_type,instrument_name,identifier,quantity,average_cost,as_of_date\n"
           b"Broker,broker,groww,equity,Reliance,RELIANCE,2,1200,2026-11-03\n")
    frame, checksum = validate_holdings_csv(raw)
    assert len(checksum) == 64
    assert frame.iloc[0]["quantity"] == 2
    assert frame.iloc[0]["average_cost"] == 1200


def test_validate_holdings_csv_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing required columns"):
        validate_holdings_csv(b"symbol,quantity\nRELIANCE,2\n")


def test_validate_holdings_csv_rejects_duplicate_rows():
    raw = (b"account_name,account_type,provider,asset_type,instrument_name,identifier,quantity,as_of_date\n"
           b"Broker,broker,groww,equity,Reliance,RELIANCE,2,2026-11-03\n"
           b"Broker,broker,groww,equity,Reliance,RELIANCE,3,2026-11-03\n")
    with pytest.raises(ValueError, match="Duplicate holding rows"):
        validate_holdings_csv(raw)

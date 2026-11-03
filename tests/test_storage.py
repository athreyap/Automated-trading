from datetime import date
import pytest
from alphafund.storage import PortfolioStore


def test_portfolio_store_creates_accounts_instruments_and_holdings(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    store.initialize()
    account_id = store.add_account("Groww Demat", "broker", provider="groww")
    instrument_id = store.add_instrument("equity", "Reliance Industries", "RELIANCE")
    store.add_holding(account_id, instrument_id, 2, date(2026, 11, 3), 1400.0)
    assert store.list_accounts()[0]["provider"] == "groww"
    holding = store.list_holdings()[0]
    assert holding["instrument"] == "Reliance Industries"
    assert holding["quantity"] == 2
    assert holding["average_cost"] == 1400.0
    assert holding["as_of_date"] == "2026-11-03"


def test_import_batch_tracks_source_and_checksum(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    batch_id = store.create_import_batch("pms", filename="sample-pms.csv",
        checksum="a" * 64, as_of_date=date(2026, 10, 31), row_count=12)
    assert batch_id > 0


def test_import_batch_rejects_unknown_source(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    with pytest.raises(ValueError, match="Unsupported import source"):
        store.create_import_batch("unknown")

def test_csv_import_is_idempotent_and_skips_existing_snapshot(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    row = {"account_name": "Broker", "account_type": "broker", "provider": "groww",
           "asset_type": "equity", "instrument_name": "Reliance", "identifier": "RELIANCE",
           "quantity": 2, "average_cost": 1200.0, "as_of_date": date(2026, 11, 3),
           "currency": "INR", "exchange": "NSE"}
    first = store.import_holdings([row], "holdings.csv", "a" * 64)
    second = store.import_holdings([row], "holdings.csv", "a" * 64)
    assert first["inserted"] == 1
    assert second["duplicate_file"] is True
    assert len(store.list_holdings()) == 1

from datetime import date
import pytest

from alphafund.analytics import investor_xirr, portfolio_valuation_history, valuation_enriched_holdings
from alphafund.imports import validate_transactions_csv, validate_valuations_csv
from alphafund.storage import PortfolioStore


def test_validate_transactions_csv():
    raw = (b"account_name,provider,asset_type,instrument_name,identifier,transaction_type,transaction_date,quantity,price,amount,currency,external_id\n"
           b"Broker,groww,equity,Reliance,RELIANCE,BUY,2026-10-01,2,100,200,INR,T-1\n")
    frame, checksum = validate_transactions_csv(raw)
    assert len(checksum) == 64
    assert frame.iloc[0]["transaction_type"] == "BUY"
    assert frame.iloc[0]["amount"] == 200


def test_validate_transactions_rejects_unknown_type():
    raw = (b"account_name,provider,asset_type,instrument_name,identifier,transaction_type,transaction_date,amount\n"
           b"Broker,groww,equity,Reliance,RELIANCE,UNKNOWN,2026-10-01,200\n")
    with pytest.raises(ValueError, match="Unsupported transaction_type"):
        validate_transactions_csv(raw)


def test_validate_valuations_csv():
    raw = (b"account_name,asset_type,instrument_name,identifier,valuation_date,value,observation_type,source\n"
           b"Broker,equity,Reliance,RELIANCE,2026-11-03,150,price,Yahoo\n")
    frame, _ = validate_valuations_csv(raw)
    assert frame.iloc[0]["value"] == 150
    assert frame.iloc[0]["observation_type"] == "price"


def test_import_transactions_and_valuations(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    tx = {"account_name": "Broker", "provider": "groww", "asset_type": "equity",
          "instrument_name": "Reliance", "identifier": "RELIANCE", "transaction_type": "BUY",
          "transaction_date": date(2026, 10, 1), "quantity": 2, "price": 100,
          "amount": 200, "currency": "INR", "external_id": "TX-1", "notes": None}
    first = store.import_transactions([tx], "tx.csv", "a" * 64)
    again = store.import_transactions([tx], "tx.csv", "a" * 64)
    assert first["inserted"] == 1
    assert again["duplicate_file"] is True
    val = {"account_name": "Broker", "provider": "groww", "asset_type": "equity",
           "instrument_name": "Reliance", "identifier": "RELIANCE",
           "valuation_date": date(2026, 11, 3), "value": 150, "observation_type": "price",
           "source": "manual", "quality": "reported", "currency": "INR"}
    result = store.import_valuations([val], "val.csv", "b" * 64)
    assert result["inserted"] == 1
    assert len(store.list_valuations()) == 1


def test_valuation_enriched_holding_and_xirr():
    holdings = [{"account": "Broker", "instrument": "Reliance", "identifier": "RELIANCE",
                 "asset_type": "equity", "quantity": 2, "average_cost": 100,
                 "as_of_date": "2026-11-03"}]
    valuations = [{"account": "Broker", "identifier": "RELIANCE", "valuation_date": "2026-11-03",
                   "value": 150, "observation_type": "price", "source": "test"}]
    enriched = valuation_enriched_holdings(holdings, valuations)
    assert enriched.iloc[0]["market_value"] == 300
    assert enriched.iloc[0]["unrealised_pnl"] == 100
    flows = [("2025-11-03", -100), ("2026-11-03", 110)]
    rate = investor_xirr([], terminal_value=110, terminal_date="2026-11-03")
    assert rate is None
    from alphafund.analytics import xirr
    assert abs(xirr(flows) - 0.1) < 0.002


def test_valuation_history_uses_only_total_market_value():
    rows = [{"valuation_date": "2026-11-01", "value": 100, "observation_type": "market_value", "currency": "INR"},
            {"valuation_date": "2026-11-01", "value": 50, "observation_type": "price", "currency": "INR"}]
    history = portfolio_valuation_history(rows)
    assert len(history) == 1
    assert history.iloc[0]["portfolio_value"] == 100

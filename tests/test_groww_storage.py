from datetime import date, timedelta

from alphafund.storage import PortfolioStore


def test_groww_sync_persists_and_upserts_same_day(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    store.initialize()
    today = date(2026, 11, 3)

    first = store.sync_groww_holdings([{
        "trading_symbol": "RELIANCE",
        "isin": "INE002A01018",
        "exchange": "NSE",
        "quantity": 5,
        "average_price": 1200,
    }], as_of_date=today)
    assert first["inserted"] == 1
    assert first["updated"] == 0

    second = store.sync_groww_holdings([{
        "trading_symbol": "RELIANCE",
        "isin": "INE002A01018",
        "exchange": "NSE",
        "quantity": 7,
        "average_price": 1210,
    }], as_of_date=today)
    assert second["inserted"] == 0
    assert second["updated"] == 1

    rows = store.list_holdings()
    assert len(rows) == 1
    assert rows[0]["quantity"] == 7
    assert rows[0]["average_cost"] == 1210
    assert rows[0]["provider"] == "groww"
    assert rows[0]["channel"] == "Groww"
    assert rows[0]["source"] == "Groww API"
    assert store.get_last_groww_sync()


def test_groww_sync_keeps_history_and_closes_missing_positions(tmp_path):
    store = PortfolioStore(f"sqlite:///{tmp_path / 'portfolio.db'}")
    store.initialize()
    first_day = date(2026, 11, 3)
    next_day = first_day + timedelta(days=1)
    row = {
        "trading_symbol": "TCS",
        "isin": "INE467B01029",
        "exchange": "NSE",
        "quantity": 3,
        "average_price": 3000,
    }
    store.sync_groww_holdings([row], as_of_date=first_day)
    result = store.sync_groww_holdings([], as_of_date=next_day)

    assert result["inserted"] == 1
    rows = store.list_holdings()
    assert len(rows) == 2
    latest = next(item for item in rows if item["as_of_date"] == next_day.isoformat())
    assert latest["quantity"] == 0

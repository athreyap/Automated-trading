from alphafund import paper_broker


def test_paper_buy_sell_fees_and_weighted_average_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_broker, "DB_PATH", tmp_path / "paper.db")
    paper_broker.initialize_ledger()

    buy = paper_broker.record_paper_trade(
        "ABC", "BUY", 10, 100, 2000, allocation_limit=2000, fee_bps=10
    )
    assert buy["notional"] == 1000
    assert buy["fees"] == 1
    assert paper_broker.paper_cash(2000) == 999

    sell = paper_broker.record_paper_trade(
        "ABC", "SELL", 4, 120, paper_broker.paper_cash(2000),
        allocation_limit=2000, fee_bps=10
    )
    assert sell["notional"] == 480
    assert round(paper_broker.paper_cash(2000), 2) == 1478.52

    position = paper_broker.paper_positions()[0]
    assert position["quantity"] == 6
    assert round(position["average_cost"], 2) == 100.10
    assert round(position["realized_pnl"], 2) == 79.12


def test_paper_ledger_blocks_overselling(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_broker, "DB_PATH", tmp_path / "paper.db")
    paper_broker.record_paper_trade("ABC", "BUY", 2, 10, 100, allocation_limit=100)
    try:
        paper_broker.record_paper_trade("ABC", "SELL", 3, 11, 100, allocation_limit=100)
    except ValueError as exc:
        assert "only 2 units are held" in str(exc)
    else:
        raise AssertionError("Oversell should be rejected.")

from alphafund.analyst import portfolio_review, current_positions


def sample_holding(identifier, asset_type="equity", cost=100, date="2026-11-03"):
    return {
        "instrument": identifier, "identifier": identifier, "asset_type": asset_type,
        "quantity": 1, "average_cost": cost, "as_of_date": date,
        "account": "Groww", "provider": "groww", "channel": "Groww",
    }


def test_current_positions_uses_latest_snapshot_without_double_counting():
    rows = [sample_holding("ABC", cost=90, date="2026-10-01"),
            sample_holding("ABC", cost=100, date="2026-11-03")]
    frame = current_positions(rows)
    assert len(frame) == 1
    assert frame.iloc[0]["average_cost"] == 100


def test_review_does_not_claim_market_value_without_complete_valuations():
    review = portfolio_review([sample_holding("ABC")], [], [])
    assert review["market_value"] is None
    assert review["unrealised_pnl"] is None
    assert review["valuation_coverage_pct"] == 0
    assert any("coverage" in item.lower() for item in review["findings"])


def test_review_computes_value_only_when_all_positions_are_valued():
    rows = [sample_holding("ABC"), sample_holding("XYZ", asset_type="mutual_fund")]
    valuations = [
        {"account":"Groww", "identifier":"ABC", "observation_type":"price",
         "valuation_date":"2026-11-03", "value":120, "source":"test"},
        {"account":"Groww", "identifier":"XYZ", "observation_type":"nav",
         "valuation_date":"2026-11-03", "value":80, "source":"test"},
    ]
    review = portfolio_review(rows, valuations, [])
    assert review["market_value"] == 200
    assert review["unrealised_pnl"] == 0
    assert review["valuation_coverage_pct"] == 100

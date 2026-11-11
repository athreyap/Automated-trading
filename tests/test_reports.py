from alphafund.reports import build_research_report


def test_report_contains_methodology_and_no_trade_claim():
    report = build_research_report(
        "Test report", "NSE", "RELIANCE",
        technical={"as_of":"2026-11-10","close":100,"trend":"Bullish",
                   "technical_score":3,"technical_score_max":5},
        screening={"composite_score":75,"coverage":"3/4 pillars",
                   "methodology":"Heuristic"},
        news=[],
    )
    assert "Not investment advice" in report
    assert "Heuristic composite score" in report
    assert "No live orders" in report

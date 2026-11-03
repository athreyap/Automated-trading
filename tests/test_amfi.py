from alphafund.amfi import search_nav_schemes
import pandas as pd


def test_search_nav_schemes_matches_case_insensitively():
    frame = pd.DataFrame([
        {"scheme_code": "1", "scheme_name": "Alpha Large Cap Fund", "nav": 10.5},
        {"scheme_code": "2", "scheme_name": "Beta Liquid Fund", "nav": 20.0},
    ])
    result = search_nav_schemes(frame, "LARGE")
    assert len(result) == 1
    assert result.iloc[0]["scheme_code"] == "1"


def test_search_nav_schemes_empty_query_returns_empty():
    frame = pd.DataFrame([{"scheme_name": "Alpha Fund"}])
    assert search_nav_schemes(frame, "").empty

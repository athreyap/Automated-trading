import pandas as pd

from alphafund.company_intel import _news_content, _statement_table


def test_statement_table_selects_financial_rows_and_years():
    source = pd.DataFrame(
        [[1000, 900], [120, 100]],
        index=["Total Revenue", "Net Income"],
        columns=[pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")],
    )
    result = _statement_table(source)
    assert list(result["Metric"]) == ["Revenue", "Net income"]
    assert result.loc[0, "2025"] == 1000.0
    assert result.loc[1, "2024"] == 100.0


def test_news_parser_supports_nested_yfinance_payload():
    item = {
        "content": {
            "title": "Company reports results",
            "summary": "Revenue increased.",
            "provider": {"displayName": "Example News"},
            "pubDate": "2026-11-10T10:00:00Z",
            "canonicalUrl": {"url": "https://example.com/story"},
        }
    }
    result = _news_content(item)
    assert result["title"] == "Company reports results"
    assert result["publisher"] == "Example News"
    assert result["link"] == "https://example.com/story"

from alphafund.portfolio_chat import answer_portfolio_question, build_portfolio_context


def test_context_separates_groww_and_saved_records():
    context = build_portfolio_context(holdings=[{"identifier": "ABC"}],
        groww_holdings=[{"trading_symbol": "XYZ"}], transactions=[], valuations=[])
    assert len(context["saved_holdings"]) == 1
    assert context["groww_live_holdings"][0]["trading_symbol"] == "XYZ"


def test_local_chat_does_not_invent_market_value():
    context = build_portfolio_context(holdings=[{"identifier": "ABC"}])
    answer = answer_portfolio_question("What is my current market value?", context)
    assert "valuation observations" in answer
    assert "not infer" in answer


def test_local_chat_reports_transaction_count():
    context = build_portfolio_context(transactions=[{"amount": 100}, {"amount": 200}])
    answer = answer_portfolio_question("Show my transactions", context)
    assert "2 saved transactions" in answer

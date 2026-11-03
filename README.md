# AlphaFund AI V1

A paper-trading-first research platform for Indian equities.

## Current scope

- Market data: Yahoo Finance with a Groww integration boundary.
- Signal generation: deterministic technical indicators and rule-based strategy.
- AI: optional hybrid AI layer for explaining signals; AI output is not an order instruction.
- Execution: paper trading only.
- Risk: position sizing, exposure limits, and a protected cash reserve.
- Storage: local SQLite ledger for paper trades.

## Safety defaults

- Live trading is disabled.
- Broker order placement is not implemented in this initial version.
- Groww access is not required to run the paper-trading application.
- Never commit API keys, access tokens, passwords, or other secrets.
- Do not treat backtest or paper-trading results as a guarantee of future returns.

## Initial capital configuration

The initial example configuration uses INR 1,000 total capital, with INR 900 allocated for strategy testing and INR 100 held as a reserve. Adjust this only after reviewing transaction costs, liquidity, and risk limits.

## Run locally

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install dependencies from `requirements.txt`.
4. Copy `.env.example` to `.env` and configure optional services.
5. Start the dashboard with `streamlit run app.py`.

The application source and exact setup commands will be added in subsequent commits.

## Disclaimer

This project is for software development, research, and educational testing. It is not investment advice. Market data may be delayed or incomplete. Brokerage, taxes, exchange fees, spread, and slippage can materially affect small-capital strategies.

# AlphaFund AI V1

A Streamlit-based Indian equities research dashboard with technical signals, a simplified backtest, optional AI explanations, and a local SQLite paper ledger.

## V1 status and safety

- Paper trading only. Live trading is disabled and order placement is not implemented.
- Groww is a future integration boundary only; no Groww authentication or broker calls are implemented.
- Yahoo Finance is used for indicative historical market data. Availability, accuracy and delays are controlled by the data provider.
- The paper ledger is local SQLite. On ephemeral cloud hosting, its contents may be lost on restart or redeploy.
- This is educational software, not investment advice. Backtests do not predict future returns.

## Configuration

The default example uses INR 1,000 capital: INR 900 strategy allocation and INR 100 protected reserve. Copy .env.example to .env to override settings. Do not commit secrets.

## Run on a laptop

1. Install Python 3.11 or newer.
2. Clone this repository and open its folder.
3. Create a virtual environment: python -m venv .venv
4. Activate it:
   - Windows PowerShell: .venv\Scripts\Activate.ps1
   - macOS/Linux: source .venv/bin/activate
5. Install packages: pip install -r requirements.txt
6. Start: streamlit run app.py
7. Open the local URL printed by Streamlit, usually http://localhost:8501

## Run with Docker

Build: docker build -t alphafund-ai-v1 .
Run: docker run --rm -p 8501:8501 alphafund-ai-v1

## Tests

Install dependencies, then run: pytest -q

## Current limitations

- The Groww adapter deliberately raises NotImplementedError. It does not use unofficial endpoints or place orders.
- Paper ledger V1 records BUY entries and blocks SELL entries. It is not a complete portfolio/holdings engine.
- Backtest uses a simple long-only moving-average regime, lags positions by one bar to reduce look-ahead bias, and excludes transaction costs, slippage, dividends and taxes.
- Optional OpenAI explanations require an API key in the environment. Without it, a local explanation is used. ChatGPT subscription does not include API credits.
- Render free services may sleep and use ephemeral storage. Do not rely on the free deployment for persistent trade records; use a persistent database/disk before any ongoing use.

## Suggested next milestones

1. Add position-aware BUY/SELL accounting and transaction-cost modelling.
2. Add robust data validation, NSE symbol master and corporate-action handling.
3. Add authenticated user access and persistent cloud database.
4. Implement Groww only through its current official API after reviewing eligibility, fees, terms and scopes. Keep broker order placement disabled until explicitly tested and approved.

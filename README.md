# AlphaFund AI V1

A Streamlit-based Indian equities research dashboard with technical signals, a simplified backtest, optional AI explanations, a local SQLite paper ledger, and read-only Groww portfolio retrieval.

## V1 status and safety

- Paper trading only. Live trading is disabled and order placement is not implemented.
- Groww integration calls only official read-only holdings and CASH positions GET endpoints. No order placement, modification or cancellation methods are present.
- Hosting choice: Streamlit Community Cloud for the dashboard and read-only portfolio view. It does not provide stable outbound IP addresses, so it must not be used as the future Groww order-execution host.
- The dashboard requires APP_PASSWORD and keeps Groww credentials in server-side Streamlit secrets. Never commit or share secrets.
- Groww supports a direct access token (expires daily at 6:00 AM IST) or API key + secret authentication. The app can generate an access token on portfolio refresh using the API key + secret; the API key must first be approved each day on Groww Cloud → API Keys.
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

## Deploy a private mobile dashboard (Streamlit Community Cloud)

1. Open https://share.streamlit.io/ and sign in with GitHub.
2. Authorize Streamlit to access this repository.
3. Create an app using repository `athreyap/Automated-trading`, branch `main`, and main file `app.py`.
4. In app Settings → Secrets, add TOML values (replace placeholders in Streamlit settings; never send secrets in chat or commit them):

   ```toml
   APP_PASSWORD = "choose-a-long-unique-password"
   # Choose ONE Groww authentication method:
   # Method A: direct token (expires daily at 6:00 AM IST)
   # GROWW_ACCESS_TOKEN = "your-current-groww-access-token"
   # Method B: API key + secret (approve the key daily in Groww Cloud → API Keys)
   GROWW_API_KEY = "your-groww-api-key"
   GROWW_API_SECRET = "your-groww-api-secret"
   # Optional
   OPENAI_API_KEY = "your-openai-api-key"
   ```

5. Save and restart the app. Open its HTTPS `.streamlit.app` URL on Android and sign in.
6. For API key + secret authentication, approve the key each day in Groww Cloud → API Keys. In the app, click **Refresh Groww portfolio**; AlphaFund AI generates a fresh access token using Groww's documented checksum flow. Alternatively, configure GROWW_ACCESS_TOKEN directly; direct tokens expire at 6:00 AM IST daily.

The app fails closed if APP_PASSWORD is missing. This is a basic single-user password gate, not full identity management. Keep the URL private and use a unique password. Verify API access and subscription eligibility in your Groww account.

## Future architecture: Streamlit dashboard + separate execution service

The selected V1 hosting target is Streamlit Community Cloud. Keep it as the user interface and read-only portfolio dashboard. If automated Groww order execution is approved later, deploy a separate backend/execution service on a VPS or cloud VM with a reserved static public IP, whitelist that IP in Groww, and have the Streamlit UI communicate with that backend over authenticated HTTPS. Never send Groww order requests directly from Streamlit Community Cloud. See [docs/architecture.md](docs/architecture.md).

## Run with Docker

Build: docker build -t alphafund-ai-v1 .
Run: docker run --rm -p 8501:8501 alphafund-ai-v1

## Tests

Install dependencies, then run: pytest -q

## Current limitations

- Groww portfolio reads require valid credentials, daily API-key approval (for API key + secret flow), and API permissions. Holdings cost value is quantity × average price, not live market value or unrealised P&L.
- Paper ledger V1 records BUY entries and blocks SELL entries. It is not a complete portfolio/holdings engine.
- Backtest uses a simple long-only moving-average regime, lags positions by one bar to reduce look-ahead bias, and excludes transaction costs, slippage, dividends and taxes.
- Optional OpenAI explanations require an API key in the environment. Without it, a local explanation is used. ChatGPT subscription does not include API credits.
- Render free services may sleep and use ephemeral storage. Do not rely on the free deployment for persistent trade records; use a persistent database/disk before any ongoing use.

## Suggested next milestones

1. Add position-aware BUY/SELL accounting and transaction-cost modelling.
2. Add robust data validation, NSE symbol master and corporate-action handling.
3. Add authenticated user access and persistent cloud database.
4. Implement Groww only through its current official API after reviewing eligibility, fees, terms and scopes. Keep broker order placement disabled until explicitly tested and approved.

## Approved multi-asset roadmap

AlphaFund is planned as a **single-user, hybrid-AI investment workspace** for both existing holdings and new investment research. Planned coverage includes equities/ETFs, mutual funds, bonds, PMS and AIF investments.

Supported ingestion paths in the product plan:
- Groww API (read-only; current supported holdings/CASH endpoints only)
- Excel / CSV imports
- Mutual-fund CAS statements
- Manual entry
- PMS / AIF statements

Planned capabilities include consolidated portfolio analytics, interactive charts, watchlists, investment discovery, and an AI chatbot that can retrieve portfolio records, uploaded-document passages and prior AlphaFund chats. Hybrid AI means cloud and optional local model providers behind a common router; sensitive document processing must be opt-in for cloud use.

These are **planned capabilities, not currently implemented features**. See:
- [Product scope and roadmap](docs/product-scope.md)
- [Canonical data model](docs/data-model.md)
- [Engineering implementation plan](docs/implementation-plan.md)
- [Hosting and execution architecture](docs/architecture.md)

Live Groww order placement remains disabled and out of scope.

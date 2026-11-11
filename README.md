# AlphaFund AI V1

A Streamlit-based Indian equities research dashboard with technical signals, a simplified backtest, optional AI explanations, a local SQLite paper ledger, and read-only Groww portfolio retrieval.

## V1 status and safety

- Paper trading only. Live trading is disabled and order placement is not implemented.
- Groww integration calls only official read-only holdings and CASH positions GET endpoints. No order placement, modification or cancellation methods are present.
- Hosting choice: Streamlit Community Cloud for the dashboard and read-only portfolio view. It does not provide stable outbound IP addresses, so it must not be used as the future Groww order-execution host.
- The dashboard requires APP_PASSWORD and keeps Groww credentials in server-side Streamlit secrets. Never commit or share secrets.
- Groww supports a direct access token (expires daily at 6:00 AM IST) or API key + secret authentication. The app can generate an access token on portfolio refresh using the API key + secret; the API key must first be approved each day on Groww Cloud → API Keys.
- Yahoo Finance is used for indicative historical market data. Availability, accuracy and delays are controlled by the data provider.
- The paper ledger remains local SQLite. The consolidated portfolio database supports managed PostgreSQL through `DATABASE_URL`; use a hosted database for durable cloud records.
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
   # Managed open-weight AI (Hugging Face Inference Providers)
   HF_TOKEN = "your-huggingface-token"
   HUGGINGFACE_MODEL = "openai/gpt-oss-120b:cheapest"
   ALPHAFUND_AI_PROVIDER = "huggingface"
   # Enable only after deciding to send portfolio records to cloud inference
   ALPHAFUND_CLOUD_DATA_SHARING = "true"
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
- The separate paper ledger now supports long-only BUY/SELL position accounting, weighted-average cost, realized P&L, fee estimates and oversell protection. It remains a simulation only.
- Backtest uses a simple long-only moving-average regime, lags positions by one bar to reduce look-ahead bias, and excludes transaction costs, slippage, dividends and taxes.
- Managed open-weight AI uses Hugging Face Inference Providers through an OpenAI-compatible API. It requires an HF_TOKEN and provider/model availability; usage may be billed by the selected inference provider. Portfolio data sharing is disabled by default and must be explicitly enabled with ALPHAFUND_CLOUD_DATA_SHARING=true.
- Render free services may sleep and use ephemeral storage. Do not rely on the free deployment for persistent trade records; use a persistent database/disk before any ongoing use.

## Suggested next milestones

1. Add position-aware BUY/SELL accounting and transaction-cost modelling.
2. Add robust data validation, NSE symbol master and corporate-action handling.
3. Add authenticated user access and persistent cloud database.
4. Implement Groww only through its current official API after reviewing eligibility, fees, terms and scopes. Keep broker order placement disabled until explicitly tested and approved.

## Mobile navigation

The main app is organized into four sections with a persistent mobile bottom navigation: Home (Groww read-only holdings and portfolio snapshot), Portfolio (manual/CSV holdings, transactions, valuations and performance), Discover (equity technical research plus mutual-fund NAV source guidance), and AI Chat (portfolio-aware assistant). The Discover page does not treat equity prices as mutual-fund NAVs; AMFI integration remains a separate data-source milestone.

## Groww-inspired UI and AlphaFund AI chat

The app now uses a cleaner investment-dashboard visual system with a light background, green primary actions, compact metric cards, consistent tables and clearer section hierarchy.

A portfolio-aware chat interface is included at the bottom of the dashboard. It uses saved holdings, valuations, transactions and Groww holdings currently in the Streamlit session. OpenAI-backed responses require `OPENAI_API_KEY`; without it, a limited local fallback reports data coverage and missing information. Chat history is session-scoped. The assistant is instructed not to invent prices, NAVs, transactions or returns and cannot place orders.

This is a Groww-inspired design reference, not a copy of Groww branding or proprietary UI.

## Transaction and valuation analytics (Phase 4)

The dashboard now supports:
- Validated transaction CSV import with transaction dates, type, units, price, amount, currency and optional external transaction ID.
- Validated valuation CSV import with append-only dated observations and explicit observation semantics: `market_value` (total position value), `price` (per-unit price) or `nav` (per-unit NAV).
- Duplicate-file checksums and conservative duplicate transaction/valuation checks.
- Position valuation using the newest matching observation for the same account and instrument. Unit price/NAV is multiplied by the latest saved holding quantity; a `market_value` observation is treated as a total.
- Unrealised P&L and return on recorded cost only when every current holding has a matching valuation and recorded cost.
- Portfolio valuation history from explicit `market_value` observations only.
- Investor XIRR from imported transaction cash flows and a complete terminal portfolio value.

Important limitations:
- Import the complete transaction history before using XIRR. Transaction type controls cash-flow direction; verify source statement signs and types.
- XIRR is only meaningful when all relevant cash flows are present, amounts use one currency, and the terminal value covers the complete portfolio.
- The current implementation does not convert currencies, model corporate actions, accrue bond coupons, calculate taxes/fees beyond imported entries, or reconcile statement balances.
- For portfolio history, import a total `market_value` observation for each account/instrument/date. Unit price and NAV observations are not summed as portfolio values.
- Groww holdings refresh is read-only and saved as dated snapshots in the configured portfolio database. CASH positions remain session-only.

## Portfolio analytics (Phase 3)

The dashboard now includes deterministic analytics for the connected Groww equity holdings and saved consolidated holdings:
- Groww holding count, recorded cost basis, unique-security count and largest positions by cost basis.
- An optional manual refresh of recent Yahoo Finance daily closes for recognizable NSE trading symbols, with quote date and partial-coverage disclosure.
- Consolidated portfolio KPIs for saved holding records, known cost basis, cost-data coverage and missing average costs.
- Cost-basis allocation charts by asset class and account for saved consolidated holdings.

Market quotes are indicative third-party data and may be delayed or unavailable. A partial quote total must not be interpreted as the complete portfolio value. Historical performance, unrealised P&L, sector exposure and risk analytics are not yet enabled because the current records do not provide a complete dated valuation and transaction history. The dashboard deliberately does not manufacture those metrics.

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

## Portfolio foundation (Phase 0–1 implementation)

The repository now includes:
- A SQLAlchemy portfolio schema for accounts, instruments, dated holdings, transactions, valuations, cash flows and import batches.
- A repository facade in `alphafund/storage.py`.
- Alembic baseline migration: `alembic upgrade head`.
- Starter CSV templates in `templates/` for holdings, transactions and PMS/AIF cash flows.
- Mocked Groww checksum/authentication and read-only client tests, plus module import smoke tests.

### Database setup

Local development defaults to SQLite at `data/alphafund.db`. For cloud hosting, use a managed PostgreSQL database and set `DATABASE_URL` in Streamlit Cloud → App settings → Secrets. The recommended free starting option is Neon Postgres; Supabase Postgres is an alternative. See [Free cloud database setup](docs/free-database-setup.md) for the exact steps and limitations.

Run migrations after installing requirements:

```bash
alembic upgrade head
pytest -q
```

The app also initializes missing tables at startup. The existing paper-trade ledger remains a separate local SQLite store; the consolidated portfolio records use `DATABASE_URL`.


## Portfolio entry and CSV import (Phase 2)

The dashboard now includes a consolidated portfolio section backed by the SQLAlchemy database:
- Add individual holdings manually, including account, asset type, identifier, quantity, average cost and snapshot date.
- Download the holdings CSV template, upload a populated file, validate it and review a preview before confirming import.
- CSV validation checks required columns, blank identifiers, numeric quantities/costs, valid dates and duplicate rows within the file.
- Exact-file re-imports are detected by SHA-256 checksum. Existing account/instrument/date snapshots are skipped rather than inserted twice.
- The portfolio holdings tab displays saved snapshots from the database.

The importer currently supports the holdings template only. Transaction history, CAS parsing, PMS/AIF cash-flow imports, reconciliation and Groww-to-database sync are not yet implemented. Configure a persistent PostgreSQL DATABASE_URL before relying on Streamlit Cloud for durable records; local SQLite and ephemeral cloud files are not a durable cloud database.


## Groww holdings, mutual funds and AI data flow

- The Groww Trading API portfolio endpoint documents Demat stock holdings and CASH/FNO positions. It does not currently document mutual-fund folio holdings. AlphaFund loads Groww holdings automatically when opening AI Chat if Groww credentials are configured; it also remains manually refreshable from Home. Groww records are passed separately into chat and are not silently merged with manually imported records.
- Without an OpenAI API key, local chat can still calculate Groww cost-basis totals, largest positions and top-three concentration. It does not claim these are live market values or returns. Configure `OPENAI_API_KEY` in Streamlit Secrets for broader natural-language analysis.
- Discover now downloads the latest public AMFI NAV feed and supports scheme-name search. NAV is a per-unit scheme value; it does not establish the user's units, cost basis or portfolio market value.
- Mutual-fund units should be imported from a CAS statement or entered manually using the holdings CSV template with `asset_type=mutual_fund`. Add matching per-unit NAV observations using the valuations CSV template with `observation_type=nav`.
- Mobile typography uses larger body, input and navigation text with stronger contrast. Chat input remains usable on narrow screens.


## Managed open-weight AI and local Ollama

The default provider is Hugging Face Inference Providers, a managed router for open-weight models. AlphaFund uses its OpenAI-compatible chat endpoint, so no GPU server or laptop process is required for cloud access. The default model is `openai/gpt-oss-120b:cheapest`; Hugging Face documents the `:cheapest` routing policy and the OpenAI-compatible endpoint. Model/provider availability and price can change, so check the provider dashboard before use.

### Streamlit Community Cloud secrets

Add these values in app Settings → Secrets (never commit tokens):

```toml
HF_TOKEN = "your-huggingface-token"
HUGGINGFACE_MODEL = "openai/gpt-oss-120b:cheapest"
ALPHAFUND_AI_PROVIDER = "huggingface"
ALPHAFUND_CLOUD_DATA_SHARING = "true"
```

Create an HF token with Inference Providers access at https://huggingface.co/settings/tokens. The managed provider may charge based on model/provider usage. Check current pricing and free quotas before enabling it.

**Privacy gate:** `ALPHAFUND_CLOUD_DATA_SHARING=false` is the default. While false, AlphaFund does not send portfolio records or chat context to managed inference; it uses deterministic local responses/findings. Set it to `true` only after reviewing Hugging Face and the selected inference provider's data policies. Never put tokens in GitHub or chat.

### Local Ollama alternative

For private local inference, install Ollama from https://ollama.com/, run `ollama pull qwen2.5:7b`, then set `ALPHAFUND_AI_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434` and `OLLAMA_MODEL=qwen2.5:7b`. Streamlit Community Cloud cannot reach Ollama on your laptop through localhost. Use this mode when running AlphaFund on the same machine as Ollama.

### Provider routing and financial safeguards

- `ALPHAFUND_AI_PROVIDER=huggingface` (default), `ollama`, or optional `openai`.
- Python calculates holdings, cost basis, valuation coverage and portfolio metrics; the model only interprets the supplied results.
- Missing prices/NAVs, partial coverage and stale observations remain explicit; the model must not invent market values, returns or risk statistics.
- No cloud fallback occurs silently. Live broker orders remain disabled.
- The Streamlit application and Neon database are independent of the inference provider. This keeps phone access available while the laptop is offline.


## Risk analytics, price checks and research exports

The Risk & Reports page adds:
- Weighted historical portfolio analytics for up to 20 user-entered NSE, BSE or US tickers.
- Annualised volatility, historical VaR/CVaR, maximum drawdown, asset volatility, marginal risk contribution and return correlation.
- Price threshold checks against the latest available daily bar, with separate flags for a new crossing and a threshold that is already met.
- Markdown research exports for technical, company/fundamental and portfolio-risk reports; watchlist scans and risk contributions can be downloaded as CSV.
- A transparent fundamental screening score with profitability, balance-sheet, growth and valuation pillars. It reports coverage and warnings; it is not an intrinsic-value estimate or a price target.

Risk methodology and limits:
- Weights are normalised from the user's inputs. Daily portfolio returns assume periodic rebalancing to those weights and use common complete daily observations.
- Historical VaR/CVaR are sample estimates, not guaranteed loss limits. Volatility and drawdown are backward-looking.
- Price threshold checks are manual and run only when the user presses the evaluation button. Streamlit Community Cloud does not provide a dependable always-on scheduler or push-notification service for this feature.
- Yahoo Finance via yfinance remains an indicative source and can be delayed, incomplete, stale or rate-limited.
- The fundamental score uses equal-weight heuristic pass/fail thresholds and is not sector-adjusted. It must not be used alone to rank or buy securities.
- Research reports retain sources and caveats. No live broker orders are sent.

## RSI edge-case correction

The technical RSI calculation now handles monotonic price series explicitly: no-loss windows with gains return 100, no-gain windows with losses return 0, and a flat window returns 50. This avoids treating a persistent uptrend as neutral merely because the average loss is zero.

## Operational completion checklist

Before relying on the cloud dashboard:
1. Configure APP_PASSWORD in Streamlit Community Cloud secrets.
2. Configure a persistent PostgreSQL DATABASE_URL (Neon or another managed PostgreSQL service); the local SQLite fallback is not durable across ephemeral cloud restarts.
3. Configure Groww API credentials only if you want read-only holdings sync. Groww API key approval may be required daily.
4. Configure the selected AI provider and decide explicitly whether cloud portfolio-data sharing is enabled. The default privacy gate is disabled.
5. Confirm Streamlit Community Cloud points to repository athreyap/Automated-trading, branch main, app.py, then verify the deployed app after GitHub CI passes.
6. Confirm the app password, Groww connection, database persistence, company data and market-data coverage from the running app.

Background alerts, direct CAS PDF parsing, automatic PMS/AIF statement parsing, FX conversion, corporate-action reconciliation, audited-filing ingestion and live trading are not silently claimed as implemented. Live trading remains disabled.


## Excel import and paper ledger updates

- Holdings, transactions and valuation import tabs accept CSV and XLSX/XLSM files. The same schema validation, duplicate-file checksum and preview-before-import flow applies to both formats.
- Excel workbooks are read from the first worksheet using openpyxl. Keep the same column names as the downloadable CSV templates.
- The paper ledger supports long-only BUY and SELL entries, rejects sells larger than the held quantity, computes weighted-average cost and realized P&L, and includes user-entered fee basis points.
- Existing SQLite paper-ledger files are upgraded in place with a zero-default fees column when the app starts.
- Paper ledger state is still a local SQLite file and may not persist on ephemeral Streamlit Cloud storage. It is not linked to Groww and never submits broker orders.

# AlphaFund AI — Product Scope and Delivery Plan

**Product decision:** Single-user, private investment research and portfolio workspace.  
**Interface:** Streamlit, optimised for desktop and Android browser.  
**AI strategy:** Hybrid cloud + local models.  
**Broker boundary:** Groww remains read-only. Live order placement is out of scope and disabled.

## 1. Product objective
AlphaFund AI will track existing investments, research new opportunities, analyse portfolio risk and answer questions grounded in investment records and prior AlphaFund conversations. It must distinguish verified account/statement facts, market observations, user-entered assumptions and AI-generated analysis.

## 2. Supported asset classes
**Owned:** listed equities and ETFs; mutual funds and SIPs; government securities, Treasury Bills, SDLs and corporate bonds where data is available; PMS portfolios; AIF investments; cash and manually entered assets.

**Discovery:** search and watchlists for stocks, ETFs, mutual funds and bonds; PMS/AIF provider and strategy research using public disclosures and uploaded reports; comparisons, benchmark analysis, risk indicators and hypothetical portfolios. Discovery never places orders.

## 3. Data ingestion

| Source | Initial use | Important limitation |
|---|---|---|
| Groww API | Read-only equity holdings and CASH positions supported by user permissions | Do not assume endpoints cover mutual funds, bonds, PMS or AIF |
| Excel / CSV | Holdings, transactions, NAV history and provider exports using templates | Validate columns, dates, currencies, duplicates and units |
| CAS statements | Mutual-fund folio, transaction and holding import | Support defined formats; handle protected files securely; never log passwords |
| Manual entry | Assets, transactions, SIPs, bond terms and valuations | Mark user-entered values and as-of date |
| PMS / AIF statements | Holdings, capital calls, distributions, NAVs, fees and performance | Provider formats vary; begin with templates and reviewed document extraction |

Every imported record retains source, import timestamp, source as-of date, currency, validation status and import-batch reference. Re-imports must be idempotent or show a duplicate-resolution preview.

## 4. Portfolio analytics and visualisations
- Consolidated value and allocation by asset class, instrument, sector, market cap, geography and currency where supported.
- Invested capital versus current value, realised/unrealised P&L and cash flows.
- XIRR for dated investor cash flows; CAGR only where assumptions are appropriate.
- Daily/monthly/yearly performance and benchmark comparison.
- Mutual-fund NAV history, SIP contributions and fund overlap.
- Bond coupon schedule, accrued interest where calculable, indicative YTM and maturity ladder.
- PMS/AIF reported NAV and cash-flow performance with valuation dates and lag.
- Drawdown, volatility, concentration and scenario/stress analysis.
- Watchlists and hypothetical portfolio comparisons.

Never show stale, missing or incomparable values as live. Display currency, source and as-of date.

## 5. AI investment assistant
The assistant answers questions about owned investments, research candidates, charts and prior AlphaFund conversations. Example questions:
- Summarise my portfolio and its biggest concentration risks.
- Compare my mutual funds against their benchmarks.
- Show my bond maturities and expected coupon cash flows.
- Compare this PMS factsheet with my current allocation.
- What did we previously conclude about this company?
- What happens to my portfolio in a 10% market decline scenario?

### Retrieval and memory
Use retrieval-augmented generation (RAG), not an unrestricted dump of all records into every prompt:
1. Identify the question and required data domains.
2. Query structured portfolio tables for holdings, transactions, prices and cash flows.
3. Retrieve relevant prior chat messages/summaries and uploaded document passages.
4. Attach provenance, dates and confidence to retrieved facts.
5. Separate facts, assumptions and opinions in the response.
6. Store conversation and optionally create a user-approved investment note or preference.

Do not infer goals or risk appetite from one casual message and silently persist it. Provide controls to inspect, correct and delete saved investment memories. Model-generated statements are never source-of-truth portfolio data.

### Hybrid model routing
- Cloud model: complex reasoning and synthesis when the user enables a cloud provider/key.
- Local model: privacy-sensitive summarisation, document assistance and basic Q&A when a supported local model is available.
- Deterministic Python services: returns, XIRR, allocation, risk metrics, bond cash flows and chart data.
- Show which model/service handled a request; allow cloud AI to be disabled.
- Detect local model availability and hardware requirements rather than assuming them.

## 6. Proposed application architecture

```text
Private Android / Desktop browser
              |
              v
       Streamlit UI (single user)
              |
              v
       AlphaFund application layer
       |         |          |
       v         v          v
 Portfolio   Analytics   AI assistant
 services    services    + RAG router
       |         |          |
       +---------+----------+
                 |
        PostgreSQL (persistent)
        + private object storage
                 |
     +-----------+-------------+
     |           |             |
   Groww      Market/NAV    User imports
 read-only     providers   CAS/PMS/AIF/CSV
                 |
        Cloud model / local model

No order execution path in this release.
```

### Deployment
- Keep Streamlit as the initial mobile-friendly UI.
- Use persistent database storage for portfolio records, transactions, chat history and import metadata; do not rely on ephemeral SQLite for production.
- Store uploaded statements in private encrypted object storage; store extracted data and document references in the database.
- Keep API keys and broker credentials in server-side secrets, never in Git, chat, browser storage or logs.
- Any future execution service remains separate and is not part of this roadmap unless explicitly authorised.

## 7. Security and privacy
- Single-user authentication initially with strong password and secure sessions.
- Encrypt secrets/files at rest and use HTTPS in transit.
- Restrict upload size/type and validate parsers; treat documents as untrusted input.
- Redact tokens, API keys, statement passwords and personal identifiers from logs.
- Do not send CAS/PMS/AIF documents to a cloud model unless cloud processing is explicitly enabled.
- Provide data export/deletion, audit trail, database backups and restore tests.

## 8. Delivery roadmap and acceptance criteria

### Phase 0 — Foundation and reliability
Fix and verify the outstanding Groww import/deployment issue; validate authentication against current official docs; add mocked auth tests; verify deployed commit; preserve read-only endpoint allowlist.  
**Exit:** app imports, tests pass, secrets are not exposed and errors are actionable.

### Phase 1 — Unified portfolio ledger
Define canonical instruments, accounts, holdings, transactions, cash flows, valuations and import batches. Add manual entry, CSV/XLSX templates, duplicate detection and correction workflow.  
**Exit:** sample portfolio imports, reconciles and shows source/as-of timestamp.

### Phase 2 — Mutual funds and CAS
Add fund master and AMFI NAV ingestion after validating access terms/schema; map scheme codes/ISINs and folios; parse supported CAS formats; add NAV charts, SIPs and cash-flow XIRR.  
**Exit:** test statement reconciles units/cash flows and NAV chart shows source/date.

### Phase 3 — Bonds
Add bond master and terms: issuer, ISIN, coupon, frequency, maturity, face value, rating and source. Add reliable price/yield provider only after selection; calculate coupon schedule, maturity ladder and estimated YTM with documented assumptions.  
**Exit:** calculations match independent test cases and indicative inputs are labelled.

### Phase 4 — PMS / AIF
Add provider/strategy records and template-based statements; capture contributions, distributions, fees and reported NAV; distinguish reported performance from investor XIRR.  
**Exit:** sample statement imports with source and reporting lag visible.

### Phase 5 — Analytics and charts
Build allocation, performance, cash-flow, benchmark, drawdown and risk views with date/asset filters.  
**Exit:** charts reconcile to ledger and disclose stale/missing data.

### Phase 6 — Hybrid AI assistant
Add structured portfolio tools, document retrieval, conversation search, local/cloud routing, opt-in cloud processing and citations/provenance. Add user-controlled memory save/edit/delete.  
**Exit:** evaluation confirms correct records, source attribution, no fabricated values and refusal when data is absent.

### Phase 7 — Hardening and mobile release
Add backups, monitoring, parser security tests, export/deletion and Android usability checks.  
**Exit:** restore test and end-to-end import-to-chat test pass.

## 9. Explicit non-goals
- No Groww orders, execution, modification or cancellation.
- No guarantee of real-time prices or complete PMS/AIF coverage.
- No invented valuations for private/unpriced assets.
- No automatic saving of sensitive or inferred preferences.
- No recommendations presented as certainty or substitute for independent financial/tax advice.

## 10. Decisions to validate before coding
1. Current official Groww endpoints, authentication, subscription and asset coverage.
2. Permitted market/NAV/bond providers, update frequency, licensing and cost.
3. Persistent database and private object-storage target.
4. Local model runtime/model and minimum hardware.
5. Import templates and anonymised fixtures for CAS/PMS/AIF parsers.

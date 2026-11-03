# AlphaFund AI — Engineering Implementation Plan

This plan converts the approved product scope into small, testable repository changes. Implement one phase at a time; do not begin broker execution.

## Approved configuration
- User model: single user.
- Ingestion: Groww API, Excel/CSV, CAS statements, manual entry, PMS/AIF statements.
- AI: hybrid cloud/local.
- UI: Streamlit, mobile-responsive.
- Trading: paper-only; Groww read-only.

## Target repository structure

```text
alphafund/
  config.py
  auth/
  data/
    providers/
      groww.py
      amfi.py
      market_data.py
      bonds.py
    imports/
      csv_importer.py
      cas_importer.py
      pms_importer.py
      aif_importer.py
      validation.py
  domain/
    instruments.py
    portfolio.py
    transactions.py
    cashflows.py
  analytics/
    performance.py
    allocation.py
    risk.py
    bonds.py
  storage/
    database.py
    repositories/
    migrations/
  ai/
    router.py
    cloud_provider.py
    local_provider.py
    retrieval.py
    portfolio_tools.py
    memory.py
  ui/
    pages/
      overview.py
      stocks.py
      mutual_funds.py
      bonds.py
      pms_aif.py
      discovery.py
      analytics.py
      assistant.py
tests/
  fixtures/
  unit/
  integration/
docs/
```

## Implementation sequence

### Step 0 — Stabilise the current app
Reproduce/fix the Groww import and deployment issue. Validate Groww authentication against current official docs before changing auth code. Add mocked HTTP tests; verify deployed commit; preserve read-only endpoint allowlist.  
**Exit gate:** app imports, tests pass, no credentials in repository/logs.

### Step 1 — Domain and storage foundation
Introduce canonical instrument, account, holding, transaction, cash-flow and valuation models. Select persistent PostgreSQL for production; use SQLite only for local development/tests behind the same repository interface. Add migrations, backup/restore instructions and provenance.  
**Exit gate:** migrations run from empty DB and repository tests cover CRUD/reconciliation.

### Step 2 — Import framework
Define CSV/XLSX templates and examples. Build preview → validate → confirm flow. Add manual entry. Add duplicate detection and rollback for failed batches.  
**Exit gate:** repeat import does not silently duplicate transactions; errors identify row and column.

### Step 3 — Mutual funds and CAS
Build fund master and AMFI NAV adapter after validating data access terms/schema. Map scheme codes/ISINs and folios. Parse supported CAS formats with fixtures. Add NAV history, SIP schedule and cash-flow XIRR.  
**Exit gate:** sample statement reconciles units/cash flows; NAV chart shows provider/as-of date.

### Step 4 — Bonds
Add bond terms and identifiers. Add verified reference/price adapters after provider selection. Implement coupon calendar, maturity ladder, accrued-interest assumptions and YTM calculations. Test coupon frequencies, irregular periods, maturity and clean/dirty price handling.  
**Exit gate:** calculations match independently checked cases and indicative inputs are labelled.

### Step 5 — PMS/AIF
Start with standard CSV/XLSX templates for holdings, capital calls, distributions, fees and reported NAV. Add reviewed PDF extraction separately; never auto-post extracted values. Store manager-reported NAV date separately from upload date. Calculate investor XIRR from dated cash flows; show provider-reported returns separately.  
**Exit gate:** sample statement reconciles cash flows and displays valuation lag.

### Step 6 — Analytics
Implement allocation, invested value, market/reported value, realised/unrealised P&L, XIRR, benchmark comparison and drawdown. Build interactive charts and filters. Show stale/missing-data warnings and source labels.  
**Exit gate:** chart totals reconcile to portfolio services and metrics disclose methodology.

### Step 7 — Hybrid AI assistant
Add chat persistence and retrieval over approved portfolio facts, uploaded document chunks and prior messages. Route numerical questions to deterministic Python tools. Add cloud and optional local adapters behind one interface. Make cloud processing opt-in for private documents; redact secrets and personal identifiers. Add user-controlled memory save/edit/delete and prompt-injection protections.  
**Exit gate:** evaluation confirms correct facts, source attribution, no fabricated values and correct refusal when data is absent.

### Step 8 — Deployment and hardening
Configure persistent database and private object storage. Add secure uploads, size/type limits, backups, restore drills, audit logs and Android usability checks.  
**Exit gate:** end-to-end import-to-chart-to-chat test and restore drill succeed.

## First coding batch
1. Fix and test current app/Groww import path.
2. Add domain model and repository interfaces.
3. Add database migrations and import-batch schema.
4. Add sample CSV templates and fixture data.

Do not add every integration in one large change. Build against fixtures first, then connect external providers.

## Decisions intentionally deferred
- Exact PostgreSQL and private object-storage provider.
- Bond price/yield vendor and licensing.
- Local model runtime/model and minimum hardware.
- CAS/PMS/AIF parser support matrix based on anonymised sample statements.
- Whether any future execution backend is needed. Live trading remains disabled.

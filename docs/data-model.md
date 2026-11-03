# AlphaFund AI — Canonical Data Model

This is the proposed logical model, not a database migration.

## Core entities

| Entity | Purpose | Important fields |
|---|---|---|
| user_settings | Single-user preferences | timezone, base_currency, cloud_ai_enabled, local_model_id |
| source_connection | External source metadata | provider, status, last_sync_at, scopes; never raw secrets |
| import_batch | Provenance/reconciliation | source_type, filename, imported_at, as_of_date, status, checksum |
| account | Broker, folio, PMS, AIF or manual account | account_name, provider, account_type, masked_reference |
| instrument | Canonical security master | instrument_type, name, ISIN, ticker, exchange, currency |
| instrument_identifier | Provider ID mapping | instrument_id, provider, external_id |
| holding | Dated position snapshot | account_id, instrument_id, quantity, average_cost, as_of_date, source_id |
| transaction | Purchase, sale, SIP, dividend, coupon, fee, tax, contribution or distribution | account_id, instrument_id, transaction_type, units, price, amount, date |
| cash_flow | Investor contributions and withdrawals | account_id, date, flow_type, amount, currency |
| valuation | Dated valuation observation | instrument_id, account_id, value, price_or_nav, source, as_of_date, quality |
| fund_profile | Mutual-fund metadata | AMC, scheme_code, category, benchmark, expense_ratio, riskometer |
| bond_terms | Contractual bond data | ISIN, issuer, coupon_rate, frequency, maturity_date, face_value, rating |
| private_fund_profile | PMS/AIF metadata | manager, strategy, category, benchmark, published_minimum_ticket |
| watchlist_item | Saved research candidate | instrument_id, thesis, created_at |
| chat_conversation | Chat session metadata | created_at, title |
| chat_message | Chat content and routing | conversation_id, role, content, created_at, model_route |
| memory_item | User-approved persistent context | content, category, created_at, updated_at, user_approved |
| document | Private uploaded source metadata | import_batch_id, storage_key, document_type, checksum |
| document_chunk | Searchable extracted passage | document_id, page, text, embedding_reference, extraction_status |
| audit_event | Important changes and assistant actions | event_type, timestamp, entity_reference, redacted_details |

## Asset-type handling
- **Equity/ETF:** quantity, average cost, exchange, ticker/ISIN, corporate actions and market-price observations.
- **Mutual fund:** scheme code/ISIN, folio, units, NAV date, SIP and transaction cash flows.
- **Bond:** face value, units, coupon terms, payment frequency, maturity, rating and dated price/yield observations.
- **PMS:** account/strategy, reported holdings where supplied, capital calls, withdrawals, fees and reported NAV dates.
- **AIF:** fund/commitment, drawdowns, distributions, fees, reported NAV and vintage/strategy metadata.
- **Cash:** currency, account, dated balance and source.

Do not force private-fund NAVs, bond yields and mutual-fund NAVs into identical price semantics. Store observation type, unit, currency, source and as-of date.

## Data integrity rules
1. All monetary values carry ISO currency; INR is initial display/base currency.
2. Store timestamps in UTC and business/as-of dates separately. Display Asia/Kolkata by default.
3. Preserve immutable source imports with checksums and batch references.
4. Keep source values separate from normalised/corrected values.
5. Prevent duplicate transactions using provider IDs or conservative fingerprints; ambiguous matches require review.
6. Append valuations; never overwrite historical observations.
7. Holdings are snapshots; transactions/cash flows are the ledger. Reconciliation explains differences.
8. Missing market prices remain missing. Any last-known price must be labelled with its age.
9. Distinguish market value, invested cost, reported NAV, face value and estimated redemption value.
10. XIRR uses dated investor cash flows; instrument CAGR is not a substitute for investor-level return.

## AI retrieval contract
- Numerical questions call deterministic portfolio/analytics functions.
- Document questions retrieve passages with filename, page and as-of date.
- Historical-chat questions retrieve prior messages/summaries, not model recollection.
- AI output retains provenance and marks estimates/assumptions.
- The model cannot directly write holdings, valuations or transactions; proposed corrections require user review.
- Only user-approved memory items become durable preference/context records.

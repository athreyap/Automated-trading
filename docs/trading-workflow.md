# AlphaFund trading-workflow redesign

AlphaFund is being reorganised around a staged, specialist workflow inspired by
[day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill), adapted
for NSE, BSE and US equities and for AlphaFund's existing portfolio database.

## Target workflow

`Universe / Watchlist → Scanner → News & Company Intel → Setup / Entry Review
→ Exit Plan → Historical Replay → Position Sizing → Risk Gate → Paper Ledger`

- **Scanner:** reuse AlphaFund's multi-market technical research and add setup
  detectors (trend continuation, range breakout, pullback and oversold rebound).
- **News / analyst:** enrich candidates with timestamped company news, filings
  and fundamental context. Missing feeds must be shown as unavailable.
- **Entry review:** evaluate completed bars only; never label a forming bar as
  triggered.
- **Exit planner:** require a directional invalidation stop and target before
  sizing; show reward/risk and gap/slippage caveats.
- **Time Machine:** replay a fixed setup against historical observations and
  disclose sample size, assumptions and limitations. A simulation is not a
  forecast.
- **Budget manager:** calculate units from max loss, position cap, order cap
  and available cash; do not silently change user limits.
- **Risk gate:** return PASS/BLOCK with reasons. PASS is not a trade approval.
- **Paper ledger:** record only explicitly confirmed simulated trades.

## AlphaFund-specific scope

- Keep Groww read-only and retain consolidated holdings, mutual-fund NAVs,
  bonds, PMS/AIF imports and existing portfolio analytics.
- Make the workflow usable for NSE, BSE and US equities. Currency is explicit
  per market; never combine INR and USD without a verified FX conversion.
- Keep the portfolio assistant read-only and let it explain the scanner,
  analyst, replay, sizing and risk outputs from the same structured snapshot.
- Use timestamped market data, source labels and stale-data warnings.

## Safety boundary

This redesign is research-first and paper-only. No live broker connector,
order endpoint, automatic order placement, short selling, margin, options or
leverage is introduced. Groww remains a read-only portfolio source. A future
execution feature would require a separate explicit product decision, security
review and independent approval workflow.

## Implementation status

This PR establishes the deterministic plan, sizing, risk-gate, replay and
workflow hand-off primitives with offline tests. UI integration, symbol
universe discovery, intraday data validation, alert scheduling and multi-user
authentication are subsequent implementation steps; they must not be treated
as complete until merged, deployed and verified.

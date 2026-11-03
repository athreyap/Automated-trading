import streamlit as st
import pandas as pd
import hmac
import os
from alphafund.config import settings
from alphafund.market_data import fetch_history, normalize_symbol
from alphafund.strategy import add_indicators, latest_signal, backtest
from alphafund.paper_broker import initialize_ledger, list_trades, record_paper_trade, paper_cash
from alphafund.ai_explainer import explain_signal
from alphafund.groww_client import GrowwReadOnlyClient, GrowwAPIError, generate_access_token


def get_secret(name: str) -> str:
    value = os.getenv(name, "")
    try:
        value = value or str(st.secrets.get(name, ""))
    except Exception:
        pass
    return value.strip()


def require_app_login() -> None:
    password = get_secret("APP_PASSWORD")
    if not password:
        st.error("Dashboard locked. Configure APP_PASSWORD in Streamlit Cloud secrets before publishing.")
        st.stop()
    if st.session_state.get("authenticated"):
        return
    st.title("AlphaFund AI — Sign in")
    entered = st.text_input("Dashboard password", type="password")
    if st.button("Sign in", type="primary"):
        if hmac.compare_digest(entered, password):
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


st.set_page_config(page_title="AlphaFund AI V1", page_icon="📈", layout="wide")
require_app_login()
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#f6f8f7; }
[data-testid="stHeader"] { background:rgba(246,248,247,.92); }
.block-container { max-width:1440px; padding-top:1.35rem; padding-bottom:3rem; }
h1,h2,h3 { letter-spacing:-.035em; color:#14251f; }
[data-testid="stMetric"] { background:#fff; border:1px solid #e5ece8; border-radius:16px; padding:16px 18px; box-shadow:0 2px 10px rgba(20,50,38,.035); }
[data-testid="stMetricLabel"] p { color:#63756d; font-size:.82rem; }
[data-testid="stMetricValue"] { color:#14251f; font-weight:700; }
.stButton > button[kind="primary"], .stFormSubmitButton > button { background:#00a878; border-color:#00a878; border-radius:10px; font-weight:650; }
.stButton > button { border-radius:10px; }
[data-testid="stTabs"] button { font-weight:650; }
div[data-testid="stRadio"] { position:fixed; left:0; right:0; bottom:0; z-index:999; background:#fff; border-top:1px solid #e4ece7; padding:10px max(12px, env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left)); box-shadow:0 -5px 20px rgba(20,50,38,.08); }
div[data-testid="stRadio"] > label { display:none; }
div[data-testid="stRadio"] > div { justify-content:space-around; gap:4px; }
div[data-testid="stRadio"] label { font-size:.82rem; font-weight:650; }
.block-container { padding-bottom:6.5rem; }
[data-testid="stDataFrame"] { border:1px solid #e5ece8; border-radius:12px; overflow:hidden; }
[data-testid="stChatMessage"] { background:#fff; border:1px solid #e8efeb; border-radius:14px; }
[data-testid="stSidebar"] { background:#fff; border-right:1px solid #e8efeb; }
[data-testid="stAlert"] { border-radius:12px; }
.af-eyebrow { color:#00a878; font-size:.78rem; font-weight:750; letter-spacing:.1em; text-transform:uppercase; }
.af-subtitle { color:#687970; font-size:.95rem; margin-top:-.5rem; }
</style>
""", unsafe_allow_html=True)
settings.validate()
initialize_ledger()

st.markdown('<div class="af-eyebrow">Your wealth, in one place</div>', unsafe_allow_html=True)
st.title("AlphaFund")
st.markdown('<div class="af-subtitle">Portfolio • Markets • Insights • AI assistant</div>', unsafe_allow_html=True)
st.caption("Groww-inspired portfolio experience · Groww connection is read-only · Live orders are disabled")
st.warning("Research software only. Signals are not investment advice. Market data can be delayed.")

with st.sidebar:
    st.header("Portfolio controls")
    st.metric("Initial capital", f"₹{settings.initial_capital:,.2f}")
    st.metric("Strategy allocation", f"₹{settings.trading_allocation:,.2f}")
    st.metric("Protected reserve", f"₹{settings.protected_reserve:,.2f}")
    st.metric("Paper cash remaining", f"₹{paper_cash(settings.trading_allocation):,.2f}")
    st.caption("Groww integration is read-only. No broker orders can be sent.")
    if st.button("Sign out"):
        st.session_state.pop("authenticated", None)
        st.rerun()


from datetime import date
from alphafund.storage import PortfolioStore
from alphafund.imports import validate_holdings_csv

configured_database_url = get_secret("DATABASE_URL")
if configured_database_url:
    os.environ["DATABASE_URL"] = configured_database_url

@st.cache_resource
def portfolio_store():
    store = PortfolioStore()
    store.initialize()
    return store

portfolio = portfolio_store()

# App-wide navigation
page = st.radio("Main navigation", ["Home", "Portfolio", "Discover", "AI Chat"], horizontal=True,
                label_visibility="collapsed", key="main_navigation")
st.markdown('<div class="af-subtitle">Home  ·  Portfolio  ·  Discover  ·  AI Chat</div>', unsafe_allow_html=True)

if page == "Home":
    st.subheader("Groww portfolio — read only")
    groww_access_token = get_secret("GROWW_ACCESS_TOKEN")
    groww_api_key = get_secret("GROWW_API_KEY")
    groww_api_secret = get_secret("GROWW_API_SECRET")
    if not groww_access_token and not (groww_api_key and groww_api_secret):
        st.info("Configure either GROWW_ACCESS_TOKEN, or both GROWW_API_KEY and GROWW_API_SECRET in Streamlit Secrets.")
    else:
        st.caption("Authentication: " + ("direct access token" if groww_access_token else "API key + secret (daily approval required in Groww Cloud)"))
        if st.button("Refresh Groww portfolio"):
            try:
                token = groww_access_token or generate_access_token(groww_api_key, groww_api_secret)
                holdings, positions = GrowwReadOnlyClient(token).get_portfolio()
                st.session_state["groww_holdings"] = holdings
                st.session_state["groww_positions"] = positions
                st.session_state["groww_refreshed"] = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%d %b %Y, %I:%M:%S %p IST")
                st.success("Groww portfolio refreshed successfully.")
            except GrowwAPIError as exc:
                st.error(str(exc))
        if "groww_holdings" in st.session_state:
            st.caption(f"Last refreshed: {st.session_state.get('groww_refreshed', 'Unknown')}")
            holdings = st.session_state["groww_holdings"]
            positions = st.session_state["groww_positions"]
            if holdings:
                hdf = pd.DataFrame(holdings)
                quantity = pd.to_numeric(hdf.get("quantity", pd.Series(0, index=hdf.index)), errors="coerce").fillna(0)
                average_price = pd.to_numeric(hdf.get("average_price", pd.Series(0, index=hdf.index)), errors="coerce").fillna(0)
                hdf["invested_value"] = quantity * average_price
                st.metric("Holdings cost value", f"₹{hdf['invested_value'].sum():,.2f}")
                columns = [col for col in ["trading_symbol", "quantity", "average_price", "invested_value", "isin"] if col in hdf.columns]
                st.dataframe(hdf[columns], use_container_width=True, hide_index=True)
    
                st.caption("Cost value = quantity × average purchase price. This is not current market value or unrealised P&L.")
                st.markdown("#### Groww analytics")
                if "trading_symbol" in hdf:
                    by_symbol = hdf.assign(invested_value=hdf["invested_value"]).groupby("trading_symbol")["invested_value"].sum().sort_values(ascending=False).head(10)
                    st.markdown("**Largest positions by recorded cost basis**")
                    st.bar_chart(by_symbol)
                    st.caption("Ranked by quantity × average purchase price; this is not live market value.")
                g1, g2, g3 = st.columns(3)
                g1.metric("Equity holdings", f"{len(hdf):,}")
                g2.metric("Recorded cost basis", f"₹{hdf['invested_value'].sum():,.2f}")
                g3.metric("Unique securities", str(hdf["isin"].nunique()) if "isin" in hdf else "N/A")
                with st.expander("Indicative market-price check"):
                    st.caption("Optional recent Yahoo Finance daily closes for recognizable NSE symbols. Quotes may be delayed and coverage may be partial.")
                    if st.button("Fetch indicative prices", key="groww_quote_refresh"):
                        from alphafund.market_data import fetch_history
                        quote_rows = []
                        for _, holding in hdf.iterrows():
                            symbol_value = str(holding.get("trading_symbol", "")).strip()
                            if not symbol_value or symbol_value.lower() == "nan":
                                continue
                            try:
                                history = fetch_history(symbol_value, period="5d")
                                close = float(history["Close"].dropna().iloc[-1])
                                qty = float(holding.get("quantity", 0))
                                quote_rows.append({"Symbol": symbol_value, "Quantity": qty,
                                    "Last daily close (₹)": close, "Indicative value (₹)": qty * close,
                                    "Quote date": str(history.index[-1].date())})
                            except Exception:
                                quote_rows.append({"Symbol": symbol_value, "Quantity": holding.get("quantity"),
                                    "Last daily close (₹)": None, "Indicative value (₹)": None,
                                    "Quote date": "Unavailable"})
                        st.session_state["groww_indicative_quotes"] = quote_rows
                    if st.session_state.get("groww_indicative_quotes"):
                        quote_df = pd.DataFrame(st.session_state["groww_indicative_quotes"])
                        st.dataframe(quote_df, use_container_width=True, hide_index=True)
                        quoted = quote_df.dropna(subset=["Indicative value (₹)"])
                        if not quoted.empty:
                            st.metric("Indicative value of quoted positions", f"₹{quoted['Indicative value (₹)'].sum():,.2f}")
                        st.caption("Partial quote coverage is possible. This is not a broker valuation or portfolio return.")
            else:
                st.info("Groww returned no equity holdings.")
            if positions:
                st.markdown("**Positions (CASH segment)**")
                pdf = pd.DataFrame(positions)
                cols = [col for col in ["trading_symbol", "product", "quantity", "net_price", "realised_pnl", "exchange"] if col in pdf.columns]
                st.dataframe(pdf[cols], use_container_width=True, hide_index=True)
            else:
                st.info("Groww returned no CASH positions.")
        else:
            st.caption("Select Refresh to retrieve your holdings and CASH positions.")
    st.divider()
    st.divider()
    st.subheader("Your investment workspace")
    h1, h2, h3 = st.columns(3)
    h1.metric("Saved portfolio records", f"{len(portfolio.list_holdings()):,}")
    h2.metric("Saved transactions", f"{len(portfolio.list_transactions()):,}")
    h3.metric("Saved valuations", f"{len(portfolio.list_valuations()):,}")
    st.info("Use Portfolio to manage holdings and performance, Discover to research securities, or AI Chat to ask questions about your investment data.")

elif page == "Discover":

    st.divider()
    st.subheader("Mutual fund research")
    st.caption("Mutual-fund NAV lookup and scheme comparison are being connected to AMFI data. Do not use a stock quote as a mutual-fund NAV.")
    st.link_button("Open AMFI NAV data", "https://www.amfiindia.com/net-asset-value/nav-history")
    st.subheader("Research coverage")
    st.write("Equities: historical prices and technical indicators are available above. Mutual funds: AMFI NAV integration is the next data-source milestone. Bonds, PMS and AIF: use the portfolio import tools until dedicated market/manager feeds are connected.")

    symbol_input = st.text_input("NSE symbol", value="RELIANCE", help="Enter a ticker such as RELIANCE, TCS, INFY or SBIN.")
    period = st.selectbox("History", ["3mo", "6mo", "1y", "2y", "5y"], index=1)
    
    if st.button("Fetch market data and analyse", type="primary"):
        try:
            symbol = normalize_symbol(symbol_input)
            data = fetch_history(symbol, period=period)
            st.session_state["analysis_data"] = data
            st.session_state["analysis_symbol"] = symbol
        except Exception as exc:
            st.error(str(exc))
    
    if "analysis_data" in st.session_state:
        data = st.session_state["analysis_data"]
        symbol = st.session_state["analysis_symbol"]
        enriched = add_indicators(data)
        signal = latest_signal(data)
        st.subheader(symbol)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Latest close", f"₹{signal.get('close', float(data['Close'].iloc[-1])):,.2f}")
        c2.metric("Rule signal", signal["signal"])
        c3.metric("RSI (14)", f"{signal.get('rsi', 0):.1f}")
        c4.metric("Data rows", str(len(data)))
        st.write(signal.get("reason", ""))
        st.line_chart(enriched[["Close", "SMA_20", "SMA_50"]].dropna())
        with st.expander("AI explanation"):
            st.write(explain_signal(signal, settings.openai_api_key, settings.openai_model))
        result = backtest(data, settings.trading_allocation)
        b1, b2, b3 = st.columns(3)
        b1.metric("Illustrative backtest value", f"₹{result['final_value']:,.2f}")
        b2.metric("Backtest return", f"{result['return_pct']:.2f}%")
        b3.metric("Position changes", str(result["trades"]))
        st.caption("Backtest is a simplified moving-average regime test. It excludes brokerage, taxes, slippage and corporate-action edge cases.")
    
    st.divider()
    st.subheader("Paper trade entry")
    st.caption("V1 records BUY entries only; full holdings and SELL accounting are not yet implemented.")
    with st.form("paper_trade"):
        col1, col2, col3 = st.columns(3)
        trade_symbol = col1.text_input("Symbol", value=symbol_input.upper())
        quantity = col2.number_input("Quantity", min_value=1, max_value=100000, value=1, step=1)
        price = col3.number_input("Entry price (₹)", min_value=0.01, value=100.0, step=0.05)
        submitted = st.form_submit_button("Record paper BUY")
        if submitted:
            try:
                amount = record_paper_trade(trade_symbol, "BUY", int(quantity), float(price),
                                            paper_cash(settings.trading_allocation),
                                            settings.trading_allocation)
                st.success(f"Recorded paper BUY for ₹{amount:,.2f}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    
    st.subheader("Paper ledger")
    trades = list_trades()
    if trades:
        st.dataframe(pd.DataFrame(trades, columns=["Timestamp (UTC)", "Symbol", "Side", "Quantity", "Price", "Notional"]), use_container_width=True)
    else:
        st.info("No paper trades recorded yet.")

elif page == "Portfolio":
    st.divider()
    st.header("Consolidated portfolio")
    manual_tab, csv_tab, holdings_tab, transactions_tab, valuations_tab, performance_tab = st.tabs(["Add holding", "Import holdings", "Holdings", "Import transactions", "Import valuations", "Performance & P&L"])
    
    with manual_tab:
        with st.form("manual_holding"):
            m1, m2, m3 = st.columns(3)
            account_name = m1.text_input("Account name", placeholder="Groww Demat")
            account_type = m2.selectbox("Account type", ["broker", "mutual_fund", "bond", "pms", "aif", "cash"])
            provider = m3.text_input("Provider", value="manual")
            m4, m5, m6 = st.columns(3)
            asset_type = m4.selectbox("Asset type", ["equity", "etf", "mutual_fund", "bond", "pms", "aif", "cash"])
            instrument_name = m5.text_input("Investment name")
            identifier = m6.text_input("Identifier / ISIN / symbol")
            m7, m8, m9 = st.columns(3)
            holding_quantity = m7.number_input("Quantity / units", min_value=0.0, value=1.0, step=1.0)
            average_cost = m8.number_input("Average cost per unit (₹)", min_value=0.0, value=0.0, step=1.0)
            as_of_date = m9.date_input("Snapshot date", value=date.today())
            manual_submit = st.form_submit_button("Save holding", type="primary")
            if manual_submit:
                try:
                    if not all(x.strip() for x in [account_name, provider, instrument_name, identifier]):
                        raise ValueError("Account, provider, investment name and identifier are required.")
                    account_id = portfolio.add_account(account_name, account_type, provider)
                    instrument_id = portfolio.add_instrument(asset_type, instrument_name, identifier)
                    portfolio.add_holding(account_id, instrument_id, holding_quantity, as_of_date,
                                           average_cost if average_cost > 0 else None)
                    st.success("Holding saved to the consolidated portfolio.")
                except Exception as exc:
                    st.error(f"Could not save holding: {exc}")
    
    with csv_tab:
        st.caption("Upload a CSV using the holdings template. The app validates the full file before importing.")
        st.download_button("Download holdings CSV template",
            data="account_name,account_type,provider,asset_type,instrument_name,identifier,exchange,currency,quantity,average_cost,as_of_date\nMy Broker Account,broker,manual,equity,Example Company,EXAMPLE,NSE,INR,10,125.50,2026-11-03\n",
            file_name="alphafund_holdings_template.csv", mime="text/csv")
        upload = st.file_uploader("Choose holdings CSV", type=["csv"], key="holdings_csv_upload")
        if upload is not None:
            try:
                preview, checksum = validate_holdings_csv(upload.getvalue())
                st.success(f"Validated {len(preview)} rows. Review the preview before importing.")
                st.dataframe(preview, use_container_width=True, hide_index=True)
                if st.button("Import validated holdings", type="primary"):
                    result = portfolio.import_holdings(preview.to_dict(orient="records"), upload.name, checksum)
                    if result["duplicate_file"]:
                        st.warning("This exact CSV file was already imported. No rows were added.")
                    else:
                        st.success(f"Import complete: {result['inserted']} added, {result['skipped']} existing snapshots skipped.")
                    st.rerun()
            except Exception as exc:
                st.error(f"CSV validation failed: {exc}")
    
    with holdings_tab:
        current_holdings = portfolio.list_holdings()
        if current_holdings:
            from alphafund.analytics import holdings_frame, portfolio_summary, allocation_by
            saved_frame = holdings_frame(current_holdings)
            summary = portfolio_summary(saved_frame)
            st.markdown("#### Consolidated portfolio overview")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Holding records", f"{summary['holding_count']:,}")
            k2.metric("Known recorded cost basis", f"₹{summary['cost_basis']:,.2f}")
            k3.metric("Cost data coverage", f"{summary['cost_coverage_pct']:.1f}%")
            k4.metric("Missing average cost", f"{summary['missing_cost_count']:,}")
            st.caption("Cost basis includes only records with a recorded average cost. Multiple dated snapshots may exist; this register is not a deduplicated current-position valuation.")
            left, right = st.columns(2)
            with left:
                st.markdown("**Cost basis by asset class**")
                asset_alloc = allocation_by(saved_frame, "asset_type")
                if not asset_alloc.empty:
                    st.bar_chart(asset_alloc.set_index("asset_type")["cost_basis"])
                else:
                    st.info("No cost basis available for this chart.")
            with right:
                st.markdown("**Cost basis by account**")
                account_alloc = allocation_by(saved_frame, "account")
                if not account_alloc.empty:
                    st.bar_chart(account_alloc.set_index("account")["cost_basis"])
                else:
                    st.info("No account-level cost basis available.")
            st.markdown("**Saved holdings and data quality**")
            st.dataframe(saved_frame, use_container_width=True, hide_index=True)
            st.caption("Performance, unrealised P&L, sector exposure and risk metrics require dated market valuations and/or transaction history. They are not estimated from purchase cost.")
        else:
            st.info("No consolidated holdings yet. Add a holding manually or import the CSV template.")
    
    
    with transactions_tab:
        st.caption("Import broker transaction history. BUY/SIP/contribution amounts are treated as investor outflows; SELL/dividend/coupon/distribution amounts as inflows for XIRR.")
        st.download_button("Download transactions CSV template",
            data="account_name,account_type,provider,asset_type,instrument_name,identifier,transaction_type,transaction_date,quantity,price,amount,currency,external_id,notes\nGroww Demat,broker,groww,equity,Reliance,RELIANCE,BUY,2026-10-01,2,1200,2400,INR,TXN-001,Example only\n",
            file_name="alphafund_transactions_template.csv", mime="text/csv")
        from alphafund.imports import validate_transactions_csv
        tx_upload = st.file_uploader("Upload transactions CSV", type=["csv"], key="transactions_csv_upload")
        if tx_upload is not None:
            try:
                tx_preview, tx_checksum = validate_transactions_csv(tx_upload.getvalue())
                st.success(f"Validated {len(tx_preview)} transactions. Review before importing.")
                st.dataframe(tx_preview, use_container_width=True, hide_index=True)
                if st.button("Import transactions", type="primary"):
                    result = portfolio.import_transactions(tx_preview.to_dict(orient="records"), tx_upload.name, tx_checksum)
                    if result["duplicate_file"]:
                        st.warning("This exact file was already imported.")
                    else:
                        st.success(f"Imported {result['inserted']}; skipped {result['skipped']} duplicates.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Transaction CSV validation failed: {exc}")
        existing_transactions = portfolio.list_transactions()
        if existing_transactions:
            st.markdown("**Imported transaction ledger**")
            st.dataframe(pd.DataFrame(existing_transactions), use_container_width=True, hide_index=True)
    
    with valuations_tab:
        st.caption("Import dated observations. Use observation_type=market_value for total position value, or price/nav for per-unit values.")
        st.download_button("Download valuation CSV template",
            data="account_name,provider,asset_type,instrument_name,identifier,valuation_date,value,observation_type,source,quality,currency\nGroww Demat,groww,equity,Reliance,RELIANCE,2026-11-03,2500,price,Yahoo Finance,indicative,INR\n",
            file_name="alphafund_valuations_template.csv", mime="text/csv")
        from alphafund.imports import validate_valuations_csv
        val_upload = st.file_uploader("Upload valuations CSV", type=["csv"], key="valuations_csv_upload")
        if val_upload is not None:
            try:
                val_preview, val_checksum = validate_valuations_csv(val_upload.getvalue())
                st.success(f"Validated {len(val_preview)} valuation observations. Review before importing.")
                st.dataframe(val_preview, use_container_width=True, hide_index=True)
                if st.button("Import valuations", type="primary"):
                    result = portfolio.import_valuations(val_preview.to_dict(orient="records"), val_upload.name, val_checksum)
                    if result["duplicate_file"]:
                        st.warning("This exact file was already imported.")
                    else:
                        st.success(f"Imported {result['inserted']}; skipped {result['skipped']} duplicates.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Valuation CSV validation failed: {exc}")
        existing_valuations = portfolio.list_valuations()
        if existing_valuations:
            st.markdown("**Valuation history**")
            st.dataframe(pd.DataFrame(existing_valuations), use_container_width=True, hide_index=True)
    
    with performance_tab:
        from alphafund.analytics import valuation_enriched_holdings, investor_xirr, portfolio_valuation_history
        saved_holdings = portfolio.list_holdings()
        saved_valuations = portfolio.list_valuations()
        saved_transactions = portfolio.list_transactions()
        if not saved_holdings:
            st.info("Import holdings first, then add matching valuation observations.")
        else:
            latest_frame = pd.DataFrame(saved_holdings)
            latest_frame["as_of_date"] = pd.to_datetime(latest_frame["as_of_date"], errors="coerce")
            latest_frame = latest_frame.sort_values("as_of_date").drop_duplicates(["account", "identifier"], keep="last")
            current_records = latest_frame.to_dict(orient="records")
            valued = valuation_enriched_holdings(current_records, saved_valuations)
            valued_rows = valued.dropna(subset=["market_value"])
            known_cost = valued["cost_basis"].notna()
            total_market_value = float(valued_rows["market_value"].sum())
            total_cost = float(valued.loc[known_cost, "cost_basis"].sum())
            complete_value_coverage = len(valued_rows) == len(valued)
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Valued positions", f"{len(valued_rows):,} / {len(valued):,}")
            p2.metric("Latest reported / indicative value", f"₹{total_market_value:,.2f}" if len(valued_rows) else "Unavailable")
            pnl = float((valued_rows["unrealised_pnl"].dropna()).sum())
            pnl_coverage = len(valued_rows.dropna(subset=["unrealised_pnl"])) == len(valued)
            p3.metric("Unrealised P&L", f"₹{pnl:,.2f}" if pnl_coverage and complete_value_coverage else "Partial / unavailable")
            p4.metric("Return on recorded cost", f"{(pnl / total_cost * 100):.2f}%" if pnl_coverage and complete_value_coverage and total_cost > 0 else "Unavailable")
            st.caption("Latest matching valuation per account/security is used. P&L and return are shown only when all current positions have both a valuation and recorded cost. Values across mixed currencies are not converted; use one currency per portfolio.")
            if len(valued_rows):
                st.markdown("**Position valuation and unrealised P&L**")
                st.dataframe(valued[["account", "instrument", "identifier", "quantity", "cost_basis",
                    "market_value", "unrealised_pnl", "valuation_date", "valuation_source"]], use_container_width=True, hide_index=True)
            history = portfolio_valuation_history(saved_valuations)
            if not history.empty:
                st.markdown("**Reported portfolio valuation history**")
                history["valuation_date"] = pd.to_datetime(history["valuation_date"])
                st.line_chart(history.set_index("valuation_date")["portfolio_value"])
                st.caption("History includes only explicit total market_value observations in a single currency. Price and NAV observations are not summed as position values.")
            else:
                st.info("No portfolio history chart yet. Import total market_value observations for each position and date.")
            if saved_transactions:


elif page == "AI Chat":
                    terminal_value=total_market_value if complete_value_coverage else None,
                    terminal_date=pd.Timestamp.now().date() if complete_value_coverage else None)
                st.metric("Investor XIRR", f"{xirr_value * 100:.2f}%" if xirr_value is not None and complete_value_coverage else "Not enough complete cash-flow data")
                st.caption("XIRR uses imported dated transaction amounts plus the latest complete portfolio value as terminal value. Review transaction signs/types and ensure transaction history is complete before relying on this metric.")
            else:
                st.info("Import transaction history to calculate investor-level XIRR.")
    
    
    # Portfolio-aware AI assistant
    st.divider()
    st.markdown('<div class="af-eyebrow">AlphaFund intelligence</div>', unsafe_allow_html=True)
    st.header("Ask AlphaFund")
    st.caption("Ask questions about your holdings, allocation, transactions, NAVs, valuations and investment research. Answers use the data available in this app.")
    from alphafund.portfolio_chat import build_portfolio_context, answer_portfolio_question
    chat_holdings = portfolio.list_holdings()
    chat_valuations = portfolio.list_valuations()
    chat_transactions = portfolio.list_transactions()
    chat_context = build_portfolio_context(
        holdings=chat_holdings,
        valuations=chat_valuations,
        transactions=chat_transactions,
        groww_holdings=st.session_state.get("groww_holdings", []),
    )
    if "alphafund_chat" not in st.session_state:
        st.session_state["alphafund_chat"] = [{
            "role": "assistant",
            "content": "Hello. I’m your AlphaFund portfolio assistant. I can help review your recorded investments, explain portfolio metrics and identify missing data. What would you like to understand?"
        }]
    for chat_item in st.session_state["alphafund_chat"]:
        with st.chat_message(chat_item["role"]):
            st.markdown(chat_item["content"])
    chat_question = st.chat_input("Ask about your portfolio, returns, mutual funds or a stock…")
    if chat_question:
        st.session_state["alphafund_chat"].append({"role": "user", "content": chat_question})
        chat_reply = answer_portfolio_question(
            chat_question, chat_context,
            api_key=get_secret("OPENAI_API_KEY"),
            model=get_secret("OPENAI_MODEL") or settings.openai_model,
            history=st.session_state["alphafund_chat"][:-1],
        )
        st.session_state["alphafund_chat"].append({"role": "assistant", "content": chat_reply})
        st.rerun()
    if st.button("Clear chat history", key="clear_alphafund_chat"):
        st.session_state["alphafund_chat"] = []
        st.rerun()
    st.caption(f"Context currently loaded: {len(chat_holdings)} saved holdings · {len(st.session_state.get('groww_holdings', []))} Groww holdings · {len(chat_transactions)} transactions · {len(chat_valuations)} valuations. Chat history is held in this Streamlit session.")
    

import streamlit as st
import pandas as pd
import hmac
import os
import re
from alphafund.config import settings
from alphafund.market_data import fetch_history, normalize_symbol
from alphafund.strategy import add_indicators, latest_signal, backtest
from alphafund.paper_broker import initialize_ledger, list_trades, record_paper_trade, paper_cash, paper_positions
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
:root { color-scheme: light; font-size:16px; }
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif !important;
    font-size:16px !important;
}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stText"], .stText, .stMarkdown { font-size:16px !important; line-height:1.55 !important; }
[data-testid="stCaption"], [data-testid="stCaption"] p { font-size:13px !important; line-height:1.45 !important; color:#52665c !important; }
label, [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p { font-size:15px !important; color:#17251f !important; }
[data-testid="stChatMessage"] p { font-size:15px !important; line-height:1.55 !important; }
[data-testid="stChatInput"] textarea { font-size:16px !important; color:#17251f !important; }
[data-testid="stRadio"] label, [data-testid="stRadio"] label p { font-size:14px !important; color:#26372f !important; }
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"] { background:#f6f8f7 !important; color:#17251f !important; }
[data-testid="stHeader"] { background:rgba(246,248,247,.96) !important; }
.block-container { max-width:1440px; padding-top:1.35rem; padding-bottom:7rem; }
h1,h2,h3,h4,h5,h6,[data-testid="stMarkdownContainer"] p,[data-testid="stMarkdownContainer"] li,[data-testid="stMarkdownContainer"] span,[data-testid="stText"],[data-testid="stCaption"],[data-testid="stWidgetLabel"],[data-testid="stMetricLabel"],[data-testid="stAlert"] p,label,.stMarkdown,.stText { color:#17251f !important; }
h1,h2,h3 { letter-spacing:-.035em; font-weight:700 !important; }
[data-testid="stCaption"] { color:#607269 !important; }
[data-testid="stMetric"] { background:#fff; border:1px solid #e5ece8; border-radius:16px; padding:16px 18px; box-shadow:0 2px 10px rgba(20,50,38,.035); }
[data-testid="stMetricLabel"] p { color:#63756d !important; font-size:.82rem; }
[data-testid="stMetricValue"] { color:#14251f !important; font-weight:700; }
.stButton > button[kind="primary"], .stFormSubmitButton > button { background:#00a878; border-color:#00a878; color:#fff !important; border-radius:10px; font-weight:650; }
.stButton > button { border-radius:10px; }
[data-testid="stTabs"] button { font-weight:650; }
[data-testid="stDataFrame"] { border:1px solid #e5ece8; border-radius:12px; overflow:hidden; }
[data-testid="stChatMessage"] { background:#fff; border:1px solid #e8efeb; border-radius:14px; }
[data-testid="stSidebar"] { background:#fff; border-right:1px solid #e8efeb; }
[data-testid="stAlert"] { border-radius:12px; }
.af-eyebrow { color:#008b63 !important; font-size:.78rem; font-weight:750; letter-spacing:.1em; text-transform:uppercase; }
.af-subtitle { color:#687970 !important; font-size:.95rem; margin-top:-.5rem; }
/* Mobile navigation: left aligned with readable labels. */
div[data-testid="stRadio"] { position:fixed; left:0; right:0; bottom:0; z-index:999; background:#fff; border-top:1px solid #e4ece7; padding:10px max(12px, env(safe-area-inset-right)) calc(10px + env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); box-shadow:0 -5px 20px rgba(20,50,38,.08); }
div[data-testid="stRadio"] > label { display:none !important; }
div[data-testid="stRadio"] > div { display:flex !important; justify-content:flex-start !important; align-items:center !important; gap:clamp(16px, 5vw, 32px) !important; flex-wrap:nowrap !important; overflow-x:auto; }
div[data-testid="stRadio"] label { color:#26372f !important; font-size:.82rem !important; font-weight:650 !important; white-space:nowrap !important; }
div[data-testid="stRadio"] label p { color:#26372f !important; }
div[data-testid="stRadio"] [role="radiogroup"] { justify-content:flex-start !important; }
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
page = st.radio("Main navigation", ["Home", "Portfolio", "Discover", "Research", "Company Intel", "Risk & Reports", "AI Chat"], horizontal=True,
                label_visibility="collapsed", key="main_navigation")

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
                hdf["channel"] = "Groww"
                st.metric("Holdings cost value", f"₹{hdf['invested_value'].sum():,.2f}")
                columns = [col for col in ["trading_symbol", "quantity", "average_price", "invested_value", "isin", "channel"] if col in hdf.columns]
                st.dataframe(hdf[columns].rename(columns={"channel": "Channel"}), use_container_width=True, hide_index=True)
    
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
    st.subheader("Mutual funds")
    st.caption("Latest scheme NAVs are sourced from AMFI. NAV is per unit and is not your holding value; add your units and purchase history through Portfolio imports.")
    if st.button("Load latest AMFI NAV data", type="primary", key="load_amfi_nav"):
        try:
            from alphafund.amfi import fetch_latest_nav
            with st.spinner("Downloading the official AMFI NAV feed…"):
                st.session_state["amfi_nav_frame"] = fetch_latest_nav()
                st.session_state["amfi_nav_loaded_at"] = pd.Timestamp.now().strftime("%d %b %Y, %H:%M")
            st.success(f"Loaded {len(st.session_state['amfi_nav_frame']):,} scheme NAV records.")
        except Exception as exc:
            st.error(f"AMFI NAV download failed: {exc}")
    if "amfi_nav_frame" in st.session_state:
        nav_frame = st.session_state["amfi_nav_frame"]
        st.caption(f"Feed fetched: {st.session_state.get('amfi_nav_loaded_at', 'Unknown')} · NAV date is shown per scheme.")
        nav_query = st.text_input("Search mutual-fund scheme", placeholder="e.g. Nifty 50 Index, Parag Parikh Flexi Cap")
        if nav_query.strip():
            from alphafund.amfi import search_nav_schemes
            matches = search_nav_schemes(nav_frame, nav_query, limit=100)
            if matches.empty:
                st.info("No matching scheme names. Try a shorter search term.")
            else:
                st.dataframe(matches[["scheme_code", "scheme_name", "nav", "nav_date", "isin_growth"]].rename(columns={
                    "scheme_code": "AMFI code", "scheme_name": "Scheme", "nav": "Latest NAV (₹)",
                    "nav_date": "NAV date", "isin_growth": "Growth ISIN"
                }), use_container_width=True, hide_index=True)
        else:
            st.info("Search by scheme name to view its latest NAV.")
    else:
        st.info("Load the AMFI feed to search current scheme NAVs.")
    st.link_button("AMFI official NAV downloads", "https://www.amfiindia.com/net-asset-value/nav-download")
    st.warning("Groww's documented portfolio API returns Demat stock holdings and CASH/FNO positions, not mutual-fund folios. To add mutual-fund units, import your CAS statement after converting it to the holdings template, or enter holdings manually. Scheme NAVs alone do not tell AlphaFund how many units you own.")

    st.divider()
    st.subheader("Equity research")
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
    st.caption("Long-only paper ledger with position-aware BUY/SELL checks, weighted-average cost basis and configurable estimated fees. No broker orders are sent.")
    with st.form("paper_trade"):
        col1, col2, col3, col4 = st.columns(4)
        trade_symbol = col1.text_input("Symbol", value=symbol_input.upper())
        trade_side = col2.selectbox("Side", ["BUY", "SELL"])
        quantity = col3.number_input("Quantity", min_value=1, max_value=100000, value=1, step=1)
        price = col4.number_input("Execution price (₹)", min_value=0.01, value=100.0, step=0.05)
        fee_bps = st.number_input("Estimated fees (basis points)", min_value=0.0, max_value=1000.0, value=0.0, step=1.0)
        submitted = st.form_submit_button("Record paper trade")
        if submitted:
            try:
                trade_result = record_paper_trade(
                    trade_symbol, trade_side, int(quantity), float(price),
                    paper_cash(settings.trading_allocation), settings.trading_allocation,
                    fee_bps=float(fee_bps))
                st.success(f"Recorded paper {trade_side}: notional ₹{trade_result['notional']:,.2f}; estimated fees ₹{trade_result['fees']:,.2f}.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    p1, p2 = st.columns(2)
    p1.metric("Paper cash available", f"₹{paper_cash(settings.trading_allocation):,.2f}")
    open_paper_positions = paper_positions()
    p2.metric("Open paper positions", str(len(open_paper_positions)))
    if open_paper_positions:
        st.markdown("**Paper positions · weighted-average cost**")
        st.dataframe(pd.DataFrame(open_paper_positions), use_container_width=True, hide_index=True)
    st.subheader("Paper ledger")
    trades = list_trades()
    if trades:
        st.dataframe(pd.DataFrame(trades, columns=["Timestamp (UTC)", "Symbol", "Side", "Quantity", "Price", "Notional", "Fees"]), use_container_width=True)
    else:
        st.info("No paper trades recorded yet.")

elif page == "Portfolio":
    st.divider()
    st.header("Your investments")
    st.caption("One consolidated view across Groww, mutual funds, PMS/AIF and manually added assets.")
    # One-click broker refresh. Groww's public portfolio API currently exposes Demat
    # holdings and CASH positions, not mutual-fund folios.
    gw_token = get_secret("GROWW_ACCESS_TOKEN")
    gw_key = get_secret("GROWW_API_KEY")
    gw_secret = get_secret("GROWW_API_SECRET")
    gw_connected = bool(gw_token or (gw_key and gw_secret))
    sync_col, status_col = st.columns([1, 2])
    with sync_col:
        if st.button("Sync Groww investments", type="primary", use_container_width=True, key="portfolio_sync_groww"):
            if not gw_connected:
                st.error("Connect Groww by adding its API credentials in Streamlit Secrets.")
            else:
                try:
                    sync_token = gw_token or generate_access_token(gw_key, gw_secret)
                    sync_holdings, sync_positions = GrowwReadOnlyClient(sync_token).get_portfolio()
                    st.session_state["groww_holdings"] = sync_holdings
                    st.session_state["groww_positions"] = sync_positions
                    sync_result = portfolio.sync_groww_holdings(sync_holdings, as_of_date=pd.Timestamp.now(tz="Asia/Kolkata").date())
                    st.session_state["groww_refreshed"] = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%d %b %Y, %I:%M:%S %p IST")
                    st.session_state["groww_loaded_for_chat"] = True
                    st.session_state.pop("groww_chat_error", None)
                    st.success(
                        f"Groww synced and saved: {len(sync_holdings)} broker holdings fetched; "
                        f"{sync_result['inserted']} new, {sync_result['updated']} updated, "
                        f"{sync_result['skipped']} skipped. {len(sync_positions)} CASH positions remain session-only."
                    )
                    st.rerun()
                except GrowwAPIError as exc:
                    st.error(f"Groww sync failed: {exc}")
    with status_col:
        if gw_connected:
            st.success("Groww API credentials configured · read-only connection")
            persisted_sync = portfolio.get_last_groww_sync()
            st.caption("Last saved sync: " + (pd.Timestamp(persisted_sync).strftime("%d %b %Y, %I:%M %p") if persisted_sync else "Never"))
        else:
            st.warning("Groww is not connected. Add GROWW_ACCESS_TOKEN or GROWW_API_KEY + GROWW_API_SECRET in Streamlit Secrets.")
    groww_mf_count = sum(1 for row in portfolio.list_holdings() if str(row.get("provider", "")).lower() == "groww" and str(row.get("asset_type", "")).lower() == "mutual_fund")
    st.info(f"Mutual funds saved from Groww/CAS: {groww_mf_count}. Groww's documented API does not expose mutual-fund folios, so these cannot be synced by the broker API yet. CAS/manual import remains a fallback; AlphaFund will not pretend those units were fetched live.")
    manual_tab, csv_tab, groww_mf_tab, holdings_tab, transactions_tab, valuations_tab, performance_tab = st.tabs(["Add manually", "Import fallback", "Groww MF / CAS", "Holdings overview", "Transactions", "Valuations", "Performance"])
    
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
        st.caption("Upload a CSV or XLSX workbook using the holdings template. The app validates the full file before importing.")
        st.download_button("Download holdings CSV template",
            data="account_name,account_type,provider,asset_type,instrument_name,identifier,exchange,currency,quantity,average_cost,as_of_date\nMy Broker Account,broker,manual,equity,Example Company,EXAMPLE,NSE,INR,10,125.50,2026-11-03\n",
            file_name="alphafund_holdings_template.csv", mime="text/csv")
        upload = st.file_uploader("Choose holdings CSV", type=["csv", "xlsx", "xlsm"], key="holdings_csv_upload")
        if upload is not None:
            try:
                preview, checksum = validate_holdings_csv(upload.getvalue(), upload.name)
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
    
    with groww_mf_tab:
        st.markdown("#### Mutual-fund holdings from CAS")
        st.caption("This is a fallback import—not a live Groww API sync. Groww's documented Trading API does not expose mutual-fund folios. Use a CAMS/KFintech/MFCentral CAS export or a Groww-provided statement, convert it to the AlphaFund template, and import once. Holdings then remain in the consolidated portfolio and AI Chat.")
        groww_mf_template = (
            "account_name,account_type,provider,asset_type,instrument_name,identifier,exchange,currency,quantity,average_cost,as_of_date\n"
            "Groww Mutual Funds,mutual_fund,groww,mutual_fund,Example Flexi Cap Fund,INF000000000,,INR,125.50,82.40,2026-11-03\n"
        )
        st.download_button("Download Groww mutual-fund CSV template", data=groww_mf_template,
            file_name="alphafund_groww_mutual_funds_template.csv", mime="text/csv")
        groww_mf_upload = st.file_uploader("Upload Groww mutual-fund CSV", type=["csv", "xlsx", "xlsm"], key="groww_mf_csv_upload")
        if groww_mf_upload is not None:
            try:
                groww_mf_preview, groww_mf_checksum = validate_holdings_csv(groww_mf_upload.getvalue(), groww_mf_upload.name)
                groww_mf_preview["account_name"] = "Groww Mutual Funds"
                groww_mf_preview["account_type"] = "mutual_fund"
                groww_mf_preview["provider"] = "groww"
                groww_mf_preview["asset_type"] = "mutual_fund"
                st.success(f"Validated {len(groww_mf_preview)} Groww mutual-fund holdings. Review before importing.")
                st.dataframe(groww_mf_preview, use_container_width=True, hide_index=True)
                if st.button("Import Groww mutual funds", type="primary", key="import_groww_mf"):
                    result = portfolio.import_holdings(groww_mf_preview.to_dict(orient="records"), groww_mf_upload.name, groww_mf_checksum)
                    if result["duplicate_file"]:
                        st.warning("This exact Groww file was already imported. No rows were added.")
                    else:
                        st.success(f"Groww mutual funds added: {result['inserted']}; duplicate snapshots skipped: {result['skipped']}.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Groww mutual-fund CSV validation failed: {exc}")
        st.info("After a one-time import, fund units are saved and included in Holdings, portfolio analytics and AI Chat. Refresh AMFI NAV data in Discover and add matching NAV observations to calculate indicative value. A future official CAS integration can replace this fallback.")

    with holdings_tab:
        current_holdings = portfolio.list_holdings()
        if gw_connected and not portfolio.get_last_groww_sync():
            st.info("Groww is connected. Select Sync Groww investments above to save your first Demat snapshot.")
        if current_holdings:
            from alphafund.analytics import holdings_frame, portfolio_summary, allocation_by, portfolio_valuation_history
            saved_frame = holdings_frame(current_holdings)
            # Historical snapshots remain in the register, but current metrics use
            # only the latest row per account/instrument to prevent double-counting.
            current_frame = saved_frame.copy()
            current_frame["as_of_date"] = pd.to_datetime(current_frame["as_of_date"], errors="coerce")
            current_frame = current_frame.sort_values("as_of_date").drop_duplicates(
                ["account", "identifier"], keep="last")
            current_frame = current_frame[current_frame["quantity"] > 0].copy()
            summary = portfolio_summary(current_frame)
            st.markdown("#### Consolidated portfolio overview")
            from alphafund.analyst import portfolio_review, ai_interpretation, review_fingerprint
            saved_valuations_for_review = portfolio.list_valuations()
            saved_transactions_for_review = portfolio.list_transactions()
            review = portfolio_review(current_frame.to_dict("records"), saved_valuations_for_review,
                                      saved_transactions_for_review)
            fingerprint = review_fingerprint(current_frame.to_dict("records"), saved_valuations_for_review,
                                             saved_transactions_for_review)
            if st.session_state.get("portfolio_review_fingerprint") != fingerprint:
                with st.spinner("AlphaFund is reviewing your portfolio…"):
                    ai_provider = (get_secret("ALPHAFUND_AI_PROVIDER") or "huggingface").lower()
                    st.session_state["portfolio_review_text"] = ai_interpretation(
                        review, api_key=get_secret("OPENAI_API_KEY"),
                        model=get_secret("OPENAI_MODEL") or settings.openai_model,
                        provider=ai_provider,
                        ollama_model=get_secret("OLLAMA_MODEL") or "qwen2.5:7b",
                        ollama_base_url=get_secret("OLLAMA_BASE_URL") or "http://localhost:11434",
                        allow_cloud_fallback=get_secret("OPENAI_FALLBACK_ENABLED").lower() == "true",
                        huggingface_token=get_secret("HF_TOKEN"),
                        huggingface_model=get_secret("HUGGINGFACE_MODEL") or "openai/gpt-oss-120b:cheapest",
                        cloud_data_sharing=get_secret("ALPHAFUND_CLOUD_DATA_SHARING").lower() == "true",
                    )
                    st.session_state["portfolio_ai_provider_used"] = ai_provider
                    st.session_state["portfolio_review_fingerprint"] = fingerprint
            st.markdown("#### AlphaFund AI analyst")
            st.markdown(st.session_state.get("portfolio_review_text", "Portfolio review is being prepared."))
            st.caption("Analysis refreshes automatically when holdings, valuations or transactions change. Financial metrics are deterministic. Provider: " + (get_secret("ALPHAFUND_AI_PROVIDER") or "huggingface").upper() + ". Cloud portfolio-data sharing is opt-in via ALPHAFUND_CLOUD_DATA_SHARING.")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Holding records", f"{summary['holding_count']:,}")
            k2.metric("Known recorded cost basis", f"₹{summary['cost_basis']:,.2f}")
            k3.metric("Cost data coverage", f"{summary['cost_coverage_pct']:.1f}%")
            k4.metric("Missing average cost", f"{summary['missing_cost_count']:,}")
            st.caption("Cost basis includes only records with a recorded average cost. Multiple dated snapshots may exist; this register is not a deduplicated current-position valuation.")
            st.markdown("#### Portfolio analytics")
            chart_left, chart_right = st.columns(2)
            asset_alloc = allocation_by(current_frame, "asset_type")
            with chart_left:
                st.markdown("**Asset allocation · recorded cost basis**")
                if not asset_alloc.empty:
                    import plotly.express as px
                    fig = px.pie(asset_alloc, names="asset_type", values="cost_basis", hole=0.62)
                    fig.update_layout(margin=dict(t=12,b=12,l=8,r=8), legend_title_text="Asset class")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No recorded cost basis for allocation.")
            with chart_right:
                st.markdown("**Largest positions · recorded cost basis**")
                largest = current_frame.dropna(subset=["cost_basis"]).nlargest(10, "cost_basis")
                if not largest.empty:
                    import plotly.express as px
                    fig = px.bar(largest.sort_values("cost_basis"), x="cost_basis", y="instrument",
                                 orientation="h", color="asset_type", labels={
                                     "cost_basis":"Cost basis (₹)", "instrument":"Investment",
                                     "asset_type":"Asset class"})
                    fig.update_layout(margin=dict(t=12,b=12,l=8,r=8), yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No position cost data available.")
            valuation_history = portfolio_valuation_history(portfolio.list_valuations())
            if not valuation_history.empty:
                st.markdown("**Reported portfolio value over time**")
                import plotly.express as px
                history_chart = valuation_history.copy()
                history_chart["valuation_date"] = pd.to_datetime(history_chart["valuation_date"])
                fig = px.area(history_chart, x="valuation_date", y="portfolio_value",
                              labels={"valuation_date":"Date","portfolio_value":"Portfolio value (₹)"})
                fig.update_layout(margin=dict(t=12,b=12,l=8,r=8))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Performance chart will appear when dated total market-value observations are imported. Cost basis is not a substitute for performance.")
            st.markdown("**Saved holdings and data quality**")
            display_holdings = saved_frame.copy()
            display_holdings = display_holdings.rename(columns={"channel": "Channel", "source_file": "Source file"})
            st.dataframe(display_holdings, use_container_width=True, hide_index=True)
            st.caption("This register retains dated snapshots, including closed positions. Current summary and allocation charts use only the latest snapshot per account/security. Performance, unrealised P&L, sector exposure and risk metrics require dated market valuations and/or transaction history.")
        else:
            st.info("No holdings saved yet. Start with Sync Groww investments, then add non-Groww assets manually or use the one-time CAS/file fallback.")
    
    
    with transactions_tab:
        st.caption("Import broker transaction history. BUY/SIP/contribution amounts are treated as investor outflows; SELL/dividend/coupon/distribution amounts as inflows for XIRR.")
        st.download_button("Download transactions CSV template",
            data="account_name,account_type,provider,asset_type,instrument_name,identifier,transaction_type,transaction_date,quantity,price,amount,currency,external_id,notes\nGroww Demat,broker,groww,equity,Reliance,RELIANCE,BUY,2026-10-01,2,1200,2400,INR,TXN-001,Example only\n",
            file_name="alphafund_transactions_template.csv", mime="text/csv")
        from alphafund.imports import validate_transactions_csv
        tx_upload = st.file_uploader("Upload transactions CSV or XLSX workbook", type=["csv", "xlsx", "xlsm"], key="transactions_csv_upload")
        if tx_upload is not None:
            try:
                tx_preview, tx_checksum = validate_transactions_csv(tx_upload.getvalue(), tx_upload.name)
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
        val_upload = st.file_uploader("Upload valuations CSV or XLSX workbook", type=["csv", "xlsx", "xlsm"], key="valuations_csv_upload")
        if val_upload is not None:
            try:
                val_preview, val_checksum = validate_valuations_csv(val_upload.getvalue(), val_upload.name)
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
                xirr_value = investor_xirr(
                    saved_transactions,
                    terminal_value=total_market_value if complete_value_coverage else None,
                    terminal_date=pd.Timestamp.now().date() if complete_value_coverage else None,
                )
                st.metric("Investor XIRR", f"{xirr_value * 100:.2f}%" if xirr_value is not None and complete_value_coverage else "Not enough complete cash-flow data")
                st.caption("XIRR uses imported dated transaction amounts plus the latest complete portfolio value as terminal value. Review transaction signs/types and ensure transaction history is complete before relying on this metric.")
            else:
                st.info("Import transaction history to calculate investor-level XIRR.")


elif page == "AI Chat":
    # Portfolio-aware AI assistant
    st.divider()
    st.markdown('<div class="af-eyebrow">AlphaFund intelligence</div>', unsafe_allow_html=True)
    st.header("Ask AlphaFund")
    st.caption("Ask questions about your holdings, allocation, transactions, NAVs, valuations and investment research. Managed open-weight AI runs through Hugging Face when configured. Portfolio data is not sent to cloud AI unless ALPHAFUND_CLOUD_DATA_SHARING=true.")
    from alphafund.portfolio_chat import build_portfolio_context, answer_portfolio_question
    # Load Groww read-only data on first visit to Chat, so chat does not depend on a prior Home-page click.
    groww_credentials = (
        get_secret("GROWW_ACCESS_TOKEN"),
        get_secret("GROWW_API_KEY"),
        get_secret("GROWW_API_SECRET"),
    )
    if not st.session_state.get("groww_loaded_for_chat") and any(groww_credentials):
        try:
            token = groww_credentials[0] or generate_access_token(groww_credentials[1], groww_credentials[2])
            live_holdings, live_positions = GrowwReadOnlyClient(token).get_portfolio()
            st.session_state["groww_holdings"] = live_holdings
            st.session_state["groww_positions"] = live_positions
            st.session_state["groww_refreshed"] = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%d %b %Y, %I:%M:%S %p IST")
            st.session_state["groww_loaded_for_chat"] = True
            st.session_state.pop("groww_chat_error", None)
        except GrowwAPIError as exc:
            st.session_state["groww_chat_error"] = str(exc)
            st.session_state["groww_loaded_for_chat"] = True
    if st.session_state.get("groww_chat_error"):
        st.warning("Groww data could not be loaded for this chat session: " + st.session_state["groww_chat_error"])
    elif not any(groww_credentials):
        st.info("Connect Groww in Streamlit Secrets to load live holdings here. The chatbot currently sees saved AlphaFund holdings only.")
    chat_holdings = portfolio.list_holdings()
    chat_valuations = portfolio.list_valuations()
    chat_transactions = portfolio.list_transactions()
    chat_context = build_portfolio_context(
        holdings=chat_holdings,
        valuations=chat_valuations,
        transactions=chat_transactions,
        # Groww Demat holdings are persisted in saved_holdings during sync;
        # do not also pass the live copy or the chatbot would double-count them.
        groww_holdings=[],
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
            api_key=get_secret("HF_TOKEN") if (get_secret("ALPHAFUND_AI_PROVIDER") or "huggingface").lower() == "huggingface" else get_secret("OPENAI_API_KEY"),
            model=(get_secret("HUGGINGFACE_MODEL") or "openai/gpt-oss-120b:cheapest") if (get_secret("ALPHAFUND_AI_PROVIDER") or "huggingface").lower() == "huggingface" else (get_secret("OPENAI_MODEL") or settings.openai_model),
            provider=(get_secret("ALPHAFUND_AI_PROVIDER") or "huggingface").lower(),
            cloud_data_sharing=get_secret("ALPHAFUND_CLOUD_DATA_SHARING").lower() == "true",
            ollama_model=get_secret("OLLAMA_MODEL") or "qwen2.5:7b",
            ollama_base_url=get_secret("OLLAMA_BASE_URL") or "http://localhost:11434",
            history=st.session_state["alphafund_chat"][:-1],
        )
        st.session_state["alphafund_chat"].append({"role": "assistant", "content": chat_reply})
        st.rerun()
    if st.button("Clear chat history", key="clear_alphafund_chat"):
        st.session_state["alphafund_chat"] = []
        st.rerun()
    st.caption(f"Context currently loaded: {len(chat_holdings)} saved holdings · {len(st.session_state.get('groww_holdings', []))} Groww holdings · {len(chat_transactions)} transactions · {len(chat_valuations)} valuations. Chat history is held in this Streamlit session.")

elif page == "Company Intel":
    from alphafund.company_intel import fetch_fundamentals, fetch_company_news, score_company_fundamentals
    from alphafund.market_research import MARKETS

    st.subheader("Company fundamentals & news")
    st.caption("Company profile, valuation, financial statements and recent headlines for NSE, BSE and US-listed equities.")
    intel_market = st.selectbox("Market", ["NSE", "BSE", "US"], key="intel_market")
    intel_default = "RELIANCE" if intel_market == "NSE" else ("500325" if intel_market == "BSE" else "AAPL")
    intel_symbol = st.text_input("Ticker / scrip code", value=intel_default, key="intel_symbol")
    currency = MARKETS[intel_market]["currency"]
    intel_col1, intel_col2 = st.columns(2)
    with intel_col1:
        if st.button("Load fundamentals", type="primary", key="load_company_fundamentals"):
            try:
                with st.spinner("Retrieving company profile and financial statements…"):
                    st.session_state["company_fundamentals"] = fetch_fundamentals(intel_symbol, intel_market)
                    st.session_state["company_fundamentals_key"] = (intel_market, intel_symbol.strip().upper())
            except Exception as exc:
                st.error(f"Fundamental data unavailable: {exc}")
    with intel_col2:
        if st.button("Load company news", key="load_company_news"):
            try:
                with st.spinner("Retrieving recent company headlines…"):
                    st.session_state["company_news"] = fetch_company_news(intel_symbol, intel_market, limit=10)
                    st.session_state["company_news_key"] = (intel_market, intel_symbol.strip().upper())
            except Exception as exc:
                st.error(f"Company news unavailable: {exc}")

    requested_key = (intel_market, intel_symbol.strip().upper())
    fundamentals = st.session_state.get("company_fundamentals")
    if fundamentals and st.session_state.get("company_fundamentals_key") == requested_key:
        profile = fundamentals["profile"]
        st.markdown(f"### {profile.get('Company', profile.get('Ticker', intel_symbol))}")
        st.caption(f"Source: {fundamentals['source']} · Retrieved: {fundamentals['retrieved_at_utc']} · Statement coverage: {fundamentals['statement_coverage']}")
        st.markdown("#### Valuation and quality metrics")
        metric_keys = [
            "Market capitalisation", "Trailing P/E", "Forward P/E", "Price / book",
            "Price / sales", "PEG ratio", "Return on equity", "Return on assets",
            "Profit margin", "Operating margin", "Debt / equity", "Current ratio",
            "Revenue growth", "Earnings growth", "Free cash flow", "Dividend yield",
        ]
        available = [(key, profile[key]) for key in metric_keys if profile.get(key) is not None]
        if available:
            cols = st.columns(4)
            for index, (label, value) in enumerate(available):
                if label in ("Market capitalisation", "Free cash flow"):
                    display = f"{currency} {float(value):,.0f}"
                elif label in ("Return on equity", "Return on assets", "Profit margin", "Operating margin", "Revenue growth", "Earnings growth", "Dividend yield"):
                    display = f"{float(value) * 100:.2f}%"
                else:
                    display = f"{float(value):,.2f}"
                cols[index % 4].metric(label, display)
        else:
            st.info("The provider did not return valuation or quality ratios for this security.")
        if fundamentals["warnings"]:
            for warning in fundamentals["warnings"]:
                st.warning(warning)
        screening = score_company_fundamentals(profile)
        st.markdown("#### Fundamental screening score")
        if screening["composite_score"] is not None:
            st.metric("Heuristic screening score", f'{screening["composite_score"]:.1f}/100')
            st.caption(f'Method: {screening["methodology"]} · Coverage: {screening["coverage"]}')
            score_frame = pd.DataFrame([
                {"Pillar": pillar, "Score / 100": item["score"], "Inputs": ", ".join(item["inputs"])}
                for pillar, item in screening["pillars"].items()
            ])
            st.dataframe(score_frame, use_container_width=True, hide_index=True)
        else:
            st.info("Not enough reported ratios to calculate a screening score.")
        for flag in screening["flags"]:
            st.warning(flag)
        for statement_name, statement_frame in fundamentals["statements"].items():
            with st.expander(statement_name, expanded=(statement_name == "Income statement")):
                if statement_frame.empty:
                    st.info("No statement data returned for this security.")
                else:
                    st.dataframe(statement_frame, use_container_width=True, hide_index=True)
        st.caption("Metrics are provider-reported and may be stale, unavailable or calculated differently across markets. Review source filings before relying on them.")

    news = st.session_state.get("company_news")
    if st.session_state.get("company_news_key") == requested_key:
        st.markdown("#### Recent company headlines")
        if not news:
            st.info("No recent headlines were returned.")
        else:
            for item in news:
                st.markdown(f"**{item['title']}**")
                st.caption(f"{item['publisher']} · {item['published']}")
                if item["summary"]:
                    st.write(item["summary"])
                if item["link"]:
                    st.markdown(f"[Open original article]({item['link']})")
                st.divider()
        st.caption("Headlines are presented as supplied by the publisher index. AlphaFund does not infer sentiment or treat headlines as verified facts.")

    if fundamentals and st.session_state.get("company_fundamentals_key") == requested_key:
        from alphafund.reports import build_research_report
        company_screening = score_company_fundamentals(fundamentals["profile"])
        company_news = news if st.session_state.get("company_news_key") == requested_key else None
        company_report = build_research_report(
            "AlphaFund Company Research Report", intel_market, fundamentals["profile"].get("Ticker", intel_symbol),
            fundamentals=fundamentals, screening=company_screening, news=company_news)
        st.download_button("Download company research report (Markdown)", company_report,
                           file_name=f"alphafund_{intel_symbol.strip().lower()}_research.md",
                           mime="text/markdown")

elif page == "Risk & Reports":
    from alphafund.risk import (
        parse_weighted_symbols, fetch_price_matrix, calculate_portfolio_risk,
        evaluate_price_alert,
    )
    from alphafund.reports import build_research_report
    from alphafund.market_research import fetch_market_history

    st.subheader("Portfolio risk, price thresholds & reports")
    st.caption("Historical risk analytics from adjusted daily closes. Use explicit weights; this page does not infer portfolio weights from incomplete or mixed-asset records.")
    risk_market = st.selectbox("Risk market", ["NSE", "BSE", "US"], key="risk_market")
    risk_default = "RELIANCE:50, TCS:30, INFY:20" if risk_market == "NSE" else ("500325:60, 532540:40" if risk_market == "BSE" else "AAPL:50, MSFT:30, NVDA:20")
    risk_symbols_text = st.text_area("Ticker weights (SYMBOL:WEIGHT)", value=risk_default, key="risk_symbols_text",
                                     help="Weights are normalized automatically; they do not need to add up to 100.")
    risk_period = st.selectbox("Risk lookback", ["1y", "2y", "5y"], index=1, key="risk_period")
    risk_confidence = st.slider("Historical VaR confidence", 0.90, 0.99, 0.95, 0.01, key="risk_confidence")
    if st.button("Calculate portfolio risk", type="primary", key="calculate_portfolio_risk"):
        try:
            with st.spinner("Fetching daily adjusted closes and calculating risk…"):
                parsed_weights = parse_weighted_symbols(risk_symbols_text)
                price_matrix = fetch_price_matrix(parsed_weights, risk_market, risk_period)
                risk_result = calculate_portfolio_risk(price_matrix, parsed_weights, risk_confidence)
                risk_result["market"] = risk_market
                risk_result["symbols"] = list(parsed_weights)
                risk_result["request_signature"] = (risk_market, risk_symbols_text, risk_period, risk_confidence)
                st.session_state["risk_report_result"] = risk_result
                st.session_state["risk_report_weights"] = parsed_weights
        except Exception as exc:
            st.error(f"Risk calculation failed: {exc}")

    risk_result = st.session_state.get("risk_report_result")
    if risk_result and risk_result.get("request_signature") == (risk_market, risk_symbols_text, risk_period, risk_confidence):
        st.caption(f'Common daily return window: {risk_result["start_date"]} to {risk_result["end_date"]} · {risk_result["observations"]} observations')
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Annualised volatility", f'{risk_result["annualised_volatility_pct"]:.2f}%')
        r2.metric(f'Historical VaR ({risk_result["confidence"]:.0%})', f'{risk_result["historical_var_pct"]:.2f}%')
        r3.metric("Historical CVaR", f'{risk_result["historical_cvar_pct"]:.2f}%')
        r4.metric("Maximum drawdown", f'{risk_result["max_drawdown_pct"]:.2f}%')
        st.markdown("#### Portfolio weights and risk contribution")
        contribution_rows = []
        for symbol, weight in risk_result["weights_pct"].items():
            contribution_rows.append({
                "Symbol": symbol,
                "Weight (%)": round(weight, 2),
                "Annualised volatility (%)": round(risk_result["asset_volatility_pct"].get(symbol, 0), 2),
                "Risk contribution (%)": round(risk_result["risk_contribution_pct"].get(symbol, 0), 2),
            })
        st.dataframe(pd.DataFrame(contribution_rows), use_container_width=True, hide_index=True)
        st.markdown("#### Historical portfolio growth")
        st.line_chart(risk_result["equity_curve"], use_container_width=True)
        st.markdown("#### Return correlation")
        st.dataframe(risk_result["correlation"].round(3), use_container_width=True)
        if risk_result.get("price_failures"):
            st.warning("Some symbols were excluded because price history was unavailable: " + "; ".join(
                f'{key}: {value}' for key, value in risk_result["price_failures"].items()))
        report_text = build_research_report(
            "AlphaFund Portfolio Risk Report", risk_market,
            ", ".join(risk_result["symbols"]), risk=risk_result)
        st.download_button("Download risk report (Markdown)", report_text,
                           file_name="alphafund_portfolio_risk_report.md", mime="text/markdown")
        st.download_button("Download risk contributions (CSV)",
                           pd.DataFrame(contribution_rows).to_csv(index=False),
                           file_name="alphafund_risk_contributions.csv", mime="text/csv")
        st.caption("VaR/CVaR are historical sample estimates, not maximum-loss limits. The weighted-return calculation assumes periodic rebalancing to the entered weights and uses only common complete observations. No taxes, fees, slippage, FX conversion or dividend adjustments are added.")

    st.divider()
    st.markdown("#### Price threshold checks")
    st.caption("Manual checks only: AlphaFund fetches recent daily closes when you press Evaluate. It does not run a background scheduler or send push notifications.")
    alert_market = st.selectbox("Alert market", ["NSE", "BSE", "US"], key="alert_market")
    alert_rules = st.text_area("Threshold rules (SYMBOL:above|below:PRICE)",
                               value="RELIANCE:above:1500, TCS:below:3000" if alert_market == "NSE" else ("500325:above:1000" if alert_market == "BSE" else "AAPL:above:250"),
                               key="alert_rules")
    if st.button("Evaluate price thresholds", key="evaluate_price_thresholds"):
        alert_rows = []
        try:
            rules = [x.strip() for x in alert_rules.replace("\n", ",").split(",") if x.strip()]
            if not rules:
                raise ValueError("Enter at least one threshold rule.")
            if len(rules) > 20:
                raise ValueError("Limit each check to 20 rules.")
            for rule in rules:
                parts = [x.strip() for x in rule.split(":")]
                if len(parts) != 3:
                    raise ValueError(f"Invalid rule '{rule}'. Use SYMBOL:above|below:PRICE.")
                symbol, direction, target_text = parts
                target = float(target_text)
                _, history = fetch_market_history(symbol, alert_market, period="6mo")
                closes = history["Close"].dropna()
                if len(closes) < 2:
                    raise ValueError(f"Not enough recent closes for {symbol}.")
                evaluated = evaluate_price_alert(float(closes.iloc[-1]), float(closes.iloc[-2]), target, direction)
                alert_rows.append({
                    "Symbol": symbol.upper(), "Direction": direction.lower(),
                    "Target": target, "Last close": evaluated["last_price"],
                    "Previous close": evaluated["previous_price"],
                    "Crossed this session": evaluated["triggered"],
                    "Threshold currently met": evaluated["currently_met"],
                    "Data date": str(closes.index[-1].date()),
                })
            st.session_state["price_threshold_results"] = alert_rows
            st.session_state["price_threshold_market"] = alert_market
        except Exception as exc:
            st.error(f"Threshold evaluation failed: {exc}")
    if st.session_state.get("price_threshold_market") == alert_market:
        alert_frame = pd.DataFrame(st.session_state.get("price_threshold_results", []))
        if not alert_frame.empty:
            st.dataframe(alert_frame, use_container_width=True, hide_index=True)
            crossed = alert_frame[alert_frame["Crossed this session"]]
            if not crossed.empty:
                st.success(f'{len(crossed)} threshold crossing(s) detected in the latest available daily bar.')
            else:
                st.info("No new threshold crossings detected in the latest available daily bar.")
    st.warning("This feature is a manual daily-bar check, not continuous monitoring. For automatic notifications, AlphaFund needs an always-on scheduler and a configured notification channel. Yahoo Finance data can be delayed or unavailable.")

elif page == "Research":
    from alphafund.market_research import (
        MARKETS, fetch_market_history, add_research_indicators,
        analyse_history, research_backtest, scan_symbols,
    )
    st.subheader("Multi-market equity research")
    st.caption("Technical research for NSE, BSE and US-listed equities. Prices are indicative Yahoo Finance data; validate with your broker before acting.")
    market_label = st.selectbox("Market", ["NSE", "BSE", "US"], index=0)
    currency = MARKETS[market_label]["currency"]
    symbol_input = st.text_input("Ticker symbol", value="RELIANCE" if market_label == "NSE" else ("500325" if market_label == "BSE" else "AAPL"),
                                 help="Enter NSE symbol, BSE scrip code, or US ticker. Do not include exchange suffix unless it matches the selected market.")
    period = st.selectbox("History window", ["6mo", "1y", "2y", "5y"], index=2)
    if st.button("Analyse security", type="primary", key="multi_market_analyse"):
        try:
            with st.spinner("Loading market history and calculating indicators…"):
                ticker, history = fetch_market_history(symbol_input, market_label, period=period)
                enriched = add_research_indicators(history)
                metrics = analyse_history(history)
                st.session_state["research_result"] = {
                    "ticker": ticker, "market": market_label, "currency": currency,
                    "history": enriched, "metrics": metrics,
                }
        except Exception as exc:
            st.error(f"Research could not be completed: {exc}")
    result = st.session_state.get("research_result")
    if result and result["market"] == market_label:
        m = result["metrics"]
        st.caption(f'{result["ticker"]} · Data through {m["as_of"]} · {m["observations"]:,} observations')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Last close", f'{currency} {m["close"]:,.2f}')
        c2.metric("Trend", m["trend"])
        c3.metric("RSI (14)", f'{m["rsi"]:.1f}')
        c4.metric("Technical score", f'{m["technical_score"]}/5')
        st.caption("The technical score is a rule-based indicator summary, not a probability, target price or buy/sell recommendation.")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("1-month return", f'{m["return_1m_pct"]:.2f}%' if m["return_1m_pct"] is not None else "N/A")
        c6.metric("3-month return", f'{m["return_3m_pct"]:.2f}%' if m["return_3m_pct"] is not None else "N/A")
        c7.metric("Annualised volatility", f'{m["annualised_volatility_pct"]:.1f}%' if m["annualised_volatility_pct"] is not None else "N/A")
        c8.metric("Historical max drawdown", f'{m["max_drawdown_pct"]:.1f}%')
        hist = result["history"]
        st.markdown("#### Price and trend")
        chart_cols = [x for x in ["Close", "SMA_20", "SMA_50", "SMA_200"] if x in hist.columns and hist[x].notna().any()]
        st.line_chart(hist[chart_cols].tail(260), use_container_width=True)
        t1, t2, t3 = st.tabs(["Momentum", "Backtest", "Risk"])
        with t1:
            st.line_chart(hist[["RSI_14"]].tail(180), use_container_width=True)
            st.line_chart(hist[["MACD", "MACD_SIGNAL"]].tail(180), use_container_width=True)
            st.write({"MACD": round(m["macd"], 3), "MACD signal": round(m["macd_signal"], 3),
                      "Momentum": m["momentum"], "ATR (14)": round(m["atr14"], 3) if m["atr14"] is not None else None})
        with t2:
            fee_bps = st.slider("Estimated transaction cost (basis points per position change)", 0, 50, 10, 1)
            bt = research_backtest(hist, fee_bps=fee_bps)
            b1, b2, b3 = st.columns(3)
            b1.metric("Strategy return", f'{bt["strategy_return_pct"]:.2f}%')
            b2.metric("Buy & hold", f'{bt["buy_hold_return_pct"]:.2f}%')
            b3.metric("Strategy max drawdown", f'{bt["max_drawdown_pct"]:.2f}%')
            st.line_chart(bt["equity_curve"], use_container_width=True)
            st.caption(f'20/50-day long-only SMA regime · {bt["trade_entries"]} entries · {bt["trade_exits"]} exits · {fee_bps} bps estimated cost per position change. Historical simulation only; excludes taxes, market impact and dividends.')
        with t3:
            st.write({
                "SMA 20": round(m["sma20"], 2), "SMA 50": round(m["sma50"], 2),
                "SMA 200": round(m["sma200"], 2) if m["sma200"] is not None else "Not enough data",
                "ATR 14": round(m["atr14"], 2) if m["atr14"] is not None else "N/A",
                "Annualised volatility": m["annualised_volatility_pct"],
                "Maximum historical drawdown": m["max_drawdown_pct"],
            })
            st.caption("Volatility and drawdown are calculated from the selected historical window. They are not forecasts.")
        from alphafund.reports import build_research_report
        technical_report = build_research_report(
            "AlphaFund Technical Research Report", result["market"], result["ticker"],
            technical=m)
        st.download_button("Download technical research report (Markdown)", technical_report,
                           file_name=f"alphafund_{result['ticker'].lower()}_technical.md",
                           mime="text/markdown")
    st.divider()
    st.markdown("#### Multi-stock scanner")
    st.caption("Scan a small watchlist (maximum 30 tickers) for comparable technical metrics.")
    scan_market = st.selectbox("Scanner market", ["NSE", "BSE", "US"], key="scan_market")
    scan_text = st.text_area("Symbols separated by commas or new lines", value="RELIANCE, TCS, INFY" if scan_market == "NSE" else ("500325, 532540" if scan_market == "BSE" else "AAPL, MSFT, NVDA"))
    if st.button("Run watchlist scan", key="run_multi_market_scan"):
        symbols = [x.strip() for x in re.split(r"[,\s]+", scan_text) if x.strip()]
        if len(symbols) > 30:
            st.error("Please limit each scan to 30 symbols.")
        elif not symbols:
            st.error("Enter at least one ticker.")
        else:
            with st.spinner(f"Scanning {len(symbols)} {scan_market} symbols…"):
                st.session_state["market_scan_results"] = scan_symbols(symbols, scan_market)
                st.session_state["market_scan_market"] = scan_market
    if st.session_state.get("market_scan_results") is not None and st.session_state.get("market_scan_market") == scan_market:
        st.dataframe(st.session_state["market_scan_results"], use_container_width=True, hide_index=True)
        st.download_button("Download scanner results (CSV)",
                           st.session_state["market_scan_results"].to_csv(index=False),
                           file_name=f"alphafund_{scan_market.lower()}_watchlist_scan.csv",
                           mime="text/csv")
    st.warning("Data provider limitations: Yahoo Finance data may be delayed, incomplete or rate-limited. NSE/BSE ticker coverage must be checked symbol by symbol. Fundamental ratios, exchange filings, live quotes and news sentiment are not part of this first integration. No orders are sent.");


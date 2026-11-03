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
settings.validate()
initialize_ledger()

st.title("AlphaFund AI V1")
st.caption("Indian equities research • Paper trading only • Live orders disabled")
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

st.divider()
st.header("Consolidated portfolio")
from datetime import date
from alphafund.storage import PortfolioStore
from alphafund.imports import validate_holdings_csv

@st.cache_resource
def portfolio_store():
    store = PortfolioStore()
    store.initialize()
    return store

portfolio = portfolio_store()
manual_tab, csv_tab, holdings_tab = st.tabs(["Add holding", "Import CSV", "Portfolio holdings"])

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
        st.dataframe(pd.DataFrame(current_holdings), use_container_width=True, hide_index=True)
    else:
        st.info("No consolidated holdings yet. Add a holding manually or import the CSV template.")

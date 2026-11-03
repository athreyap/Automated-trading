import streamlit as st
import pandas as pd
import hmac
import os
from alphafund.config import settings
from alphafund.market_data import fetch_history, normalize_symbol
from alphafund.strategy import add_indicators, latest_signal, backtest
from alphafund.paper_broker import initialize_ledger, list_trades, record_paper_trade, paper_cash
from alphafund.ai_explainer import explain_signal
from alphafund.groww_client import GrowwReadOnlyClient, GrowwAPIError


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


require_app_login()

st.set_page_config(page_title="AlphaFund AI V1", page_icon="📈", layout="wide")
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
groww_token = get_secret("GROWW_ACCESS_TOKEN")
if not groww_token:
    st.info("Add GROWW_ACCESS_TOKEN to Streamlit app secrets. Groww access tokens expire daily at 6:00 AM IST.")
else:
    if st.button("Refresh Groww portfolio"):
        try:
            holdings, positions = GrowwReadOnlyClient(groww_token).get_portfolio()
            st.session_state["groww_holdings"] = holdings
            st.session_state["groww_positions"] = positions
            st.session_state["groww_refreshed"] = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%d %b %Y, %I:%M:%S %p IST")
        except GrowwAPIError as exc:
            st.error(str(exc))
    if "groww_holdings" in st.session_state:
        st.caption(f"Last refreshed: {st.session_state.get('groww_refreshed', 'Unknown')}")
        holdings = st.session_state["groww_holdings"]
        positions = st.session_state["groww_positions"]
        if holdings:
            hdf = pd.DataFrame(holdings)
            hdf["invested_value"] = pd.to_numeric(hdf["quantity"], errors="coerce").fillna(0) * pd.to_numeric(hdf["average_price"], errors="coerce").fillna(0)
            st.metric("Holdings cost value", f"₹{hdf['invested_value'].sum():,.2f}")
            st.dataframe(hdf[[c for c in ["trading_symbol", "quantity", "average_price", "invested_value", "isin"] if c in hdf.columns]], use_container_width=True, hide_index=True)
            st.caption("Cost value = quantity × average purchase price. This is not current market value or unrealised P&L.")
        else: st.info("Groww returned no equity holdings.")
        if positions:
            st.markdown("**Positions (CASH segment)**")
            pdf = pd.DataFrame(positions)
            cols = [c for c in ["trading_symbol", "product", "quantity", "net_price", "realised_pnl", "exchange"] if c in pdf.columns]
            st.dataframe(pdf[cols], use_container_width=True, hide_index=True)
        else: st.info("Groww returned no CASH positions.")
    else: st.caption("Select Refresh to retrieve your holdings and CASH positions.")
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

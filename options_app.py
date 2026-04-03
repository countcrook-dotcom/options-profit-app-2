import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import yfinance as yf

st.set_page_config(page_title="Options Profit + Trends App", layout="wide")
st.title("🚀 Options Profit Calculator + Inception Trends + Barchart-Style Chain")
st.markdown("**100% Free • No API key • Powered by Yahoo Finance (yfinance)**")

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("Analyze Specific Option")
    underlying = st.text_input("Underlying Ticker", value="AAPL").strip().upper()
    opt_type_input = st.selectbox("Call or Put", ["Call", "Put"])
    opt_type = "CALL" if opt_type_input == "Call" else "PUT"
    strike = st.number_input("Strike Price", value=220.0, step=0.5)
    expiration = st.date_input("Expiration Date", value=datetime(2025, 4, 18).date())
    premium = st.number_input("Premium per share ($)", value=4.50, step=0.01)
    contracts = st.number_input("Number of Contracts", value=1, min_value=1, step=1)
    current_price = st.number_input("Current Underlying Price", value=225.0, step=0.01)
    analyze_btn = st.button("🔥 Analyze This Option", type="primary")

# ==================== BARCHART-STYLE CHAIN BROWSER (Free & Live) ====================
with st.expander("🔍 Barchart-Style Live Options Chain", expanded=True):
    st.subheader("Load full options chain")
    st.caption("Exactly like the Barchart page — Last, Bid, Ask, Vol, OI, IV")

    chain_ticker = st.text_input("Underlying Ticker", value=underlying, key="chain_ticker")

    if st.button("📊 Load Full Chain"):
        with st.spinner("Fetching live chain from Yahoo Finance..."):
            try:
                tk = yf.Ticker(chain_ticker)
                expirations = tk.options

                if not expirations:
                    st.warning("No options found.")
                else:
                    selected_exp = st.selectbox("Choose Expiration", expirations, index=0)
                    chain = tk.option_chain(selected_exp)

                    df_calls = chain.calls.copy()
                    df_puts = chain.puts.copy()

                    df_calls["Type"] = "CALL"
                    df_puts["Type"] = "PUT"

                    df_chain = pd.concat([df_calls, df_puts])
                    df_chain = df_chain[["Type", "strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]]
                    df_chain = df_chain.rename(columns={
                        "strike": "Strike",
                        "lastPrice": "Last",
                        "bid": "Bid",
                        "ask": "Ask",
                        "volume": "Volume",
                        "openInterest": "Open Interest",
                        "impliedVolatility": "IV %"
                    })
                    df_chain["IV %"] = (df_chain["IV %"] * 100).round(2)
                    df_chain = df_chain.sort_values(by=["Type", "Strike"])

                    st.dataframe(
                        df_chain,
                        use_container_width=True,
                        height=600,
                        column_config={
                            "Last": st.column_config.NumberColumn(format="$%.2f"),
                            "Bid": st.column_config.NumberColumn(format="$%.2f"),
                            "Ask": st.column_config.NumberColumn(format="$%.2f"),
                            "Volume": st.column_config.NumberColumn(format="%.0f"),
                            "Open Interest": st.column_config.NumberColumn(format="%.0f"),
                            "IV %": st.column_config.NumberColumn(format="%.2f"),
                        }
                    )

                    st.success(f"✅ Loaded {len(df_chain)} contracts")
                    st.info("**Tip:** Copy any row’s Strike + Type → paste into sidebar → click Analyze")

            except Exception as e:
                st.error(f"Error loading chain: {e}")

# ==================== MAIN ANALYSIS ====================
if analyze_btn:
    with st.spinner("Fetching option data and history..."):
        try:
            # Build option ticker symbol for yfinance (e.g. AAPL250418C00220000)
            exp_str = expiration.strftime("%y%m%d")
            strike_str = f"{int(strike*1000):08d}"
            opt_symbol = f"{underlying}{exp_str}{'C' if opt_type == 'CALL' else 'P'}{strike_str}"

            # Get current option data
            opt = yf.Ticker(opt_symbol)
            hist = opt.history(period="max")  # This pulls from inception!

            if hist.empty:
                st.error("No data found for this option yet (too new or invalid).")
                st.stop()

            current_data = opt.info if hasattr(opt, 'info') else {}
            last_price = hist['Close'].iloc[-1] if not hist.empty else premium

            st.success(f"✅ Option found: **{opt_symbol}**")

            # Profit calculator
            def profit_at_price(price):
                if opt_type == "CALL":
                    return max(0, price - strike) - premium
                else:
                    return max(0, strike - price) - premium

            breakeven = strike + premium if opt_type == "CALL" else strike - premium
            max_loss = -premium * 100 * contracts

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Breakeven", f"${breakeven:.2f}")
            col2.metric("Max Loss", f"${max_loss:,.0f}")
            col3.metric("Max Profit", "Unlimited ↑" if opt_type == "CALL" else f"${(strike - premium)*100*contracts:,.0f}")
            col4.metric("Shares", f"{contracts * 100}")

            # P/L graph
            prices = np.linspace(max(0, current_price * 0.4), current_price * 1.8, 200)
            profits = [profit_at_price(p) * 100 * contracts for p in prices]
            fig_pl = go.Figure()
            fig_pl.add_trace(go.Scatter(x=prices, y=profits, mode='lines', name='P/L', line=dict(color='green', width=3)))
            fig_pl.add_hline(y=0, line_dash="dash", line_color="black")
            fig_pl.add_vline(x=strike, line_dash="dash", line_color="red", annotation_text="Strike")
            fig_pl.add_vline(x=breakeven, line_dash="dash", line_color="blue", annotation_text="Breakeven")
            fig_pl.add_vline(x=current_price, line_dash="dot", line_color="purple", annotation_text="Current")
            fig_pl.update_layout(title="Profit/Loss at Expiration", xaxis_title="Stock Price at Expiration", yaxis_title="Total P/L ($)", height=400)
            st.plotly_chart(fig_pl, use_container_width=True)

            # Historical graph from inception (price + volume)
            st.subheader(f"📈 Historical Trends – {opt_symbol} (from first trade day)")
            st.caption(f"First traded: **{hist.index[0].date()}** | {len(hist)} trading days")

            fig_hist = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3],
                                     subplot_titles=("Option Premium Price", "Daily Volume"))
            fig_hist.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Close Price", line=dict(color="blue")), row=1, col=1)
            fig_hist.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volume", marker_color="orange", opacity=0.7), row=2, col=1)
            fig_hist.update_layout(height=600, title_text=f"{opt_symbol} — Full History Since Inception")
            st.plotly_chart(fig_hist, use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
            st.info("Tip: Make sure the expiration and strike exist on Yahoo Finance.")

st.caption("✅ No API key needed • Built with yfinance (Yahoo Finance) • Deployed on Streamlit Cloud")

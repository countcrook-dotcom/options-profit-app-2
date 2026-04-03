import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import yfinance as yf
from scipy.stats import norm

st.set_page_config(page_title="Options Profit + Trends App", layout="wide")
st.title("🚀 Options Profit Calculator + Inception Trends + Barchart-Style Chain")
st.markdown("**100% Free • No API key • Click any option to analyze instantly**")

# ==================== SIDEBAR (manual entry fallback) ====================
with st.sidebar:
    st.header("Manual Option Entry")
    underlying = st.text_input("Underlying Ticker", value="AAPL").strip().upper()
    opt_type_input = st.selectbox("Call or Put", ["Call", "Put"])
    opt_type = "CALL" if opt_type_input == "Call" else "PUT"
    strike = st.number_input("Strike Price", value=220.0, step=0.5)
    expiration = st.date_input("Expiration Date", value=datetime(2025, 4, 18).date())
    premium = st.number_input("Premium per share ($)", value=4.50, step=0.01)
    contracts = st.number_input("Number of Contracts", value=1, min_value=1, step=1)
    current_price = st.number_input("Current Underlying Price (optional)", value=225.0, step=0.01)
    analyze_btn = st.button("🔥 Analyze Manually", type="primary")

# ==================== BARCHART-STYLE CHAIN (main flow) ====================
with st.expander("🔍 Barchart-Style Live Options Chain", expanded=True):
    st.subheader("Load chain → click any option → get charts instantly")
    
    chain_underlying = st.text_input("Underlying Ticker", value=underlying, key="chain_underlying")
    
    tk = yf.Ticker(chain_underlying)
    current_stock_price = tk.fast_info.get('lastPrice', None)
    if current_stock_price:
        st.metric("Current Underlying Stock Price", f"${current_stock_price:.2f}")
    
    if tk.options:
        selected_exp_str = st.selectbox("Select Expiration Date", tk.options, key="selected_exp_key")
        selected_exp = datetime.strptime(selected_exp_str, "%Y-%m-%d").date()
        
        if st.button("📊 Load Chain for this Expiration"):
            with st.spinner("Fetching live chain..."):
                chain = tk.option_chain(selected_exp_str)
                df_calls = chain.calls.copy()
                df_puts = chain.puts.copy()
                df_calls["Type"] = "CALL"
                df_puts["Type"] = "PUT"
                df_chain = pd.concat([df_calls, df_puts])
                df_chain = df_chain[["Type", "strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]]
                df_chain = df_chain.rename(columns={
                    "strike": "Strike", "lastPrice": "Last", "bid": "Bid", "ask": "Ask",
                    "volume": "Volume", "openInterest": "Open Interest", "impliedVolatility": "IV %"
                })
                df_chain["IV %"] = (df_chain["IV %"] * 100).round(2)
                df_chain = df_chain.sort_values(by=["Type", "Strike"])
                
                st.session_state.df_chain = df_chain
                st.session_state.selected_exp = selected_exp_str
                st.session_state.current_stock_price = current_stock_price
                st.success(f"✅ Loaded {len(df_chain)} contracts")

        if 'df_chain' in st.session_state:
            df_chain = st.session_state.df_chain
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
            
            # Click-to-analyze
            option_list = [f"{row['Type']} ${row['Strike']:.2f} (Last ${row['Last']:.2f})" for _, row in df_chain.iterrows()]
            selected_option_str = st.selectbox("👉 Select option to analyze", option_list, key="selected_option_key")
            
            if st.button("🚀 Load P/L + Historical Charts for this option"):
                # Parse selection
                type_part, rest = selected_option_str.split(" $")
                strike_part = rest.split(" (Last")[0]
                selected_type = type_part
                selected_strike = float(strike_part)
                
                # Get IV and Last price from chain
                row = df_chain[(df_chain['Type'] == selected_type) & (df_chain['Strike'] == selected_strike)].iloc[0]
                iv = row['IV %'] / 100 if pd.notna(row['IV %']) else 0.30
                premium = row['Last'] if pd.notna(row['Last']) else premium
                
                st.success(f"✅ Analyzing {selected_type} ${selected_strike:.2f} exp {st.session_state.selected_exp}")
                
                # ===================== PROFIT CALCULATOR =====================
                def profit_at_price(price):
                    if selected_type == "CALL":
                        return max(0, price - selected_strike) - premium
                    else:
                        return max(0, selected_strike - price) - premium
                
                breakeven = selected_strike + premium if selected_type == "CALL" else selected_strike - premium
                max_loss = -premium * 100 * contracts
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Breakeven at Exp.", f"${breakeven:.2f}")
                col2.metric("Max Loss", f"${max_loss:,.0f}")
                col3.metric("Max Profit", "Unlimited ↑" if selected_type == "CALL" else f"${(selected_strike - premium)*100*contracts:,.0f}")
                col4.metric("Shares", f"{contracts * 100}")
                
                # P/L graph
                prices = np.linspace(max(0, st.session_state.get('current_stock_price', 225) * 0.4),
                                   st.session_state.get('current_stock_price', 225) * 1.8, 200)
                profits = [profit_at_price(p) * 100 * contracts for p in prices]
                fig_pl = go.Figure()
                fig_pl.add_trace(go.Scatter(x=prices, y=profits, mode='lines', name='P/L', line=dict(color='green', width=3)))
                fig_pl.add_hline(y=0, line_dash="dash", line_color="black")
                fig_pl.add_vline(x=selected_strike, line_dash="dash", line_color="red", annotation_text="Strike")
                fig_pl.add_vline(x=breakeven, line_dash="dash", line_color="blue", annotation_text="Breakeven")
                fig_pl.update_layout(title="Profit/Loss at Expiration", xaxis_title="Stock Price at Expiration", yaxis_title="Total P/L ($)", height=400)
                st.plotly_chart(fig_pl, use_container_width=True)
                
                # Profit Likeliness %
                today = datetime.now().date()
                days_to_exp = (selected_exp - today).days
                pop = 50.0
                if days_to_exp > 0 and iv > 0:
                    T = days_to_exp / 365.0
                    S = st.session_state.get('current_stock_price', 225)
                    K = breakeven
                    sigma = iv
                    d2 = (np.log(S / K) - 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
                    pop = norm.cdf(d2) * 100 if selected_type == "CALL" else norm.cdf(-d2) * 100
                st.metric("📊 Estimated Probability of Profit", f"{pop:.1f}%", help="Probability the option finishes in-the-money beyond breakeven (based on IV)")
                
                # Historical trends from inception
                opt_symbol = f"{chain_underlying}{selected_exp_str.replace('-','')[2:]}{selected_type[0]}{int(selected_strike*1000):08d}"
                opt = yf.Ticker(opt_symbol)
                hist = opt.history(period="max")
                if not hist.empty:
                    st.subheader(f"📈 Historical Trends – {opt_symbol} (from inception)")
                    st.caption(f"First traded: **{hist.index[0].date()}** | {len(hist)} trading days")
                    fig_hist = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3],
                                             subplot_titles=("Option Premium Price", "Daily Volume"))
                    fig_hist.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Close Price", line=dict(color="blue")), row=1, col=1)
                    fig_hist.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volume", marker_color="orange", opacity=0.7), row=2, col=1)
                    fig_hist.update_layout(height=600, title_text=f"{opt_symbol} — Full History Since Inception")
                    st.plotly_chart(fig_hist, use_container_width=True)

st.caption("Built with ❤️ using yfinance • Click any option in the chain above to analyze instantly")

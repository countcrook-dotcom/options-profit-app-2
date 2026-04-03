import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
from polygon import RESTClient

st.set_page_config(page_title="Options Profit + Trends App", layout="wide")
st.title("🚀 Options Profit Calculator + Inception Trends")
st.markdown("**Real market data • Exact option contract • Historical volume & trades from day 1**")

# ==================== SIDEBAR INPUTS ====================
with st.sidebar:
    st.header("Option Details")
    underlying = st.text_input("Underlying Ticker", value="AAPL").strip().upper()
    
    opt_type_input = st.selectbox("Call or Put", ["Call", "Put"])
    contract_type = "call" if opt_type_input == "Call" else "put"
    opt_type = "CALL" if opt_type_input == "Call" else "PUT"
    
    strike = st.number_input("Strike Price", value=220.0, step=0.5)
    expiration = st.date_input("Expiration Date", value=datetime(2025, 4, 18).date())
    premium = st.number_input("Premium per share ($)", value=4.50, step=0.01)
    contracts = st.number_input("Number of Contracts", value=1, min_value=1, step=1)
    current_price = st.number_input("Current Underlying Price (optional)", value=225.0, step=0.01)

    api_key = st.text_input("Polygon API Key", type="password", value=st.secrets.get("POLYGON_API_KEY", ""))
    analyze_btn = st.button("🔥 Analyze This Option", type="primary")

# ==================== MAIN APP ====================
if analyze_btn and api_key:
    client = RESTClient(api_key=api_key)
    
    with st.spinner("Finding exact option contract and fetching data..."):
        try:
            # Find exact contract
            option_contracts = list(client.list_options_contracts(
                underlying_ticker=underlying,
                contract_type=contract_type,
                expiration_date=expiration.strftime("%Y-%m-%d"),
                strike_price=strike,
                limit=5
            ))
            
            if not option_contracts:
                st.error(f"❌ No {opt_type} option found for {underlying} {expiration} @ ${strike}")
                st.stop()
            
            option = option_contracts[0]
            ticker = option.ticker
            
            st.success(f"✅ Found: **{ticker}** ({opt_type} ${strike} exp {expiration})")
            
            # ==================== PROFIT CALCULATOR ====================
            def profit_at_price(price):
                if opt_type == "CALL":
                    return max(0, price - strike) - premium
                else:
                    return max(0, strike - price) - premium
            
            breakeven = strike + premium if opt_type == "CALL" else strike - premium
            max_loss = -premium * 100 * contracts
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Breakeven at Exp.", f"${breakeven:.2f}")
            col2.metric("Max Loss", f"${max_loss:,.0f}", delta="100% loss if worthless")
            if opt_type == "CALL":
                col3.metric("Max Profit", "Unlimited ↑")
            else:
                col3.metric("Max Profit", f"${(strike - premium) * 100 * contracts:,.0f}")
            col4.metric("Contracts × 100", f"{contracts * 100} shares")
            
            # P/L Graph
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
            
            # ==================== HISTORICAL DATA FROM INCEPTION ====================
            st.subheader(f"📈 Historical Trends – {ticker} (from first trade day)")
            
            aggs = list(client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_="2000-01-01",
                to=datetime.now().strftime("%Y-%m-%d"),
                limit=50000
            ))
            
            if not aggs:
                st.warning("⚠️ No historical data yet (option is brand new)")
            else:
                df = pd.DataFrame([{
                    'date': pd.to_datetime(a.timestamp, unit='ms').date(),
                    'close': a.close,
                    'volume': a.volume,
                    'trades': getattr(a, 'transactions', 0)
                } for a in aggs])
                df = df.sort_values('date')
                
                inception = df['date'].iloc[0]
                st.caption(f"First traded: **{inception}** | {len(df)} trading days")
                
                # Historical Charts (FIXED subplot error)
                fig_hist = make_subplots(
                    rows=2, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.08, 
                    row_heights=[0.7, 0.3],
                    subplot_titles=("Option Premium Price", "Volume & Trade Count"),
                    specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
                )
                
                fig_hist.add_trace(go.Scatter(x=df['date'], y=df['close'], name="Close Price", line=dict(color="blue")), row=1, col=1)
                fig_hist.add_trace(go.Bar(x=df['date'], y=df['volume'], name="Daily Volume", marker_color="orange", opacity=0.7), row=2, col=1)
                fig_hist.add_trace(go.Scatter(x=df['date'], y=df['trades'], name="Daily Trades", line=dict(color="purple")), row=2, col=1, secondary_y=True)
                
                fig_hist.update_layout(height=600, title_text=f"{ticker} — Full History Since Inception")
                fig_hist.update_yaxes(title_text="Price ($)", row=1, col=1)
                fig_hist.update_yaxes(title_text="Volume", row=2, col=1)
                fig_hist.update_yaxes(title_text="Trades", secondary_y=True, row=2, col=1)
                st.plotly_chart(fig_hist, use_container_width=True)
                
                # Quick stats
                st.info(f"Total volume since inception: **{df['volume'].sum():,} contracts** | Avg daily volume: **{df['volume'].mean():,.0f}**")
        
        except Exception as e:
            st.error(f"Error: {e}")
            st.info("Tip: Make sure your Polygon API key is correct and has Options data access.")

else:
    st.info("👈 Fill in the details on the left and click **Analyze This Option**")
    st.caption("Need a Polygon key? Get it free at massive.com/dashboard/keys")

st.caption("Built with ❤️ using Streamlit + Polygon.io (now Massive) • Deployed on Streamlit Cloud")

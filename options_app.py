import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime
import yfinance as yf
from polygon import RESTClient
from scipy.stats import norm

st.set_page_config(page_title="Options Profit + Trends App", layout="wide")
st.title("🚀 Options Profit Calculator + Inception Trends + Barchart-Style Chain")
st.markdown("**Click any row to analyze** • Global Top 10 with filters • Live prices")

# ==================== SIDEBAR ====================
with st.sidebar:
    st.header("Data Source")
    data_source = st.radio("Select provider:", 
                          ["yfinance (free, no key)", "Polygon (more reliable)"], 
                          horizontal=True, key="data_source")
    
    polygon_key = st.secrets.get("POLYGON_API_KEY", "") if data_source == "Polygon (more reliable)" else ""

# ==================== GLOBAL TOP 10 ====================
popular_tickers = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "AMZN", "GOOGL", "META", "MSFT", "AMD", "SMCI", "PLTR"]

st.subheader("🔥 Global Top 10 Highest Probability Options Today")
col_a, col_b = st.columns([1, 1])
with col_a:
    exp_filter = st.selectbox("Expiration Window", 
                             ["Nearest Expiration", "0-7 days", "7-30 days", "30-60 days", "60+ days"],
                             key="exp_filter")
with col_b:
    moneyness_filter = st.selectbox("Moneyness Filter", 
                                   ["Any", "ITM", "OTM", "0-5% ITM", "5-10% ITM", "10%+ ITM", "0-5% OTM", "5-10% OTM"],
                                   key="moneyness_filter")

if st.button("Scan Global Top 10", use_container_width=True, type="primary"):
    with st.spinner("Scanning across popular tickers..."):
        top_options = []
        for ticker in popular_tickers:
            try:
                tk = yf.Ticker(ticker)
                current_price = tk.fast_info.get('lastPrice', None)
                if not current_price or not tk.options:
                    continue
                exps = tk.options
                if exp_filter == "Nearest Expiration":
                    exp = exps[0]
                else:
                    days_list = [(datetime.strptime(e, "%Y-%m-%d").date() - datetime.now().date()).days for e in exps]
                    if exp_filter == "0-7 days":
                        exp = next((e for e, d in zip(exps, days_list) if 0 < d <= 7), exps[0])
                    elif exp_filter == "7-30 days":
                        exp = next((e for e, d in zip(exps, days_list) if 7 < d <= 30), exps[0])
                    elif exp_filter == "30-60 days":
                        exp = next((e for e, d in zip(exps, days_list) if 30 < d <= 60), exps[0])
                    else:
                        exp = next((e for e, d in zip(exps, days_list) if d > 60), exps[0])

                chain = tk.option_chain(exp)
                df = pd.concat([chain.calls, chain.puts])
                df = df.rename(columns={"strike": "Strike", "lastPrice": "Last", "impliedVolatility": "IV"})
                df["Type"] = ["CALL"] * len(chain.calls) + ["PUT"] * len(chain.puts)
                df["Ticker"] = ticker
                df["Expiration"] = exp
                df["Current Price"] = current_price

                for _, row in df.iterrows():
                    selected_type = row["Type"]
                    selected_strike = row["Strike"]
                    premium = row["Last"] if pd.notna(row["Last"]) else 0.0
                    iv = row["IV"] if pd.notna(row["IV"]) else 0.30
                    breakeven = selected_strike + premium if selected_type == "CALL" else selected_strike - premium
                    days_to_exp = (datetime.strptime(exp, "%Y-%m-%d").date() - datetime.now().date()).days
                    if days_to_exp <= 0 or iv <= 0: continue
                    T = days_to_exp / 365.0
                    S = current_price
                    K = breakeven
                    sigma = iv
                    d2 = (np.log(S / K) - 0.5 * sigma**2 * T) / (sigma * np.sqrt(T)) if K > 0 else 0
                    pop = norm.cdf(d2) * 100 if selected_type == "CALL" else norm.cdf(-d2) * 100

                    moneyness = (selected_strike - current_price) / current_price * 100 if selected_type == "CALL" else (current_price - selected_strike) / current_price * 100

                    if moneyness_filter != "Any":
                        if moneyness_filter == "ITM" and moneyness <= 0: continue
                        if moneyness_filter == "OTM" and moneyness >= 0: continue
                        if "ITM" in moneyness_filter and not (0 < moneyness <= float(moneyness_filter.split("%")[0].split("-")[-1] if "-" in moneyness_filter else 100)): continue
                        if "OTM" in moneyness_filter and not (-float(moneyness_filter.split("%")[0].split("-")[-1] if "-" in moneyness_filter else 100) <= moneyness < 0): continue

                    top_options.append({
                        "Ticker": ticker,
                        "Type": selected_type,
                        "Strike": selected_strike,
                        "Last": premium,
                        "POP %": round(pop, 1),
                        "Expiration": exp,
                        "Current Price": current_price,
                        "Moneyness %": round(moneyness, 1)
                    })
            except:
                continue

        df_top = pd.DataFrame(top_options)
        df_top = df_top.sort_values(by="POP %", ascending=False).head(10)
        st.session_state.df_top10 = df_top
        st.success("✅ Top 10 updated!")

if 'df_top10' in st.session_state:
    selection_top = st.dataframe(
        st.session_state.df_top10.style.highlight_max(subset=["POP %"], color="#00ff00"),
        use_container_width=True,
        height=400,
        on_select="rerun",
        selection_mode="single-row"
    )

    if len(selection_top.selection.rows) > 0:
        row = st.session_state.df_top10.iloc[selection_top.selection.rows[0]]
        chain_underlying = row["Ticker"]
        selected_exp_str = row["Expiration"]
        selected_type = row["Type"]
        selected_strike = row["Strike"]
        premium = row["Last"]
        current_price = row["Current Price"]

        st.success(f"✅ Analyzing {chain_underlying} {selected_type} ${selected_strike:.2f} from Global Top 10")

        def profit_at_price(price):
            if selected_type == "CALL":
                return max(0, price - selected_strike) - premium
            else:
                return max(0, selected_strike - price) - premium

        breakeven = selected_strike + premium if selected_type == "CALL" else selected_strike - premium

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Breakeven", f"${breakeven:.2f}")
        c2.metric("Max Loss", f"${-premium*100:,.0f}")
        c3.metric("Max Profit", "Unlimited ↑" if selected_type == "CALL" else f"${(selected_strike - premium)*100:,.0f}")
        c4.metric("Shares", "100")

        prices = np.linspace(max(0, current_price * 0.4), current_price * 1.8, 200)
        profits = [profit_at_price(p) * 100 for p in prices]
        fig_pl = go.Figure()
        fig_pl.add_trace(go.Scatter(x=prices, y=profits, mode='lines', name='P/L', line=dict(color='green', width=3)))
        fig_pl.add_hline(y=0, line_dash="dash", line_color="black")
        fig_pl.add_vline(x=selected_strike, line_dash="dash", line_color="red", annotation_text="Strike")
        fig_pl.add_vline(x=breakeven, line_dash="dash", line_color="blue", annotation_text="Breakeven")
        fig_pl.update_layout(title="Profit/Loss at Expiration", xaxis_title="Stock Price at Expiration", yaxis_title="Total P/L ($)", height=400)
        st.plotly_chart(fig_pl, use_container_width=True)

        st.metric("Estimated Probability of Profit", f"{row['POP %']:.1f}%")

        opt_symbol = f"{chain_underlying}{selected_exp_str.replace('-','')[2:]}{selected_type[0]}{int(selected_strike*1000):08d}"
        opt = yf.Ticker(opt_symbol)
        hist = opt.history(period="max")
        if not hist.empty:
            st.subheader(f"📈 Historical Trends – {opt_symbol}")
            st.caption(f"First traded: **{hist.index[0].date()}**")
            fig_hist = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3])
            fig_hist.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Close Price", line=dict(color="blue")), row=1, col=1)
            fig_hist.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volume", marker_color="orange"), row=2, col=1)
            fig_hist.update_layout(height=600, title_text=f"{opt_symbol} — Full History Since Inception")
            st.plotly_chart(fig_hist, use_container_width=True)

# ==================== BARCHART-STYLE LIVE OPTIONS CHAIN ====================
with st.expander("📊 Barchart-Style Live Options Chain", expanded=True):
    col_ticker, col_price = st.columns([3, 1])
    with col_ticker:
        chain_underlying = st.text_input("Underlying Ticker", value="AAPL", key="chain_underlying").upper().strip()
    with col_price:
        if chain_underlying:
            try:
                tk_price = yf.Ticker(chain_underlying)
                live_price = tk_price.fast_info.get('lastPrice', None)
                st.metric("Current Price", f"${live_price:.2f}" if live_price else "—")
            except:
                st.metric("Current Price", "—")

    if st.button("Load Available Expirations & Chain", use_container_width=True):
        with st.spinner(f"Fetching from {data_source}..."):
            try:
                if data_source == "yfinance (free, no key)":
                    tk = yf.Ticker(chain_underlying)
                    current_stock_price = tk.fast_info.get('lastPrice', None)
                    exp_list = tk.options
                else:
                    if not polygon_key:
                        st.error("Enter your Polygon API key in Streamlit secrets")
                        st.stop()
                    client = RESTClient(polygon_key)
                    current_stock_price = client.get_last_trade(chain_underlying).price
                    contracts = list(client.list_options_contracts(underlying_ticker=chain_underlying, limit=1000))
                    exp_list = sorted(set(c.expiration_date for c in contracts))

                st.session_state.exp_list = exp_list
                st.session_state.current_stock_price = current_stock_price
                st.success(f"✅ Found {len(exp_list)} expiration dates")
            except Exception as e:
                st.error(f"Error: {str(e)}")

    if 'exp_list' in st.session_state:
        selected_exp_str = st.selectbox("Select Expiration Date", st.session_state.exp_list, key="selected_exp_key")

        if st.button("Load Chain for Selected Date", use_container_width=True):
            with st.spinner("Loading full chain..."):
                try:
                    if data_source == "yfinance (free, no key)":
                        tk = yf.Ticker(chain_underlying)
                        chain = tk.option_chain(selected_exp_str)
                        df_calls = chain.calls.copy()
                        df_puts = chain.puts.copy()
                    else:
                        client = RESTClient(polygon_key)
                        contracts = list(client.list_options_contracts(underlying_ticker=chain_underlying, expiration_date=selected_exp_str, limit=1000))
                        data = []
                        for c in contracts:
                            data.append({
                                "Type": c.contract_type.upper(),
                                "Strike": c.strike_price,
                                "Last": getattr(c, 'last_trade_price', None),
                                "Bid": getattr(c, 'bid_price', None),
                                "Ask": getattr(c, 'ask_price', None),
                                "Volume": getattr(c, 'volume', None),
                                "Open Interest": getattr(c, 'open_interest', None),
                                "IV %": getattr(c, 'implied_volatility', None)
                            })
                        df_raw = pd.DataFrame(data)
                        df_calls = df_raw[df_raw["Type"] == "CALL"].copy()
                        df_puts = df_raw[df_raw["Type"] == "PUT"].copy()

                    df_calls["Type"] = "CALL"
                    df_puts["Type"] = "PUT"
                    df_chain = pd.concat([df_calls, df_puts], ignore_index=True)
                    df_chain = df_chain.rename(columns={
                        "strike": "Strike", "strike_price": "Strike",
                        "lastPrice": "Last", "last_trade_price": "Last",
                        "bid": "Bid", "bid_price": "Bid",
                        "ask": "Ask", "ask_price": "Ask",
                        "volume": "Volume",
                        "openInterest": "Open Interest", "open_interest": "Open Interest",
                        "impliedVolatility": "IV %", "implied_volatility": "IV %"
                    })
                    df_chain = df_chain[["Type", "Strike", "Last", "Bid", "Ask", "Volume", "Open Interest", "IV %"]]
                    df_chain["IV %"] = (df_chain["IV %"] * 100).round(2)
                    df_chain = df_chain.sort_values(by="Strike")

                    st.session_state.df_chain = df_chain
                    st.session_state.selected_exp_str = selected_exp_str
                    st.session_state.current_stock_price = st.session_state.get('current_stock_price', 225)

                except Exception as e:
                    st.error(f"Error loading chain: {str(e)}")

    if 'df_chain' in st.session_state:
        df_chain = st.session_state.df_chain
        current_price = st.session_state.get('current_stock_price', 225)

        strikes = df_chain['Strike'].unique()
        closest_strikes = sorted(strikes, key=lambda x: abs(x - current_price))[:5]

        def highlight_closest(row):
            return ['background-color: lightgreen' if row['Strike'] in closest_strikes else '' for _ in row.index]

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📈 Calls")
            calls = df_chain[df_chain['Type'] == "CALL"].copy()
            selection_calls = st.dataframe(
                calls.style.apply(highlight_closest, axis=1),
                use_container_width=True,
                height=600,
                on_select="rerun",
                selection_mode="single-row"
            )

        with col2:
            st.subheader("📉 Puts")
            puts = df_chain[df_chain['Type'] == "PUT"].copy()
            selection_puts = st.dataframe(
                puts.style.apply(highlight_closest, axis=1),
                use_container_width=True,
                height=600,
                on_select="rerun",
                selection_mode="single-row"
            )

        selected_row = None
        if len(selection_calls.selection.rows) > 0:
            selected_row = calls.iloc[selection_calls.selection.rows[0]]
        elif len(selection_puts.selection.rows) > 0:
            selected_row = puts.iloc[selection_puts.selection.rows[0]]

        if selected_row is not None:
            selected_type = selected_row['Type']
            selected_strike = selected_row['Strike']
            premium = selected_row['Last'] if pd.notna(selected_row['Last']) else 0.0
            iv = selected_row['IV %'] / 100 if pd.notna(selected_row['IV %']) else 0.30

            st.success(f"✅ Analyzing {selected_type} ${selected_strike:.2f} (clicked from chain)")

            def profit_at_price(price):
                if selected_type == "CALL":
                    return max(0, price - selected_strike) - premium
                else:
                    return max(0, selected_strike - price) - premium

            breakeven = selected_strike + premium if selected_type == "CALL" else selected_strike - premium

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Breakeven", f"${breakeven:.2f}")
            c2.metric("Max Loss", f"${-premium*100:,.0f}")
            c3.metric("Max Profit", "Unlimited ↑" if selected_type == "CALL" else f"${(selected_strike - premium)*100:,.0f}")
            c4.metric("Shares", "100")

            prices = np.linspace(max(0, current_price * 0.4), current_price * 1.8, 200)
            profits = [profit_at_price(p) * 100 for p in prices]
            fig_pl = go.Figure()
            fig_pl.add_trace(go.Scatter(x=prices, y=profits, mode='lines', name='P/L', line=dict(color='green', width=3)))
            fig_pl.add_hline(y=0, line_dash="dash", line_color="black")
            fig_pl.add_vline(x=selected_strike, line_dash="dash", line_color="red", annotation_text="Strike")
            fig_pl.add_vline(x=breakeven, line_dash="dash", line_color="blue", annotation_text="Breakeven")
            fig_pl.update_layout(title="Profit/Loss at Expiration", xaxis_title="Stock Price at Expiration", yaxis_title="Total P/L ($)", height=400)
            st.plotly_chart(fig_pl, use_container_width=True)

            today = datetime.now().date()
            days_to_exp = (datetime.strptime(st.session_state.selected_exp_str, "%Y-%m-%d").date() - today).days
            pop = 50.0
            if days_to_exp > 0 and iv > 0:
                T = days_to_exp / 365.0
                S = current_price
                K = breakeven
                sigma = iv
                d2 = (np.log(S / K) - 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
                pop = norm.cdf(d2) * 100 if selected_type == "CALL" else norm.cdf(-d2) * 100
            st.metric("Estimated Probability of Profit", f"{pop:.1f}%")

            opt_symbol = f"{chain_underlying}{st.session_state.selected_exp_str.replace('-','')[2:]}{selected_type[0]}{int(selected_strike*1000):08d}"
            opt = yf.Ticker(opt_symbol)
            hist = opt.history(period="max")
            if not hist.empty:
                st.subheader(f"📈 Historical Trends – {opt_symbol}")
                st.caption(f"First traded: **{hist.index[0].date()}**")
                fig_hist = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.7, 0.3])
                fig_hist.add_trace(go.Scatter(x=hist.index, y=hist['Close'], name="Close Price", line=dict(color="blue")), row=1, col=1)
                fig_hist.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name="Volume", marker_color="orange"), row=2, col=1)
                fig_hist.update_layout(height=600, title_text=f"{opt_symbol} — Full History Since Inception")
                st.plotly_chart(fig_hist, use_container_width=True)

st.caption("✅ Exact GitHub/Cloud version • All features included")

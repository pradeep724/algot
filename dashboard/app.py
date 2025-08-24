# dashboard.py
import streamlit as st
import pandas as pd
import time

st.set_page_config(page_title="Trade Monitor", layout="wide")

st.title("📊 Live Trade Monitor")

TRADE_CSV = "data/trade_monitor/latest_status.csv"

# Refresh interval (seconds)
REFRESH_INTERVAL = 10

placeholder = st.empty()

while True:
    try:
        df = pd.read_csv(TRADE_CSV)
        df = df[['symbol','price','ltp','stop_price','target_price','qty','status','pnl']]
        
        # Conditional formatting
        def highlight_status(val):
            if val == 'STOP_LOSS_HIT':
                return 'background-color: red; color: white'
            elif val == 'TARGET_HIT':
                return 'background-color: green; color: white'
            elif val == 'ACTIVE':
                return 'background-color: yellow; color: black'
            return ''

        st.dataframe(df.style.applymap(highlight_status, subset=['status']))
        
    except Exception as e:
        st.error(f"Error loading trade monitor CSV: {e}")

    time.sleep(REFRESH_INTERVAL)

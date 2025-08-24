import os
import pandas as pd
import streamlit as st
from datetime import datetime

PAPER_TRADE_DIR = "data/paper_trades"
PAPER_TRADE_DIR="/Users/pradeep/Documents/algo/v1/algot/data/paper_trades"


st.set_page_config(page_title="Paper Trading Dashboard", layout="wide")
st.title("📊 Paper Trading & Backtesting Dashboard")

def load_all_paper_trades():
    """Load all paper trade CSVs into one DataFrame"""
    trades = []
    if not os.path.exists(PAPER_TRADE_DIR):
        return pd.DataFrame()
    for f in os.listdir(PAPER_TRADE_DIR):
        if f.endswith(".csv"):
            df = pd.read_csv(os.path.join(PAPER_TRADE_DIR, f))
            trades.append(df)
    return pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()

# --- Load Data ---
df = load_all_paper_trades()

if df.empty:
    st.warning("No paper trades found. Run paper_trade.py first!")
else:
    st.subheader("Summary Metrics")
    total_trades = len(df)
    open_trades = len(df[df["status"] == "Open"])
    target_hit = len(df[df["status"] == "Target Hit"])
    sl_hit = len(df[df["status"] == "SL Hit"])
    total_pnl = df["pnl"].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Trades", total_trades)
    col2.metric("Open Trades", open_trades)
    col3.metric("Target Hit", target_hit)
    col4.metric("SL Hit", sl_hit)
    col5.metric("Total P&L", f"{total_pnl:.2f}")

    st.subheader("Trades Details")
    st.dataframe(df.sort_values(by="hit_time", ascending=False), use_container_width=True)

    st.subheader("P&L by Symbol")
    pnl_by_symbol = df.groupby("symbol")["pnl"].sum().reset_index()
    st.bar_chart(pnl_by_symbol.set_index("symbol"))

    st.subheader("Hit Ratio by Symbol")
    hit_ratio = df.groupby("symbol")["status"].apply(
        lambda x: (x=="Target Hit").sum()/len(x)
    ).reset_index(name="hit_ratio")
    st.bar_chart(hit_ratio.set_index("symbol"))

    st.markdown("✅ Dashboard automatically aggregates all paper trade logs in `data/paper_trades/`")

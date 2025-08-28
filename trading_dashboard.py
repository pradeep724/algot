import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

st.set_page_config(page_title="ProTraderBot Dashboard", page_icon="📈", layout="wide")

def load_data():
    data = {}
    for instrument in ["NIFTY", "BANKNIFTY"]:
        csv_file = "backtest_results_" + instrument + ".csv"
        csv_file = f"results/{csv_file}"
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                df["entry_date"] = pd.to_datetime(df["entry_date"])
                data[instrument] = df
                st.sidebar.success("Loaded " + instrument + ": " + str(len(df)) + " trades")
            except Exception as e:
                st.sidebar.error("Error loading " + instrument + ": " + str(e))
    return data

def get_metrics(df):
    empty_result = {
        "total_trades": len(df) if not df.empty else 0,
        "success_trades": 0,
        "failure_trades": 0,
        "success_rate": 0,
        "total_pnl": 0,
        "target_hit": 0,
        "sl_hit": 0,
        "time_exit": 0
    }
    
    if df.empty or "pnl" not in df.columns:
        return empty_result
    
    completed = df.dropna(subset=["pnl"])
    if completed.empty:
        return empty_result
    
    success = completed[completed["pnl"] > 50]
    failure = completed[completed["pnl"] < -50]
    
    target_hit = len(completed[completed["pnl"] >= 300])
    sl_hit = len(completed[completed["pnl"] <= -200])
    time_exit = len(completed) - target_hit - sl_hit
    
    success_rate = len(success) / len(completed) * 100 if len(completed) > 0 else 0
    
    return {
        "total_trades": len(df),
        "success_trades": len(success),
        "failure_trades": len(failure),
        "success_rate": success_rate,
        "total_pnl": completed["pnl"].sum(),
        "target_hit": target_hit,
        "sl_hit": sl_hit,
        "time_exit": time_exit
    }

def create_pnl_chart(df, instrument):
    if df.empty or "pnl" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    completed = df.dropna(subset=["pnl"]).copy()
    completed = completed.sort_values("entry_date")
    completed["cumulative_pnl"] = completed["pnl"].cumsum()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=completed["entry_date"],
        y=completed["cumulative_pnl"],
        mode="lines+markers",
        name=instrument + " P&L",
        line=dict(width=3)
    ))
    
    fig.update_layout(title=instrument + " - Cumulative P&L")
    return fig

def create_pie_chart(df, instrument):
    if df.empty or "pnl" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    completed = df.dropna(subset=["pnl"])
    success = len(completed[completed["pnl"] > 50])
    failure = len(completed[completed["pnl"] < -50])
    no_change = len(completed) - success - failure
    
    labels = ["Success", "Failure", "No Change"]
    values = [success, failure, no_change]
    colors = ["#28a745", "#dc3545", "#ffc107"]
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, marker_colors=colors)])
    fig.update_layout(title=instrument + " - Trade Outcomes")
    return fig

def main():
    st.title("ProTraderBot Dashboard")
    
    data = load_data()
    
    if len(data) == 0:
        st.error("No data found!")
        st.info("Run: python run_backtest.py")
        return
    
    st.sidebar.header("Dashboard Controls")
    
    instruments = list(data.keys())
    selected = st.sidebar.selectbox("Select Instrument", ["All"] + instruments)
    
    if selected == "All":
        st.header("Portfolio Overview")
        
        total_trades = 0
        total_success = 0
        total_failure = 0
        total_pnl = 0
        total_target = 0
        total_sl = 0
        total_time = 0
        
        for instrument, df in data.items():
            metrics = get_metrics(df)
            total_trades += metrics["total_trades"]
            total_success += metrics["success_trades"]
            total_failure += metrics["failure_trades"]
            total_pnl += metrics["total_pnl"]
            total_target += metrics["target_hit"]
            total_sl += metrics["sl_hit"]
            total_time += metrics["time_exit"]
        
        completed = total_success + total_failure
        success_rate = total_success / completed * 100 if completed > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Trades", total_trades)
        with col2:
            st.metric("Success Rate", str(round(success_rate, 1)) + "%")
        with col3:
            st.metric("Total P&L", "Rs " + str(round(total_pnl, 0)))
        with col4:
            st.metric("Instruments", len(data))
        
        st.subheader("Exit Reasons")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success("Target Hit: " + str(total_target))
        with col2:
            st.error("SL Hit: " + str(total_sl))
        with col3:
            st.warning("Time Exit: " + str(total_time))
        
        for instrument, df in data.items():
            with st.expander(instrument + " Details", expanded=True):
                metrics = get_metrics(df)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Trades", metrics["total_trades"])
                with col2:
                    st.metric("Success Rate", str(round(metrics["success_rate"], 1)) + "%")
                with col3:
                    st.metric("P&L", "Rs " + str(round(metrics["total_pnl"], 0)))
                
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(create_pie_chart(df, instrument), use_container_width=True)
                with col2:
                    st.plotly_chart(create_pnl_chart(df, instrument), use_container_width=True)
    
    else:
        df = data[selected]
        st.header(selected + " Analysis")
        
        metrics = get_metrics(df)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total", metrics["total_trades"])
        with col2:
            st.metric("Success", metrics["success_trades"])
        with col3:
            st.metric("Failure", metrics["failure_trades"])
        with col4:
            st.metric("Rate", str(round(metrics["success_rate"], 1)) + "%")
        with col5:
            st.metric("P&L", "Rs " + str(round(metrics["total_pnl"], 0)))
        
        st.subheader("Exit Analysis")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success("Target Hit: " + str(metrics["target_hit"]))
        with col2:
            st.error("SL Hit: " + str(metrics["sl_hit"]))
        with col3:
            st.warning("Time Exit: " + str(metrics["time_exit"]))
        
        st.subheader("Visual Analysis")
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(create_pie_chart(df, selected), use_container_width=True)
        with col2:
            st.plotly_chart(create_pnl_chart(df, selected), use_container_width=True)
    
    st.markdown("---")
    st.markdown("ProTraderBot Dashboard")

if __name__ == "__main__":
    main()

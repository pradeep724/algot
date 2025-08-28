import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import glob

st.set_page_config(page_title="Real Trading Results", layout="wide")

@st.cache_data
def load_actual_results():
    """Load your actual backtest results - no fake data"""
    data = {}
    result_files = glob.glob("backtest_results_*.csv")
    
    for file_path in result_files:
        instrument = file_path.replace("backtest_results_", "").replace(".csv", "")
        
        try:
            df = pd.read_csv(file_path)
            if 'pnl' in df.columns and len(df) > 0:
                data[instrument] = df
                st.sidebar.success(f"✅ {instrument}: {len(df)} trades")
            else:
                st.sidebar.error(f"❌ {instrument}: Invalid data")
        except Exception as e:
            st.sidebar.error(f"❌ {instrument}: {e}")
    
    return data

def calculate_metrics(df):
    """Calculate real metrics from actual data"""
    if df.empty:
        return {}
    
    total_trades = len(df)
    winning_trades = len(df[df['pnl'] > 0])
    total_pnl = df['pnl'].sum()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_pnl': df['pnl'].mean(),
        'max_profit': df['pnl'].max(),
        'max_loss': df['pnl'].min()
    }

def create_pnl_chart(df, instrument):
    """Create P&L chart from actual data"""
    if df.empty:
        return go.Figure()
    
    df_sorted = df.sort_values('entry_date') if 'entry_date' in df.columns else df
    df_sorted['cumulative_pnl'] = df_sorted['pnl'].cumsum()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_sorted.index,
        y=df_sorted['cumulative_pnl'],
        mode='lines+markers',
        name=f"{instrument} Actual P&L",
        line=dict(color='green' if df_sorted['cumulative_pnl'].iloc[-1] > 0 else 'red')
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=f"{instrument} - Actual Cumulative P&L",
        xaxis_title="Trade Number",
        yaxis_title="Cumulative P&L (₹)"
    )
    
    return fig

def main():
    st.title("📊 Real Trading Results Dashboard")
    st.markdown("**Displaying YOUR actual backtest results (no fake data)**")
    
    data = load_actual_results()
    
    if not 
        st.error("❌ No backtest results found!")
        st.markdown("### Generate Results:")
        st.code("python run_backtest_enhanced.py")
        return
    
    # Portfolio overview
    st.header("Portfolio Performance")
    
    total_pnl = sum(calculate_metrics(df)['total_pnl'] for df in data.values())
    total_trades = sum(calculate_metrics(df)['total_trades'] for df in data.values())
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Trades", total_trades)
    with col2:
        st.metric("Total P&L", f"₹{total_pnl:,.0f}")
    with col3:
        st.metric("Active Instruments", len(data))
    
    # Individual results
    for instrument, df in data.items():
        with st.expander(f"{instrument} Results"):
            metrics = calculate_metrics(df)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Trades", metrics['total_trades'])
            with col2:
                st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
            with col3:
                st.metric("Total P&L", f"₹{metrics['total_pnl']:,.0f}")
            with col4:
                st.metric("Avg P&L", f"₹{metrics['avg_pnl']:.0f}")
            
            # Show chart
            st.plotly_chart(create_pnl_chart(df, instrument), use_container_width=True)
            
            # Show recent trades
            st.subheader("Recent Trades")
            st.dataframe(df.tail(10))

if __name__ == "__main__":
    main()

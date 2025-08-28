import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import yaml

# Set page config
st.set_page_config(
    page_title="ProTraderBot Multi-Index Dashboard", 
    page_icon="ðŸš€", 
    layout="wide"
)

@st.cache_data
def load_config():
    """Load your existing config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error("âŒ config.yaml not found! Please ensure your config file exists.")
        return None

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_backtest_data():
    """Load all available backtest results"""
    data = {}
    
    # Try to load data for all possible instruments
    instruments = ["NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY", "BANKEX", "NIFTYNXT50"]
    
    for instrument in instruments:
        csv_file = f"results/backtest_results_{instrument}_fixed.csv"
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                
                # Ensure required columns exist
                required_columns = ['pnl']
                if all(col in df.columns for col in required_columns):
                    # Convert date columns if they exist
                    for col in df.columns:
                        if 'date' in col.lower() and df[col].dtype == 'object':
                            try:
                                df[col] = pd.to_datetime(df[col])
                            except:
                                pass
                    
                    data[instrument] = df
                    st.sidebar.success(f"âœ… {instrument}: {len(df)} trades")
                else:
                    st.sidebar.error(f"âŒ {instrument}: Missing required columns")
            except Exception as e:
                st.sidebar.error(f"âŒ {instrument}: {str(e)}")
    
    return data

def calculate_enhanced_metrics(df):
    """Calculate comprehensive trading metrics"""
    if df.empty or 'pnl' not in df.columns:
        return {
            'total_trades': 0, 'success_trades': 0, 'failure_trades': 0,
            'success_rate': 0, 'total_pnl': 0, 'avg_pnl': 0,
            'max_profit': 0, 'max_loss': 0, 'profit_factor': 0,
            'target_hit': 0, 'sl_hit': 0, 'time_exit': 0,
            'best_month': 'N/A', 'worst_month': 'N/A',
            'consecutive_wins': 0, 'consecutive_losses': 0
        }
    
    # Clean data
    completed = df.dropna(subset=['pnl'])
    
    # Basic metrics
    success = completed[completed['pnl'] > 50]
    failure = completed[completed['pnl'] < -50]
    
    total_profit = success['pnl'].sum() if len(success) > 0 else 0
    total_loss = abs(failure['pnl'].sum()) if len(failure) > 0 else 1
    
    # Exit reasons analysis
    if 'exit_reason' in completed.columns:
        exit_counts = completed['exit_reason'].value_counts()
        target_hit = exit_counts.get('Target Hit', 0)
        sl_hit = exit_counts.get('SL Hit', 0)
        time_exit = exit_counts.get('Time Exit', 0)
    else:
        # Estimate based on P&L ranges
        target_hit = len(completed[completed['pnl'] >= 250])
        sl_hit = len(completed[completed['pnl'] <= -150])
        time_exit = len(completed) - target_hit - sl_hit
    
    # Monthly performance
    best_month = 'N/A'
    worst_month = 'N/A'
    
    if 'entry_date' in completed.columns:
        try:
            completed['month'] = pd.to_datetime(completed['entry_date']).dt.to_period('M')
            monthly_pnl = completed.groupby('month')['pnl'].sum()
            if not monthly_pnl.empty:
                best_month = str(monthly_pnl.idxmax())
                worst_month = str(monthly_pnl.idxmin())
        except:
            pass
    
    # Consecutive wins/losses
    consecutive_wins = 0
    consecutive_losses = 0
    if len(completed) > 0:
        # Simple calculation
        wins = (completed['pnl'] > 50).astype(int)
        current_win_streak = 0
        current_loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for win in wins:
            if win:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
        
        consecutive_wins = max_win_streak
        consecutive_losses = max_loss_streak
    
    return {
        'total_trades': len(df),
        'success_trades': len(success),
        'failure_trades': len(failure),
        'success_rate': (len(success) / len(completed) * 100) if len(completed) > 0 else 0,
        'total_pnl': completed['pnl'].sum(),
        'avg_pnl': completed['pnl'].mean(),
        'max_profit': completed['pnl'].max(),
        'max_loss': completed['pnl'].min(),
        'profit_factor': total_profit / total_loss if total_loss > 0 else 0,
        'target_hit': target_hit,
        'sl_hit': sl_hit,
        'time_exit': time_exit,
        'best_month': best_month,
        'worst_month': worst_month,
        'consecutive_wins': consecutive_wins,
        'consecutive_losses': consecutive_losses
    }

def create_enhanced_pnl_chart(df, instrument):
    """Create advanced P&L chart with multiple views"""
    if df.empty or 'pnl' not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No data available", x=0.5, y=0.5, showarrow=False)
        return fig
    
    completed = df.dropna(subset=['pnl']).copy()
    
    # Sort by date if available
    if 'entry_date' in completed.columns:
        completed = completed.sort_values('entry_date')
        x_axis = completed['entry_date']
        x_title = "Date"
    else:
        completed = completed.reset_index()
        x_axis = completed.index
        x_title = "Trade Number"
    
    # Calculate cumulative P&L
    completed['cumulative_pnl'] = completed['pnl'].cumsum()
    
    # Determine colors
    colors = ['green' if pnl > 0 else 'red' for pnl in completed['cumulative_pnl']]
    
    fig = go.Figure()
    
    # Add cumulative P&L line
    fig.add_trace(go.Scatter(
        x=x_axis,
        y=completed['cumulative_pnl'],
        mode='lines+markers',
        name=f"{instrument} Cumulative P&L",
        line=dict(width=3, color='blue'),
        marker=dict(size=4),
        hovertemplate=f'<b>{instrument}</b><br>' +
                      'Cumulative P&L: â‚¹%{y:,.0f}<br>' +
                      'Individual P&L: â‚¹%{customdata:,.0f}<br>' +
                      '<extra></extra>',
        customdata=completed['pnl']
    ))
    
    # Add break-even line
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="Break Even")
    
    # Add annotations for major milestones
    max_profit = completed['cumulative_pnl'].max()
    max_drawdown = completed['cumulative_pnl'].min()
    
    if max_profit > 1000:
        max_idx = completed['cumulative_pnl'].idxmax()
        fig.add_annotation(
            x=x_axis.iloc[max_idx] if hasattr(x_axis, 'iloc') else max_idx,
            y=max_profit,
            text=f"Peak: â‚¹{max_profit:,.0f}",
            showarrow=True,
            arrowhead=2
        )
    
    fig.update_layout(
        title=f"{instrument} - Enhanced P&L Analysis",
        xaxis_title=x_title,
        yaxis_title="Cumulative P&L (â‚¹)",
        hovermode='x unified'
    )
    
    return fig

def create_performance_heatmap(data):
    """Create performance heatmap across instruments"""
    if not data:
        return go.Figure()
    
    # Prepare data for heatmap
    instruments = list(data.keys())
    metrics = ['Total P&L', 'Success Rate', 'Avg P&L/Trade', 'Max Drawdown']
    
    heatmap_data = []
    for instrument in instruments:
        df = data[instrument]
        metrics_data = calculate_enhanced_metrics(df)
        
        row = [
            metrics_data['total_pnl'],
            metrics_data['success_rate'],
            metrics_data['avg_pnl'],
            metrics_data['max_loss']
        ]
        heatmap_data.append(row)
    
    # Normalize data for better visualization
    heatmap_array = pd.DataFrame(heatmap_data, index=instruments, columns=metrics)
    
    # Normalize each column to 0-1 scale
    for col in heatmap_array.columns:
        if col == 'Max Drawdown':
            # For drawdown, lower is better
            heatmap_array[col] = 1 - (heatmap_array[col] - heatmap_array[col].min()) / (heatmap_array[col].max() - heatmap_array[col].min())
        else:
            # For other metrics, higher is better
            heatmap_array[col] = (heatmap_array[col] - heatmap_array[col].min()) / (heatmap_array[col].max() - heatmap_array[col].min())
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_array.values,
        x=metrics,
        y=instruments,
        colorscale='RdYlGn',
        text=[[f"{heatmap_data[i][j]:.0f}" for j in range(len(metrics))] for i in range(len(instruments))],
        texttemplate="%{text}",
        textfont={"size": 10},
    ))
    
    fig.update_layout(
        title="Multi-Index Performance Heatmap",
        xaxis_title="Metrics",
        yaxis_title="Instruments"
    )
    
    return fig

def create_risk_return_scatter(data):
    """Create risk-return scatter plot"""
    if not data:
        return go.Figure()
    
    returns = []
    risks = []
    instruments = []
    colors = []
    
    for instrument, df in data.items():
        metrics = calculate_enhanced_metrics(df)
        
        returns.append(metrics['avg_pnl'])
        # Use standard deviation of returns as risk measure
        if not df.empty and 'pnl' in df.columns:
            risk = df['pnl'].std()
        else:
            risk = 0
        risks.append(risk)
        instruments.append(instrument)
        
        # Color based on performance
        if metrics['total_pnl'] > 1000:
            colors.append('green')
        elif metrics['total_pnl'] > -1000:
            colors.append('orange')
        else:
            colors.append('red')
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=risks,
        y=returns,
        mode='markers+text',
        text=instruments,
        textposition="top center",
        marker=dict(
            size=15,
            color=colors,
            opacity=0.7,
            line=dict(width=2, color='black')
        ),
        hovertemplate='<b>%{text}</b><br>' +
                      'Avg Return: â‚¹%{y:.0f}<br>' +
                      'Risk (Std Dev): â‚¹%{x:.0f}<br>' +
                      '<extra></extra>'
    ))
    
    fig.update_layout(
        title="Risk-Return Analysis",
        xaxis_title="Risk (Standard Deviation of P&L)",
        yaxis_title="Average Return per Trade (â‚¹)"
    )
    
    return fig

def main():
    st.title("ðŸš€ ProTraderBot Multi-Index Dashboard")
    st.markdown("**Compatible with your existing Angel One setup and strategies**")
    
    # Load config and data
    config = load_config()
    if not config:
        return
        
    data = load_backtest_data()
    
    if not data:
        st.error("âŒ No backtest data found!")
        
        st.markdown("### ðŸ“‹ Setup Instructions:")
        st.info("1. **Run your data fetcher:** `python fetch_update_data_enhanced.py`")
        st.info("2. **Run backtests:** Use your existing strategies or run `python main_enhanced.py`")
        st.info("3. **Refresh this page** once you have backtest results")
        
        with st.expander("ðŸ“ Expected Data Files"):
            expected_files = ["backtest_results_NIFTY.csv", "backtest_results_BANKNIFTY.csv", 
                            "backtest_results_SENSEX.csv", "backtest_results_FINNIFTY.csv"]
            for file in expected_files:
                if os.path.exists(file):
                    st.success(f"âœ… {file}")
                else:
                    st.error(f"âŒ {file}")
        return
    
    # Sidebar controls
    st.sidebar.header("ðŸŽ›ï¸ Dashboard Controls")
    
    # Instrument selection
    instruments = list(data.keys())
    selected = st.sidebar.selectbox("ðŸ“Š Select Analysis", ["Portfolio Overview"] + instruments)
    
    # Show BANKNIFTY improvements info
    if 'BANKNIFTY' in instruments:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ðŸ”§ BANKNIFTY Enhancements:")
        st.sidebar.success("âœ… Reduced position size")
        st.sidebar.success("âœ… Lower VIX threshold (18)")
        st.sidebar.success("âœ… Higher RSI threshold (40)")
        st.sidebar.success("âœ… Better risk/reward ratios")
        st.sidebar.success("âœ… Enhanced time filters")
    
    # Show system status
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ðŸ“Š System Status:")
    total_instruments = len(instruments)
    st.sidebar.metric("Active Instruments", total_instruments)
    
    # Calculate portfolio totals
    portfolio_pnl = sum(calculate_enhanced_metrics(df)['total_pnl'] for df in data.values())
    st.sidebar.metric("Portfolio P&L", f"â‚¹{portfolio_pnl:,.0f}")
    
    if selected == "Portfolio Overview":
        # Portfolio Overview Page
        st.header("ðŸŒŸ Multi-Index Portfolio Overview")
        
        # Key metrics row
        total_trades = sum(calculate_enhanced_metrics(df)['total_trades'] for df in data.values())
        total_success = sum(calculate_enhanced_metrics(df)['success_trades'] for df in data.values())
        total_failure = sum(calculate_enhanced_metrics(df)['failure_trades'] for df in data.values())
        
        portfolio_success_rate = (total_success / (total_success + total_failure) * 100) if (total_success + total_failure) > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("ðŸ“Š Total Trades", f"{total_trades:,}")
        with col2:
            st.metric("ðŸ“ˆ Portfolio Success Rate", f"{portfolio_success_rate:.1f}%")
        with col3:
            color = "normal" if portfolio_pnl >= 0 else "inverse"
            st.metric("ðŸ’° Total Portfolio P&L", f"â‚¹{portfolio_pnl:,.0f}", delta_color=color)
        with col4:
            st.metric("ðŸ“‹ Active Instruments", len(instruments))
        
        # Performance comparison table
        st.subheader("ðŸ“Š Performance Comparison")
        
        comparison_data = []
        for instrument, df in data.items():
            metrics = calculate_enhanced_metrics(df)
            
            # Performance status
            if metrics['total_pnl'] > 2000 and metrics['success_rate'] > 55:
                status = "ðŸŽ‰ Excellent"
            elif metrics['total_pnl'] > 0 and metrics['success_rate'] > 45:
                status = "âœ… Good"
            elif metrics['total_pnl'] > -2000:
                status = "âš ï¸ Needs Work"
            else:
                status = "âŒ Critical"
            
            comparison_data.append({
                'Instrument': instrument,
                'Trades': f"{metrics['total_trades']:,}",
                'Success Rate': f"{metrics['success_rate']:.1f}%",
                'Total P&L': f"â‚¹{metrics['total_pnl']:,.0f}",
                'Avg P&L': f"â‚¹{metrics['avg_pnl']:.0f}",
                'Best Trade': f"â‚¹{metrics['max_profit']:.0f}",
                'Worst Trade': f"â‚¹{metrics['max_loss']:.0f}",
                'Status': status
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        st.dataframe(comparison_df, use_container_width=True)
        
        # Performance analysis
        st.subheader("ðŸ“ˆ Advanced Performance Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(create_performance_heatmap(data), use_container_width=True)
        
        with col2:
            st.plotly_chart(create_risk_return_scatter(data), use_container_width=True)
        
        # Individual instrument performance
        st.subheader("ðŸ” Individual Instrument Analysis")
        
        for instrument, df in data.items():
            with st.expander(f"ðŸ“Š {instrument} Detailed Analysis", expanded=False):
                metrics = calculate_enhanced_metrics(df)
                
                # Key metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Trades", metrics['total_trades'])
                with col2:
                    st.metric("Success Rate", f"{metrics['success_rate']:.1f}%")
                with col3:
                    st.metric("P&L", f"â‚¹{metrics['total_pnl']:,.0f}")
                with col4:
                    st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
                with col5:
                    st.metric("Best Streak", metrics['consecutive_wins'])
                
                # Chart
                st.plotly_chart(create_enhanced_pnl_chart(df, instrument), use_container_width=True)
    
    else:
        # Individual instrument analysis
        df = data[selected]
        metrics = calculate_enhanced_metrics(df)
        
        st.header(f"ðŸ“Š {selected} Detailed Analysis")
        
        # Performance alert
        if selected == 'BANKNIFTY' and metrics['total_pnl'] < 0:
            st.warning(f"âš ï¸ **BANKNIFTY Performance Alert**\nCurrent P&L: â‚¹{metrics['total_pnl']:,.0f}\nEnhancements have been applied to improve performance!")
        
        # Key metrics
        st.subheader("ðŸ“ˆ Performance Metrics")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric("Total Trades", metrics['total_trades'])
        with col2:
            st.metric("Success Rate", f"{metrics['success_rate']:.1f}%")
        with col3:
            color = "normal" if metrics['total_pnl'] >= 0 else "inverse"
            st.metric("Total P&L", f"â‚¹{metrics['total_pnl']:,.0f}", delta_color=color)
        with col4:
            st.metric("Avg P&L/Trade", f"â‚¹{metrics['avg_pnl']:.0f}")
        with col5:
            st.metric("Best Trade", f"â‚¹{metrics['max_profit']:.0f}")
        with col6:
            st.metric("Worst Trade", f"â‚¹{metrics['max_loss']:.0f}")
        
        # Advanced metrics
        st.subheader("ðŸ“Š Advanced Analytics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")
        with col2:
            st.metric("Max Win Streak", metrics['consecutive_wins'])
        with col3:
            st.metric("Max Loss Streak", metrics['consecutive_losses'])
        with col4:
            drawdown_pct = (metrics['max_loss'] / 100000) * 100 if metrics['max_loss'] < 0 else 0
            st.metric("Max Drawdown", f"{drawdown_pct:.1f}%")
        
        # Exit reasons analysis
        st.subheader("ðŸŽ¯ Exit Analysis")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.success(f"ðŸŽ¯ **Target Hit**\n{metrics['target_hit']} trades\n({(metrics['target_hit']/max(metrics['total_trades'],1)*100):.1f}%)")
        with col2:
            st.error(f"ðŸ›‘ **Stop Loss Hit**\n{metrics['sl_hit']} trades\n({(metrics['sl_hit']/max(metrics['total_trades'],1)*100):.1f}%)")
        with col3:
            st.warning(f"â° **Time Exit**\n{metrics['time_exit']} trades\n({(metrics['time_exit']/max(metrics['total_trades'],1)*100):.1f}%)")
        
        # Performance chart
        st.subheader("ðŸ“ˆ P&L Analysis")
        st.plotly_chart(create_enhanced_pnl_chart(df, selected), use_container_width=True)
        
        # Recommendations
        if metrics['success_rate'] < 50 or metrics['total_pnl'] < -1000:
            st.subheader("âš ï¸ Performance Recommendations")
            
            if selected == 'BANKNIFTY':
                st.error("**BANKNIFTY Specific Issues Detected:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**âœ… Improvements Applied:**")
                    st.success("â€¢ Reduced position size to 1 lot")
                    st.success("â€¢ Lower VIX threshold (18)")
                    st.success("â€¢ Higher RSI entry threshold (40)")
                    st.success("â€¢ Better stop loss: â‚¹250")
                    st.success("â€¢ Higher targets: â‚¹450")
                    st.success("â€¢ Time filters activated")
                
                with col2:
                    st.markdown("**ðŸ”„ Additional Suggestions:**")
                    st.info("â€¢ Trade only 10:00-11:30 & 2:00-3:15")
                    st.info("â€¢ Avoid high VIX days (>18)")
                    st.info("â€¢ Use NIFTY correlation filter")
                    st.info("â€¢ Consider paper trading first")
                    st.info("â€¢ Monitor for 2 weeks before live")
            else:
                st.markdown("**General Improvement Suggestions:**")
                st.info("â€¢ Review entry criteria for better selectivity")
                st.info("â€¢ Analyze losing trades for patterns")  
                st.info("â€¢ Consider position sizing adjustments")
                st.info("â€¢ Review market regime filters")
        
        # Recent trades
        if not df.empty:
            st.subheader("ðŸ“‹ Recent Trade History")
            
            # Format for display
            display_df = df.copy()
            
            # Format numeric columns
            if 'pnl' in display_df.columns:
                display_df['P&L'] = display_df['pnl'].apply(lambda x: f"â‚¹{x:,.0f}")
            
            # Show last 20 trades
            recent_trades = display_df.tail(20)
            st.dataframe(recent_trades, use_container_width=True)
    
    # Footer
    st.markdown("---")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("ðŸ¤– **ProTraderBot Multi-Index Dashboard**")
    with col2:
        st.markdown("ðŸ“¡ **Compatible with Angel One API**")
    with col3:
        st.markdown(f"ðŸ•’ **Last Updated:** {current_time}")

if __name__ == "__main__":
    main()

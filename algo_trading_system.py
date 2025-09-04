"""
🚀 Indian Index and Options Algo Trading System - Streamlit GUI

A professional algorithmic trading platform designed specifically for Indian markets.

Features:
- Multi-index support (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX)
- 10 production-grade trading strategies
- Kelly Criterion-based risk management
- Advanced backtesting with realistic costs
- Real-time performance analytics
- Interactive strategy configuration

Author: Advanced Trading Systems
Version: 2.0
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yaml
import os
import sys
from datetime import datetime, timedelta
import time
import io

# Add project modules to path
if os.path.exists('strategies'):
    sys.path.insert(0, 'strategies')

# Import system modules
try:
    from sample_data import EnhancedSampleDataGenerator
    from enhanced_backtesting import EnhancedBacktester
    from strategy_analyzer import StrategyAnalyzer
    from enhanced_risk_management import EnhancedRiskManager
except ImportError as e:
    st.error(f"Failed to import system modules: {e}")
    st.stop()

# Configure Streamlit page
st.set_page_config(
    page_title="Indian Algo Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .success-metric {
        background-color: #d4edda;
        color: #155724;
    }
    .warning-metric {
        background-color: #fff3cd;
        color: #856404;
    }
    .danger-metric {
        background-color: #f8d7da;
        color: #721c24;
    }
    .stSelectbox > div > div > div {
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_config():
    """Load system configuration"""
    try:
        with open('enhanced_config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        st.error("Configuration file 'enhanced_config.yaml' not found!")
        st.stop()

@st.cache_resource
def initialize_system(config):
    """Initialize trading system components"""
    return {
        'generator': EnhancedSampleDataGenerator(),
        'analyzer': StrategyAnalyzer(),
        'risk_manager': EnhancedRiskManager(config)
    }

def create_performance_charts(results):
    """Create comprehensive performance visualization"""
    
    # Extract daily P&L data
    daily_pnl = pd.Series(results['daily_pnl']).sort_index()
    if daily_pnl.empty:
        return None
    
    cumulative_pnl = daily_pnl.cumsum()
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            'Cumulative P&L Over Time',
            'Daily P&L Distribution', 
            'Strategy Performance Comparison',
            'Risk Metrics Dashboard'
        ),
        specs=[[{"secondary_y": True}, {"type": "histogram"}],
               [{"type": "bar"}, {"type": "indicator"}]]
    )
    
    # 1. Cumulative P&L line chart
    fig.add_trace(
        go.Scatter(
            x=cumulative_pnl.index,
            y=cumulative_pnl.values,
            mode='lines',
            name='Cumulative P&L',
            line=dict(color='green', width=2)
        ),
        row=1, col=1
    )
    
    # 2. Daily P&L histogram
    fig.add_trace(
        go.Histogram(
            x=daily_pnl.values,
            name='Daily P&L',
            nbinsx=30,
            marker_color='lightblue'
        ),
        row=1, col=2
    )
    
    # 3. Strategy performance bar chart
    strategy_perf = results.get('strategy_performance', {})
    if strategy_perf:
        strategies = list(strategy_perf.keys())
        pnls = [strategy_perf[s].get('total_pnl', 0) for s in strategies]
        
        colors = ['green' if pnl > 0 else 'red' for pnl in pnls]
        
        fig.add_trace(
            go.Bar(
                x=strategies,
                y=pnls,
                name='Strategy P&L',
                marker_color=colors
            ),
            row=2, col=1
        )
    
    # 4. Key metrics indicator
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=results['sharpe_ratio'],
            delta={"reference": 1.0},
            title={"text": "Sharpe Ratio"},
            number={'suffix': ""},
            domain={'x': [0, 1], 'y': [0, 1]}
        ),
        row=2, col=2
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=False,
        title_text="Trading System Performance Analysis",
        title_x=0.5
    )
    
    return fig

def display_strategy_details(config):
    """Display detailed strategy information and configuration"""
    
    st.subheader("📊 Available Trading Strategies")
    
    strategies = config.get('strategies', {})
    
    # Create tabs for each strategy category
    momentum_strategies = ['volatility_breakout', 'price_action_breakout', 'options_flow_momentum']
    mean_reversion_strategies = ['rsi_mean_reversion', 'bollinger_band_reversal', 'support_resistance_bounce']
    statistical_strategies = ['statistical_arbitrage', 'bollinger_squeeze', 'implied_volatility_premium']
    trend_strategies = ['moving_average_crossover']
    
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Momentum", "🔄 Mean Reversion", "📈 Statistical", "📊 Trend Following"])
    
    def display_strategy_group(tab, strategy_list, title):
        with tab:
            st.write(f"**{title} Strategies:**")
            for strategy in strategy_list:
                if strategy in strategies:
                    config_data = strategies[strategy]
                    enabled = config_data.get('enabled', False)
                    status = "✅ Enabled" if enabled else "❌ Disabled"
                    
                    with st.expander(f"{strategy.replace('_', ' ').title()} {status}"):
                        st.write("**Configuration:**")
                        for key, value in config_data.items():
                            if key != 'enabled':
                                st.write(f"- {key}: {value}")
    
    display_strategy_group(tab1, momentum_strategies, "Momentum-Based")
    display_strategy_group(tab2, mean_reversion_strategies, "Mean Reversion")
    display_strategy_group(tab3, statistical_strategies, "Statistical")
    display_strategy_group(tab4, trend_strategies, "Trend Following")

def display_risk_management_panel(config):
    """Display risk management configuration and controls"""
    
    st.subheader("🛡️ Risk Management Configuration")
    
    risk_config = config.get('risk_management', {})
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Account Capital", 
            f"₹{risk_config.get('account_capital', 0):,}",
            help="Total trading capital available"
        )
        
        st.metric(
            "Max Risk Per Trade", 
            f"{risk_config.get('max_risk_per_trade', 0)*100:.1f}%",
            help="Maximum risk allowed per individual trade"
        )
    
    with col2:
        st.metric(
            "Max Portfolio Risk", 
            f"{risk_config.get('max_portfolio_risk', 0)*100:.1f}%",
            help="Maximum total portfolio risk exposure"
        )
        
        st.metric(
            "Max Daily Loss", 
            f"{risk_config.get('max_daily_loss', 0)*100:.1f}%",
            help="Daily loss limit as % of capital"
        )
    
    with col3:
        st.metric(
            "Max Open Positions", 
            f"{risk_config.get('max_open_positions', 0)}",
            help="Maximum number of concurrent positions"
        )
        
        st.metric(
            "Kelly Fraction Cap", 
            f"{risk_config.get('kelly_fraction_cap', 0)*100:.1f}%",
            help="Maximum Kelly Criterion position size"
        )

def run_backtest_with_progress(backtester, data_dict):
    """Run backtest with progress tracking"""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Simulate progress updates (in real implementation, you'd get actual progress from backtester)
    for i in range(100):
        progress_bar.progress(i + 1)
        if i < 20:
            status_text.text('Loading strategies...')
        elif i < 40:
            status_text.text('Processing market data...')
        elif i < 70:
            status_text.text('Generating trading signals...')
        elif i < 90:
            status_text.text('Calculating performance metrics...')
        else:
            status_text.text('Finalizing results...')
        
        time.sleep(0.01)  # Small delay for visual effect
    
    # Run actual backtest
    try:
        results = backtester.run_enhanced_backtest(data_dict)
        progress_bar.empty()
        status_text.empty()
        return results
    except Exception as e:
        st.error(f"Backtest failed: {str(e)}")
        return None

def display_trade_log(results):
    """Display detailed trade log with filtering options"""
    
    st.subheader("📋 Trade Log")
    
    trades = results.get('trades', [])
    if not trades:
        st.write("No trades executed in this backtest.")
        return
    
    # Convert trades to DataFrame for easier manipulation
    trade_data = []
    for trade in trades:
        trade_data.append({
            'Entry Time': trade.entry_time,
            'Exit Time': trade.exit_time,
            'Symbol': trade.signal.symbol,
            'Strategy': trade.signal.strategy,
            'Signal Type': trade.signal.signal_type,
            'Entry Price': trade.entry_price,
            'Exit Price': trade.exit_price,
            'P&L': trade.pnl,
            'Exit Reason': trade.exit_reason,
            'Holding Period': trade.holding_period,
            'Status': trade.status
        })
    
    df_trades = pd.DataFrame(trade_data)
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        strategy_filter = st.selectbox(
            "Filter by Strategy:",
            ['All'] + list(df_trades['Strategy'].unique())
        )
    
    with col2:
        signal_filter = st.selectbox(
            "Filter by Signal Type:",
            ['All', 'BUY', 'SELL']
        )
    
    with col3:
        status_filter = st.selectbox(
            "Filter by Status:",
            ['All', 'OPEN', 'CLOSED']
        )
    
    # Apply filters
    filtered_df = df_trades.copy()
    
    if strategy_filter != 'All':
        filtered_df = filtered_df[filtered_df['Strategy'] == strategy_filter]
    
    if signal_filter != 'All':
        filtered_df = filtered_df[filtered_df['Signal Type'] == signal_filter]
    
    if status_filter != 'All':
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]
    
    # Display filtered results
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True
    )
    
    # Summary statistics for filtered trades
    if not filtered_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        profitable_trades = len(filtered_df[filtered_df['P&L'] > 0])
        total_filtered = len(filtered_df)
        win_rate = profitable_trades / total_filtered if total_filtered > 0 else 0
        
        with col1:
            st.metric("Filtered Trades", total_filtered)
        with col2:
            st.metric("Win Rate", f"{win_rate*100:.1f}%")
        with col3:
            st.metric("Total P&L", f"₹{filtered_df['P&L'].sum():.2f}")
        with col4:
            st.metric("Avg P&L", f"₹{filtered_df['P&L'].mean():.2f}")

def main():
    """Main application function"""
    
    # Application header
    st.title("🚀 Indian Index & Options Algo Trading System")
    st.markdown("*Professional algorithmic trading platform for NSE/BSE markets*")
    
    # Load configuration
    config = load_config()
    
    # Initialize system components
    components = initialize_system(config)
    
    # Sidebar configuration
    st.sidebar.header("🔧 Trading Configuration")
    
    # Index selection
    available_indices = list(config.get('index_specific', {}).keys())
    selected_indices = st.sidebar.multiselect(
        "📈 Select Indices to Trade:",
        available_indices,
        default=['NIFTY', 'BANKNIFTY'],
        help="Choose which Indian indices to include in the analysis"
    )
    
    # Strategy selection
    strategies_config = config.get('strategies', {})
    available_strategies = list(strategies_config.keys())
    enabled_strategies = [s for s, cfg in strategies_config.items() if cfg.get('enabled', False)]
    
    selected_strategies = st.sidebar.multiselect(
        "🎯 Select Trading Strategies:",
        available_strategies,
        default=enabled_strategies,
        help="Choose which strategies to activate"
    )
    
    # Data generation parameters
    st.sidebar.subheader("📊 Data Parameters")
    data_days = st.sidebar.slider(
        "Historical Data Days:",
        min_value=100,
        max_value=1000,
        value=365,
        help="Number of days of historical data to generate"
    )
    
    # Action buttons
    st.sidebar.markdown("---")
    generate_data_btn = st.sidebar.button("🔄 Generate Sample Data", type="primary")
    run_backtest_btn = st.sidebar.button("🚀 Run Backtest", type="primary")
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "⚙️ Strategies", "🛡️ Risk Management", "📈 Results"])
    
    with tab1:
        st.header("📊 Trading Dashboard")
        
        # Display system status
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Selected Indices", len(selected_indices))
        with col2:
            st.metric("Active Strategies", len(selected_strategies))
        with col3:
            st.metric("Data Days", data_days)
        
        # Generate sample data
        if generate_data_btn or st.session_state.get('auto_generate', False):
            if not selected_indices:
                st.warning("Please select at least one index.")
            else:
                with st.spinner("🔄 Generating realistic market data..."):
                    generator = components['generator']
                    data = generator.generate_multiple_indices(
                        symbols=selected_indices, 
                        days=data_days
                    )
                    st.session_state['sample_data'] = data
                    st.session_state['data_generated'] = True
                
                st.success(f"✅ Generated {data_days} days of data for {len(selected_indices)} indices")
                
                # Display data preview
                if data:
                    st.subheader("📋 Data Preview")
                    for symbol, df in data.items():
                        with st.expander(f"{symbol} - Last 5 Days"):
                            st.dataframe(df.tail())
    
    with tab2:
        display_strategy_details(config)
    
    with tab3:
        display_risk_management_panel(config)
    
    with tab4:
        st.header("📈 Backtest Results")
        
        # Run backtest
        if run_backtest_btn:
            if 'sample_data' not in st.session_state:
                st.error("❌ Please generate sample data first!")
            elif not selected_strategies:
                st.error("❌ Please select at least one strategy!")
            else:
                # Update configuration with selected strategies
                updated_config = config.copy()
                for strategy in updated_config['strategies']:
                    updated_config['strategies'][strategy]['enabled'] = strategy in selected_strategies
                
                # Initialize backtester
                backtester = EnhancedBacktester(updated_config)
                
                # Run backtest with progress tracking
                with st.spinner("🔄 Running enhanced backtest..."):
                    results = run_backtest_with_progress(backtester, st.session_state['sample_data'])
                
                if results:
                    st.session_state['backtest_results'] = results
                    st.success("✅ Backtest completed successfully!")
                else:
                    st.error("❌ Backtest failed. Please check your configuration.")
        
        # Display results if available
        if 'backtest_results' in st.session_state:
            results = st.session_state['backtest_results']
            
            # Key metrics
            st.subheader("🎯 Key Performance Metrics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_pnl = results['total_pnl']
                pnl_color = "normal"
                if total_pnl > 0:
                    pnl_color = "normal"
                elif total_pnl < -10000:
                    pnl_color = "inverse"
                
                st.metric(
                    "Total P&L",
                    f"₹{total_pnl:,.2f}",
                    delta=f"{results['annual_return_pct']:.1f}% annual return"
                )
            
            with col2:
                st.metric(
                    "Total Trades",
                    results['total_trades'],
                    delta=f"{results['win_rate']*100:.1f}% win rate"
                )
            
            with col3:
                st.metric(
                    "Sharpe Ratio",
                    f"{results['sharpe_ratio']:.2f}",
                    help="Risk-adjusted returns measure"
                )
            
            with col4:
                st.metric(
                    "Max Drawdown",
                    f"{results['max_drawdown_pct']:.1f}%",
                    delta=f"{results['calmar_ratio']:.2f} Calmar ratio",
                    help="Maximum peak-to-trough decline"
                )
            
            # Performance charts
            st.subheader("📊 Performance Visualization")
            performance_chart = create_performance_charts(results)
            if performance_chart:
                st.plotly_chart(performance_chart, use_container_width=True)
            
            # Strategy breakdown
            st.subheader("🎯 Strategy Performance Breakdown")
            strategy_perf = results.get('strategy_performance', {})
            
            if strategy_perf:
                # Create strategy comparison table
                strategy_rows = []
                for strategy, metrics in strategy_perf.items():
                    strategy_rows.append({
                        'Strategy': strategy.replace('_', ' ').title(),
                        'Trades': metrics.get('total_trades', 0),
                        'Win Rate (%)': f"{metrics.get('win_rate', 0)*100:.1f}",
                        'Total P&L (₹)': f"{metrics.get('total_pnl', 0):,.2f}",
                        'Avg P&L/Trade (₹)': f"{metrics.get('avg_pnl_per_trade', 0):.2f}"
                    })
                
                df_strategies = pd.DataFrame(strategy_rows)
                st.dataframe(df_strategies, use_container_width=True, hide_index=True)
            
            # Detailed trade log
            display_trade_log(results)
            
            # Export results
            st.subheader("💾 Export Results")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📊 Generate Analysis Report"):
                    analyzer = components['analyzer']
                    report = analyzer.generate_analysis_report(results)
                    
                    # Create download button for report
                    st.download_button(
                        label="📥 Download Report (Markdown)",
                        data=report,
                        file_name=f"trading_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
                        mime="text/markdown"
                    )
            
            with col2:
                if st.button("📈 Export Trade Data"):
                    trades_df = pd.DataFrame([
                        {
                            'Entry Time': t.entry_time,
                            'Exit Time': t.exit_time,
                            'Symbol': t.signal.symbol,
                            'Strategy': t.signal.strategy,
                            'Signal Type': t.signal.signal_type,
                            'Entry Price': t.entry_price,
                            'Exit Price': t.exit_price,
                            'P&L': t.pnl,
                            'Exit Reason': t.exit_reason
                        } for t in results.get('trades', [])
                    ])
                    
                    csv_buffer = io.StringIO()
                    trades_df.to_csv(csv_buffer, index=False)
                    
                    st.download_button(
                        label="📥 Download Trades (CSV)",
                        data=csv_buffer.getvalue(),
                        file_name=f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>🚀 <strong>Indian Algo Trading System v2.0</strong> | Professional algorithmic trading platform</p>
            <p>⚠️ <em>For educational purposes. Past performance doesn't guarantee future results. Trade responsibly.</em></p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == '__main__':
    # Initialize session state
    if 'sample_data' not in st.session_state:
        st.session_state['sample_data'] = None
    if 'backtest_results' not in st.session_state:
        st.session_state['backtest_results'] = None
    if 'data_generated' not in st.session_state:
        st.session_state['data_generated'] = False
    
    main()

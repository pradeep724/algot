#!/usr/bin/env python3
"""
Complete Enhanced Algo Trading & Backtesting System
Production-ready application with data fetching, backtesting, and analysis
Fixed version with all type errors and iteration issues resolved
"""

import streamlit as st
import pandas as pd
import numpy as np
import yaml
import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import sys

# Configure Streamlit
st.set_page_config(
    page_title="Enhanced Algo Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import modules
try:
    from fetch_angel_data import AngelOneDataFetcher
    from enhanced_backtesting import EnhancedBacktester
    from sample_data import EnhancedSampleDataGenerator
    MODULES_AVAILABLE = True
except ImportError as e:
    st.sidebar.error(f"⚠️ Some modules missing: {e}")
    MODULES_AVAILABLE = False

# Constants
DATA_DIR = Path("historical_data")
DATA_DIR.mkdir(exist_ok=True)

def standardize_data_for_backtesting(data):
    """
    Standardize data format to match what backtesting strategies expect
    Critical: Ensures Timestamp is properly set as datetime index
    """
    
    standardized_data = {}
    
    for symbol, df in data.items():
        try:
            df_clean = df.copy()
            
            # Handle Timestamp column
            if 'Timestamp' in df_clean.columns:
                df_clean.set_index('Timestamp', inplace=True)
                print(f"✅ {symbol}: Moved Timestamp column to index")
            
            # Ensure index is datetime
            if not isinstance(df_clean.index, pd.DatetimeIndex):
                df_clean.index = pd.to_datetime(df_clean.index)
                print(f"✅ {symbol}: Converted index to datetime")
            
            # Remove timezone info
            if df_clean.index.tz is not None:
                df_clean.index = df_clean.index.tz_localize(None)
                print(f"✅ {symbol}: Removed timezone info")
            
            # Standardize column names
            column_mapping = {}
            for col in df_clean.columns:
                col_lower = col.lower()
                if col_lower == 'open' and col != 'Open':
                    column_mapping[col] = 'Open'
                elif col_lower == 'high' and col != 'High':
                    column_mapping[col] = 'High'
                elif col_lower == 'low' and col != 'Low':
                    column_mapping[col] = 'Low'
                elif col_lower == 'close' and col != 'Close':
                    column_mapping[col] = 'Close'
                elif col_lower == 'volume' and col != 'Volume':
                    column_mapping[col] = 'Volume'
            
            if column_mapping:
                df_clean.rename(columns=column_mapping, inplace=True)
                print(f"✅ {symbol}: Standardized column names")
            
            # Verify required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in df_clean.columns]
            
            if missing_columns:
                print(f"❌ {symbol}: Missing columns: {missing_columns}")
                continue
            
            # Ensure numeric data types
            for col in required_columns:
                df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            
            # Remove NaN values
            initial_rows = len(df_clean)
            df_clean.dropna(inplace=True)
            final_rows = len(df_clean)
            
            if initial_rows != final_rows:
                print(f"⚠️ {symbol}: Removed {initial_rows - final_rows} rows with NaN")
            
            # Sort by timestamp
            df_clean.sort_index(inplace=True)
            
            # Set required attributes
            df_clean.attrs['symbol'] = symbol
            df_clean.attrs['source'] = getattr(df, 'attrs', {}).get('source', 'Unknown')
            df_clean.attrs['standardized'] = True
            
            # Ensure minimum data length
            if len(df_clean) >= 50:
                standardized_data[symbol] = df_clean
                print(f"✅ {symbol}: Standardized {len(df_clean)} records")
            else:
                print(f"❌ {symbol}: Insufficient data ({len(df_clean)} records)")
                
        except Exception as e:
            print(f"❌ {symbol}: Standardization error: {e}")
            continue
    
    print(f"\n📊 Standardization Complete:")
    print(f"   Input: {len(data)} symbols")
    print(f"   Output: {len(standardized_data)} symbols")
    
    return standardized_data

@st.cache_data
def load_config():
    """Load configuration from YAML file with safety checks"""
    try:
        with open('enhanced_config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Validate config structure
        if not config:
            config = {}
        
        if 'strategies' not in config:
            config['strategies'] = {}
        
        if 'risk_management' not in config:
            config['risk_management'] = {}
        
        # Ensure strategies is a dict
        if not isinstance(config['strategies'], dict):
            config['strategies'] = {}
        
        return config
        
    except FileNotFoundError:
        st.warning("⚠️ Configuration file not found. Using default config.")
        # Return default config with proper structure
        return {
            'risk_management': {
                'account_capital': 1000000,
                'max_risk_per_trade': 0.02,
                'max_portfolio_risk': 0.05,
                'max_daily_loss': 0.03
            },
            'strategies': {
                'volatility_breakout': {
                    'enabled': True,
                    'lookback_period': 20,
                    'vol_threshold': 50.0,
                    'volume_threshold': 1.2,
                    'stop_loss_pct': 0.02,
                    'profit_target_pct': 0.03
                },
                'rsi_mean_reversion': {
                    'enabled': True,
                    'rsi_period': 14,
                    'oversold_threshold': 35.0,
                    'overbought_threshold': 65.0,
                    'stop_loss_pct': 0.02,
                    'profit_target_pct': 0.03
                }
            }
        }
    except Exception as e:
        st.error(f"❌ Error loading config: {e}")
        return {'strategies': {}, 'risk_management': {}}

def get_available_data_files():
    """Get list of available historical data files"""
    files = list(DATA_DIR.glob("*_historical.csv"))
    symbols = [f.stem.replace('_historical', '') for f in files]
    return symbols, files

def load_historical_data(symbol):
    """Load historical data from CSV file"""
    filepath = DATA_DIR / f"{symbol}_historical.csv"
    
    if filepath.exists():
        try:
            df = pd.read_csv(filepath, index_col='Timestamp', parse_dates=True)
            df.attrs['symbol'] = symbol
            df.attrs['source'] = 'CSV'
            return df
        except Exception as e:
            st.error(f"Error loading {symbol}: {e}")
            return None
    return None

def fetch_fresh_data(symbols, start_date, end_date, credentials):
    """Fetch fresh data using Angel One API"""
    if not MODULES_AVAILABLE:
        st.error("❌ Data fetching modules not available")
        return {}
    
    try:
        fetcher = AngelOneDataFetcher(
            credentials['client_id'],
            credentials['password'],
            credentials.get('totp_secret'),
            credentials.get('api_key')
        )
        
        if not fetcher.authenticate():
            st.error("❌ Authentication failed")
            return {}
        
        data = {}
        progress_bar = st.progress(0)
        
        for i, symbol in enumerate(symbols):
            st.write(f"🔍 Fetching {symbol}...")
            
            df = fetcher.fetch_and_update_historical_data(
                symbol=symbol,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if not df.empty:
                data[symbol] = df
                st.success(f"✅ {symbol}: {len(df)} records")
            else:
                st.warning(f"⚠️ No data for {symbol}")
            
            progress_bar.progress((i + 1) / len(symbols))
            time.sleep(0.5)
        
        return data
        
    except Exception as e:
        st.error(f"❌ Data fetching error: {e}")
        return {}

def create_performance_chart(df, symbol):
    """Create interactive price chart"""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=(f'{symbol} Price Chart', 'Volume')
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=symbol
        ),
        row=1, col=1
    )
    
    # Volume chart
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['Volume'],
            name='Volume',
            marker_color='lightblue'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        showlegend=False,
        xaxis_rangeslider_visible=False
    )
    
    return fig

def run_backtest(data, config):
    """Run backtest with provided data"""
    if not MODULES_AVAILABLE:
        st.error("❌ Backtesting modules not available")
        return None
    
    try:
        backtester = EnhancedBacktester(config)
        
        with st.spinner("🚀 Running backtest..."):
            results = backtester.run_enhanced_backtest(data)
        
        return results
        
    except Exception as e:
        st.error(f"❌ Backtest error: {e}")
        st.error(f"Error details: {str(e)}")
        return None

def display_backtest_results(results):
    """Display comprehensive backtest results"""
    if not results:
        return
    
    st.header("📊 Backtest Results")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trades", results.get('total_trades', 0))
    with col2:
        st.metric("Win Rate", f"{results.get('win_rate', 0)*100:.1f}%")
    with col3:
        st.metric("Total P&L", f"₹{results.get('total_pnl', 0):,.2f}")
    with col4:
        st.metric("Sharpe Ratio", f"{results.get('sharpe_ratio', 0):.2f}")
    
    # Additional metrics
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric("Max Drawdown", f"{results.get('max_drawdown_pct', 0):.1f}%")
    with col6:
        st.metric("Profit Factor", f"{results.get('profit_factor', 0):.2f}")
    with col7:
        st.metric("Avg Trade", f"₹{results.get('avg_trade_pnl', 0):.2f}")
    with col8:
        st.metric("Best Trade", f"₹{results.get('best_trade', 0):.2f}")
    
    # Performance chart
    if 'equity_curve' in results and results['equity_curve']:
        equity_data = pd.Series(results['equity_curve']).fillna(method='ffill')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=equity_data.index,
            y=equity_data.values,
            mode='lines',
            name='Equity Curve',
            line=dict(color='green', width=2)
        ))
        
        fig.update_layout(
            title="Portfolio Equity Curve",
            xaxis_title="Time",
            yaxis_title="Portfolio Value (₹)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Strategy performance breakdown
    if 'strategy_performance' in results:
        st.subheader("🎯 Strategy Performance")
        
        strategy_data = []
        for strategy, metrics in results['strategy_performance'].items():
            strategy_data.append({
                'Strategy': strategy.replace('_', ' ').title(),
                'Trades': metrics.get('total_trades', 0),
                'Win Rate (%)': f"{metrics.get('win_rate', 0)*100:.1f}",
                'P&L (₹)': f"{metrics.get('total_pnl', 0):,.2f}",
                'Avg P&L': f"₹{metrics.get('avg_pnl_per_trade', 0):.2f}",
                'Sharpe': f"{metrics.get('sharpe_ratio', 0):.2f}"
            })
        
        if strategy_data:
            df_strategies = pd.DataFrame(strategy_data)
            st.dataframe(df_strategies, use_container_width=True)
    
    # Trade log
    if 'trades' in results and results['trades']:
        st.subheader("📋 Recent Trades")
        trades_df = pd.DataFrame(results['trades'])
        if not trades_df.empty:
            recent_trades = trades_df.tail(10)
            st.dataframe(recent_trades, use_container_width=True)

def main():
    """Main application function"""
    
    st.title("📈 Enhanced Algo Trading & Backtesting System")
    st.markdown("*Complete trading system with data management, backtesting, and analysis*")
    
    # Sidebar configuration
    st.sidebar.header("🔧 Configuration")
    
    # Data source selection
    data_source = st.sidebar.radio(
        "Select Data Source",
        ["📂 Load Existing CSV Files", "🔄 Fetch Fresh Data", "🎲 Generate Sample Data"]
    )
    
    # Get available symbols
    available_symbols, _ = get_available_data_files()
    all_symbols = list(set(available_symbols + ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'SENSEX']))
    
    # Symbol selection
    selected_symbols = st.sidebar.multiselect(
        "Select Symbols",
        sorted(all_symbols),
        default=['NIFTY', 'BANKNIFTY'] if all_symbols else []
    )
    
    if not selected_symbols:
        st.error("❌ Please select at least one symbol")
        return
    
    # Date range
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime.now() - timedelta(days=365)
        )
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    # Load configuration
    config = load_config()
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Management", "🚀 Backtesting", "📈 Analysis", "⚙️ Settings"])
    
    with tab1:
        st.header("📊 Data Management")
        
        data = {}
        
        if data_source == "📂 Load Existing CSV Files":
            st.subheader("Loading Historical CSV Files")
            
            for symbol in selected_symbols:
                df = load_historical_data(symbol)
                if df is not None:
                    data[symbol] = df
                    
                    with st.expander(f"📈 {symbol} - {len(df)} records"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Records", len(df))
                        with col2:
                            st.metric("Date Range", f"{df.index.min().date()} to {df.index.max().date()}")
                        with col3:
                            st.metric("Latest Close", f"₹{df['Close'].iloc[-1]:,.2f}")
                        
                        # Show chart
                        chart = create_performance_chart(df, symbol)
                        st.plotly_chart(chart, use_container_width=True)
                else:
                    st.warning(f"⚠️ No data file found for {symbol}")
        
        elif data_source == "🔄 Fetch Fresh Data":
            st.subheader("Fetch Fresh Data from Angel One API")
            
            # Credentials input
            with st.expander("🔐 API Credentials", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    client_id = st.text_input("Client ID", type="password")
                    totp_secret = st.text_input("TOTP Secret (Optional)", type="password")
                with col2:
                    password = st.text_input("Password", type="password")
                    api_key = st.text_input("API Key", type="password")
            
            if st.button("🚀 Fetch Data", type="primary"):
                if client_id and password:
                    credentials = {
                        'client_id': client_id,
                        'password': password,
                        'totp_secret': totp_secret if totp_secret else None,
                        'api_key': api_key if api_key else None
                    }
                    
                    data = fetch_fresh_data(selected_symbols, start_date, end_date, credentials)
                    
                    if data:
                        st.success(f"✅ Successfully fetched data for {len(data)} symbols")
                        st.session_state['fetched_data'] = data
                else:
                    st.error("❌ Please provide Client ID and Password")
            
            # Show previously fetched data
            if 'fetched_data' in st.session_state:
                data = st.session_state['fetched_data']
                st.subheader("📈 Fetched Data Summary")
                for symbol, df in data.items():
                    st.write(f"**{symbol}**: {len(df)} records from {df.index.min().date()} to {df.index.max().date()}")
        
        elif data_source == "🎲 Generate Sample Data":
            st.subheader("Generate Sample Data for Testing")
            
            days = st.slider("Number of Days", 100, 1000, 365)
            
            if st.button("🎲 Generate Sample Data", type="primary"):
                if MODULES_AVAILABLE:
                    generator = EnhancedSampleDataGenerator()
                    
                    with st.spinner("Generating sample data..."):
                        data = generator.generate_multiple_indices(selected_symbols, days)
                    
                    st.success(f"✅ Generated {days} days of data for {len(selected_symbols)} symbols")
                    st.session_state['sample_data'] = data
                else:
                    st.error("❌ Sample data generator not available")
            
            # Show previously generated data
            if 'sample_data' in st.session_state:
                data = st.session_state['sample_data']
                st.subheader("📊 Generated Data Summary")
                for symbol, df in data.items():
                    st.write(f"**{symbol}**: {len(df)} records")
        
        # Store data in session state
        if data:
            st.session_state['current_data'] = data
    
    with tab2:
        st.header("🚀 Backtesting")
        
        # Get data from session state
        raw_data = st.session_state.get('current_data', {})
        
        if not raw_data:
            st.warning("⚠️ No data available. Please load or fetch data first in the Data Management tab.")
        else:
            # Standardize data
            st.subheader("📊 Data Standardization")
            
            with st.spinner("Standardizing data format..."):
                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                
                standardized_data = standardize_data_for_backtesting(raw_data)
                
                output = buffer.getvalue()
                sys.stdout = old_stdout
                
                if output:
                    with st.expander("📋 Standardization Log"):
                        st.text(output)
            
            if not standardized_data:
                st.error("❌ No valid data after standardization")
            else:
                st.success(f"✅ Standardized data for {len(standardized_data)} symbols")
                
                # Strategy configuration with safety checks
                st.subheader("🎯 Strategy Configuration")
                
                strategies = config.get('strategies', {})
                
                if not strategies or not isinstance(strategies, dict):
                    st.warning("⚠️ No strategies found in configuration")
                    st.info("Please check your enhanced_config.yaml file")
                else:
                    enabled_strategies = []
                    
                    # Safe iteration with defensive checks
                    strategy_items = list(strategies.items())
                    
                    if len(strategy_items) == 0:
                        st.warning("⚠️ No strategies available")
                    else:
                        # Create strategy checkboxes safely
                        mid_point = len(strategy_items) // 2
                        
                        col1, col2 = st.columns(2)
                        
                        # Safe iteration for first half
                        with col1:
                            for strategy_name, strategy_config in strategy_items[:mid_point]:
                                if isinstance(strategy_config, dict):
                                    enabled = st.checkbox(
                                        f"{strategy_name.replace('_', ' ').title()}",
                                        value=strategy_config.get('enabled', False),
                                        key=f"strat_{strategy_name}"
                                    )
                                    if enabled:
                                        enabled_strategies.append(strategy_name)
                        
                        # Safe iteration for second half
                        with col2:
                            if len(strategy_items) > mid_point:
                                for strategy_name, strategy_config in strategy_items[mid_point:]:
                                    if isinstance(strategy_config, dict):
                                        enabled = st.checkbox(
                                            f"{strategy_name.replace('_', ' ').title()}",
                                            value=strategy_config.get('enabled', False),
                                            key=f"strat_{strategy_name}"
                                        )
                                        if enabled:
                                            enabled_strategies.append(strategy_name)
                    
                    # Update config with enabled strategies
                    for strategy_name in strategies:
                        if isinstance(strategies[strategy_name], dict):
                            config['strategies'][strategy_name]['enabled'] = strategy_name in enabled_strategies
                    
                    # Display enabled strategies
                    if enabled_strategies:
                        st.write(f"**Enabled Strategies:** {', '.join([s.replace('_', ' ').title() for s in enabled_strategies])}")
                    else:
                        st.write("**No strategies selected**")
                    
                    # Run backtest button
                    if st.button("🚀 Run Backtest", type="primary", disabled=not enabled_strategies):
                        try:
                            results = run_backtest(standardized_data, config)
                            
                            if results and results.get('total_trades', 0) > 0:
                                st.session_state['backtest_results'] = results
                                st.success(f"✅ Backtest completed: {results['total_trades']} trades generated!")
                            else:
                                st.warning("⚠️ Backtest completed but no trades generated.")
                                
                                # Debug information
                                st.subheader("🔍 Debugging Information")
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write("**Possible Issues:**")
                                    st.write("- Strategy conditions too strict")
                                    st.write("- Insufficient data volatility")
                                    st.write("- Wrong data format")
                                    
                                with col2:
                                    st.write("**Recommendations:**")
                                    st.write("- Try relaxed parameters in Settings")
                                    st.write("- Use sample data for testing")
                                    st.write("- Check strategy configuration")
                        
                        except Exception as e:
                            st.error(f"❌ Backtest error: {e}")
                            st.error(f"Error details: {str(e)}")
                
                # Display results
                if 'backtest_results' in st.session_state:
                    display_backtest_results(st.session_state['backtest_results'])
    
    with tab3:
        st.header("📈 Analysis")
        
        results = st.session_state.get('backtest_results', {})
        
        if not results:
            st.info("📊 Run a backtest first to see analysis results")
        else:
            st.subheader("📊 Performance Analysis")
            
            # Risk metrics
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write("**Risk Metrics**")
                st.write(f"Max Drawdown: {results.get('max_drawdown_pct', 0):.1f}%")
                st.write(f"Volatility: {results.get('volatility', 0)*100:.1f}%")
                st.write(f"VaR (95%): ₹{results.get('var_95', 0):,.0f}")
                
            with col2:
                st.write("**Return Metrics**")
                st.write(f"Total Return: {results.get('total_return_pct', 0):.1f}%")
                st.write(f"Annualized Return: {results.get('annual_return_pct', 0):.1f}%")
                st.write(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
                
            with col3:
                st.write("**Trade Metrics**")
                st.write(f"Win Rate: {results.get('win_rate', 0)*100:.1f}%")
                st.write(f"Profit Factor: {results.get('profit_factor', 0):.2f}")
                st.write(f"Expectancy: ₹{results.get('expectancy', 0):.2f}")
            
            # Trade distribution
            if 'trades' in results and results['trades']:
                st.subheader("📊 Trade Distribution")
                
                trades_df = pd.DataFrame(results['trades'])
                
                if 'pnl' in trades_df.columns:
                    fig = go.Figure(data=[go.Histogram(x=trades_df['pnl'], nbinsx=20)])
                    fig.update_layout(
                        title="Trade P&L Distribution",
                        xaxis_title="P&L (₹)",
                        yaxis_title="Frequency"
                    )
                    st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
      st.header("⚙️ Settings")
      
      # Configuration editor
      st.subheader("📋 Current Configuration")
      
      # Risk Management
      with st.expander("🛡️ Risk Management Settings", expanded=True):
          risk_config = config.get('risk_management', {})
          
          new_capital = st.number_input(
              "Account Capital (₹)",
              value=int(risk_config.get('account_capital', 1000000)),
              step=100000
          )
          
          new_max_risk = st.number_input(
              "Max Risk Per Trade (%)",
              min_value=0.1,
              max_value=10.0,
              value=float(risk_config.get('max_risk_per_trade', 0.02)) * 100,
              step=0.1,
              format="%.1f"
          ) / 100
          
          config['risk_management']['account_capital'] = new_capital
          config['risk_management']['max_risk_per_trade'] = new_max_risk
      
      # Strategy Parameters - FIXED VERSION
      with st.expander("🎯 Strategy Parameters", expanded=True):
          strategies_config = config.get('strategies', {})
          
          if not strategies_config:
              st.warning("⚠️ No strategies found in configuration")
          else:
              for strategy_name, strategy_config in strategies_config.items():
                  if not isinstance(strategy_config, dict):
                      continue
                      
                  st.subheader(f"{strategy_name.replace('_', ' ').title()}")
                  
                  for param, value in strategy_config.items():
                      if param != 'enabled' and isinstance(value, (int, float)):
                          
                          # 🔧 FIXED: Dynamic min/max based on current value
                          if param.endswith('_pct'):
                              # Percentage parameters (0.001 to 0.1)
                              min_val = 0.001
                              max_val = 0.1
                              # Expand range if current value is outside
                              if value < min_val:
                                  min_val = value
                              if value > max_val:
                                  max_val = value * 2
                                  
                              new_value = st.number_input(
                                  f"{param.replace('_', ' ').title()}",
                                  min_value=min_val,
                                  max_value=max_val,
                                  value=float(value),
                                  step=0.001,
                                  format="%.3f",
                                  key=f"{strategy_name}_{param}"
                              )
                              
                          elif 'threshold' in param:
                              # 🔧 FIXED: Dynamic range for thresholds
                              if isinstance(value, float):
                                  min_val = 1.0
                                  max_val = 100.0
                                  # Expand range if needed
                                  if value < min_val:
                                      min_val = value * 0.5
                                  if value > max_val:
                                      max_val = value * 2
                                      
                                  new_value = st.number_input(
                                      f"{param.replace('_', ' ').title()}",
                                      min_value=min_val,
                                      max_value=max_val,
                                      value=float(value),
                                      step=0.1,
                                      format="%.1f",
                                      key=f"{strategy_name}_{param}"
                                  )
                              else:
                                  min_val = 1
                                  max_val = 100
                                  # Expand range if needed
                                  if value < min_val:
                                      min_val = int(value * 0.5)
                                  if value > max_val:
                                      max_val = int(value * 2)
                                      
                                  new_value = st.number_input(
                                      f"{param.replace('_', ' ').title()}",
                                      min_value=min_val,
                                      max_value=max_val,
                                      value=int(value),
                                      step=1,
                                      key=f"{strategy_name}_{param}"
                                  )
                                  
                          else:
                              # 🔧 FIXED: Dynamic range for periods and other params
                              if isinstance(value, float):
                                  min_val = 0.1
                                  max_val = 100.0
                                  # Expand range if needed
                                  if value < min_val:
                                      min_val = value * 0.5
                                  if value > max_val:
                                      max_val = value * 2
                                      
                                  new_value = st.number_input(
                                      f"{param.replace('_', ' ').title()}",
                                      min_value=min_val,
                                      max_value=max_val,
                                      value=float(value),
                                      step=0.1,
                                      key=f"{strategy_name}_{param}"
                                  )
                              else:
                                  min_val = 1
                                  max_val = 500
                                  # Expand range if needed
                                  if value < min_val:
                                      min_val = int(value * 0.5)
                                  if value > max_val:
                                      max_val = int(value * 2)
                                      
                                  new_value = st.number_input(
                                      f"{param.replace('_', ' ').title()}",
                                      min_value=min_val,
                                      max_value=max_val,
                                      value=int(value),
                                      step=1,
                                      key=f"{strategy_name}_{param}"
                                  )
                          
                          config['strategies'][strategy_name][param] = new_value
      
      # Save configuration
      if st.button("💾 Save Configuration", type="primary"):
          try:
              with open('enhanced_config.yaml', 'w') as f:
                  yaml.dump(config, f, default_flow_style=False)
              st.success("✅ Configuration saved successfully!")
          except Exception as e:
              st.error(f"❌ Failed to save configuration: {e}")
      
      # System info
      st.subheader("🔧 System Information")
      col1, col2 = st.columns(2)
      
      with col1:
          st.write("**Data Directory:**")
          st.code(str(DATA_DIR.absolute()))
          st.write(f"**Available Data Files:** {len(get_available_data_files()[0])}")
          
      with col2:
          st.write("**Modules Status:**")
          st.write(f"**Core Modules:** {'✅ Available' if MODULES_AVAILABLE else '❌ Missing'}")
          st.write(f"**Data Files:** {len(list(DATA_DIR.glob('*.csv')))}")


if __name__ == "__main__":
    main()

import os
import sys
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import your existing strategies
from strategies.debit_spreads import DebitSpreadStrategy
from strategies.long_straddle import LongStraddleStrategy
from utils.logger import log

def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

def get_active_instruments(config):
    """Get instruments but exclude NIFTYNXT50 based on analysis"""
    instruments = []
    for instrument, settings in config.get('universe', {}).items():
        if instrument == 'NIFTYNXT50':
            continue  # Skip based on poor performance
        if settings.get('active', True):
            instruments.append(instrument)
    return instruments

def load_historical_data(instrument):
    """Load your existing historical data"""
    data_paths = [
        f'data/{instrument}_historical.csv',
        f'{instrument}_historical.csv'
    ]
    
    for path in data_paths:
        if os.path.exists(path):
            df = pd.read_csv(path, index_col='Timestamp', parse_dates=True)
            return df.tail(200)  # Last 200 days
    
    log.warning(f"No data found for {instrument}")
    return pd.DataFrame()

def simulate_vix_from_data(price_data):
    """Simple VIX simulation from price volatility"""
    if len(price_data) < 20:
        return 18  # Default
        
    returns = price_data.pct_change().dropna()
    volatility = returns.rolling(20).std().iloc[-1] * np.sqrt(252)
    
    # Convert to VIX-like scale
    vix = 15 + (volatility * 100)
    return max(12, min(35, vix))  # Clamp to realistic range

def backtest_instrument(instrument, config):
    """Backtest single instrument using your actual strategies"""
    
    print(f"\n=== BACKTESTING {instrument} ===")
    os.environ['CURRENT_INSTRUMENT'] = instrument
    
    try:
        # Load historical data
        historical_data = load_historical_data(instrument)
        if historical_data.empty:
            print(f"No data for {instrument}")
            return []
        
        # Initialize your strategies
        strategies = [
            DebitSpreadStrategy(config),
            LongStraddleStrategy(config)
        ]
        
        all_trades = []
        
        for strategy in strategies:
            print(f"Running {strategy.__class__.__name__}...")
            
            # Your enhanced strategy with instrument awareness
            df = strategy._calculate_technical_indicators(historical_data.copy())
            
            in_trade = False
            entry_info = None
            
            for idx in range(50, len(df)):
                current_row = df.iloc[idx]
                current_date = df.index[idx]
                
                # Simulate live data
                simulated_vix = simulate_vix_from_data(df['Close'].iloc[:idx+1])
                live_data = {
                    'instrument': instrument,
                    'vix': {'value': simulated_vix}
                }
                
                if not in_trade:
                    # Use your enhanced strategy methods
                    signal = strategy.generate_signal(df.iloc[:idx+1], live_data)
                    
                    if signal:
                        # Get position size using your new method
                        position_info = strategy.calculate_position_size_by_performance(
                            signal, 500000, instrument
                        )
                        
                        in_trade = True
                        entry_info = {
                            'entry_date': current_date,
                            'entry_price': current_row['Close'],
                            'strategy': strategy.__class__.__name__,
                            'direction': signal.get('direction', 'neutral'),
                            'confidence': signal.get('confidence', 50),
                            'position_size': position_info['position_size'],
                            'stop_loss': position_info['stop_loss'],
                            'target': position_info.get('target', 300)
                        }
                        
                else:
                    # Check exit conditions
                    entry_price = entry_info['entry_price']
                    current_price = current_row['Close']
                    position_size = entry_info['position_size']
                    
                    # Calculate P&L
                    pnl = (current_price - entry_price) * position_size
                    
                    # Exit conditions
                    exit_triggered = False
                    exit_reason = 'Time Exit'
                    
                    if pnl >= entry_info['target']:
                        exit_triggered = True
                        exit_reason = 'Target Hit'
                    elif pnl <= -entry_info['stop_loss']:
                        exit_triggered = True
                        exit_reason = 'SL Hit'
                    elif (current_date - entry_info['entry_date']).days >= 5:
                        exit_triggered = True
                        exit_reason = 'Time Exit'
                    
                    if exit_triggered:
                        trade = {
                            'entry_date': entry_info['entry_date'],
                            'exit_date': current_date,
                            'entry_price': entry_info['entry_price'],
                            'exit_price': current_price,
                            'pnl': round(pnl, 2),
                            'direction': entry_info['direction'],
                            'strategy_type': entry_info['strategy'],
                            'exit_reason': exit_reason,
                            'spot_price': current_price,
                            'instrument': instrument,
                            'confidence': entry_info['confidence'],
                            'position_size': entry_info['position_size']
                        }
                        
                        all_trades.append(trade)
                        in_trade = False
                        entry_info = None
        
        # Save results
        if all_trades:
            df_trades = pd.DataFrame(all_trades)
            output_file = f'backtest_results_{instrument}.csv'
            df_trades.to_csv(output_file, index=False)
            
            total_pnl = df_trades['pnl'].sum()
            win_rate = (df_trades['pnl'] > 50).mean() * 100
            
            print(f"✅ {instrument}: {len(all_trades)} trades, {win_rate:.1f}% win rate, ₹{total_pnl:,.0f} P&L")
        else:
            print(f"⚠️ No trades generated for {instrument}")
        
        return all_trades
        
    except Exception as e:
        print(f"❌ Error backtesting {instrument}: {e}")
        return []
    finally:
        if 'CURRENT_INSTRUMENT' in os.environ:
            del os.environ['CURRENT_INSTRUMENT']

def main():
    """Run backtests using your actual enhanced strategies"""
    print("🚀 MULTI-INSTRUMENT BACKTESTING")
    print("Using YOUR strategies with enhanced parameters")
    print("="*50)
    
    config = load_config()
    active_instruments = get_active_instruments(config)
    
    print(f"Active instruments: {active_instruments}")
    
    results = []
    for instrument in active_instruments:
        trades = backtest_instrument(instrument, config)
        if trades:
            df = pd.DataFrame(trades)
            total_pnl = df['pnl'].sum()
            win_rate = (df['pnl'] > 50).mean() * 100
            results.append({
                'instrument': instrument,
                'trades': len(trades),
                'win_rate': win_rate,
                'total_pnl': total_pnl
            })
    
    # Summary
    print(f"\n{'='*50}")
    print("PORTFOLIO SUMMARY")
    print(f"{'='*50}")
    
    total_portfolio_pnl = sum(r['total_pnl'] for r in results)
    
    for result in results:
        status = "✅" if result['total_pnl'] > 0 else "❌"
        print(f"{status} {result['instrument']:<12}: "
              f"{result['trades']:>3} trades | "
              f"{result['win_rate']:>5.1f}% | "
              f"₹{result['total_pnl']:>8,.0f}")
    
    print(f"\n💰 TOTAL PORTFOLIO P&L: ₹{total_portfolio_pnl:,.0f}")
    
    if total_portfolio_pnl > 0:
        print("🎉 Portfolio is PROFITABLE with enhanced strategies!")
    else:
        print("⚠️ Portfolio needs further optimization")

if __name__ == "__main__":
    main()

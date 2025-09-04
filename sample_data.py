#!/usr/bin/env python3
"""
Enhanced Sample Data Generator for Indian Index/Options Algo Trading System

Generates realistic OHLCV data for Indian market indices with:
- Market-specific volatility patterns
- Gap behavior simulation  
- Volume correlation with price movements
- Volatility clustering
- Mean reversion tendencies
- Holiday/weekend exclusion

Supported Indices: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, SENSEX

Author: Indian Algo Trading System
Version: 2.0
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import warnings
warnings.filterwarnings('ignore')

class EnhancedSampleDataGenerator:
    """
    Professional-grade sample data generator for Indian market indices
    """
    
    def __init__(self):
        """Initialize with realistic parameters for Indian indices"""
        
        # Market-specific parameters based on historical behavior
        self.index_params = {
            'NIFTY': {
                'base_price': 24000,        # Current approximate level
                'daily_vol': 0.012,         # 1.2% daily volatility
                'trend_bias': 0.0002,       # Slight positive bias
                'volume_base': 1000000,     # Base volume
                'gap_probability': 0.05,    # 5% chance of gaps
                'sector_correlation': 0.8   # High correlation with other indices
            },
            'BANKNIFTY': {
                'base_price': 52000,
                'daily_vol': 0.018,         # Higher volatility than NIFTY
                'trend_bias': 0.0001,
                'volume_base': 800000,
                'gap_probability': 0.08,    # More gaps due to banking news
                'sector_correlation': 0.7
            },
            'FINNIFTY': {
                'base_price': 23000,
                'daily_vol': 0.015,
                'trend_bias': 0.0001,
                'volume_base': 500000,
                'gap_probability': 0.06,
                'sector_correlation': 0.75
            },
            'MIDCPNIFTY': {
                'base_price': 12000,
                'daily_vol': 0.020,         # Highest volatility (mid-cap effect)
                'trend_bias': 0.0003,       # Higher growth potential
                'volume_base': 300000,
                'gap_probability': 0.10,    # Most gaps
                'sector_correlation': 0.6
            },
            'SENSEX': {
                'base_price': 81000,
                'daily_vol': 0.011,         # Slightly lower volatility
                'trend_bias': 0.0002,
                'volume_base': 2000000,     # Highest volume
                'gap_probability': 0.04,    # Fewer gaps (more liquid)
                'sector_correlation': 0.85  # High correlation with NIFTY
            }
        }
    
    def generate_sample_data(self, symbol='NIFTY', days=365, start_date=None):
        """
        Generate realistic OHLCV data for a specific index
        
        Args:
            symbol: Index symbol ('NIFTY', 'BANKNIFTY', etc.)
            days: Number of trading days to generate
            start_date: Start date (if None, uses days ago from today)
        
        Returns:
            pandas.DataFrame with OHLCV data and metadata
        """
        
        if start_date is None:
            start_date = datetime.now() - timedelta(days=int(days * 1.4))  # Account for weekends
        
        # Generate only trading days (Monday-Friday)
        dates = []
        current_date = start_date
        while len(dates) < days:
            # Skip weekends
            if current_date.weekday() < 5:
                # Skip major Indian holidays (simplified)
                if not self._is_indian_holiday(current_date):
                    dates.append(current_date)
            current_date += timedelta(days=1)
        
        n_days = len(dates)
        params = self.index_params.get(symbol, self.index_params['NIFTY'])
        
        # Initialize price tracking
        current_price = params['base_price']
        prices = np.zeros(n_days)
        opens = np.zeros(n_days)
        highs = np.zeros(n_days)
        lows = np.zeros(n_days)
        closes = np.zeros(n_days)
        volumes = np.zeros(n_days)
        
        # Generate realistic price series
        for i in range(n_days):
            
            # Volatility clustering (realistic market behavior)
            vol_adjustment = 1.0
            if i > 10:
                # Recent volatility affects current volatility
                recent_returns = np.diff(prices[max(0, i-10):i])
                if len(recent_returns) > 0 and prices[i-1] > 0:
                    recent_vol = np.std(recent_returns) / prices[i-1]
                    vol_adjustment = 1 + (recent_vol - params['daily_vol']) * 2
                    vol_adjustment = np.clip(vol_adjustment, 0.5, 2.0)
            
            daily_vol = params['daily_vol'] * vol_adjustment
            
            # Mean reversion component (prices tend to revert to base)
            mean_rev = -0.1 * (current_price - params['base_price']) / params['base_price']
            
            # Generate daily return with trend, mean reversion, and randomness
            daily_return = params['trend_bias'] + mean_rev + np.random.normal(0, daily_vol)
            
            # Occasional shock events (news, events)
            if random.random() < 0.02:  # 2% chance of shock
                shock_magnitude = np.random.normal(0, daily_vol * 3)
                daily_return += shock_magnitude
            
            # Apply return to price
            current_price *= (1 + daily_return)
            prices[i] = current_price
            
            # Generate opening price (may have gaps)
            if i > 0 and random.random() < params['gap_probability']:
                # Generate gap (common in Indian markets due to overnight news)
                gap = np.random.normal(0, daily_vol * 0.5)
                open_price = closes[i-1] * (1 + gap)
            else:
                # Normal opening (close to previous close)
                open_price = closes[i-1] if i > 0 else current_price
            
            # Generate intraday high and low
            intraday_vol = daily_vol * 0.6  # Intraday volatility is typically lower
            high_low_range = current_price * intraday_vol * np.random.uniform(1.2, 2.5)
            
            # Calculate high and low based on open and close
            day_high = max(open_price, current_price) + high_low_range * np.random.uniform(0.3, 0.7)
            day_low = min(open_price, current_price) - high_low_range * np.random.uniform(0.3, 0.7)
            
            # Ensure OHLC relationships are maintained
            day_high = max(day_high, open_price, current_price)
            day_low = min(day_low, open_price, current_price)
            
            # Store OHLC values
            opens[i] = open_price
            highs[i] = day_high
            lows[i] = day_low
            closes[i] = current_price
            
            # Generate volume (correlated with price movement and volatility)
            base_vol = params['volume_base']
            
            # Volume increases with volatility
            vol_factor = 1 + abs(daily_return) * 20
            
            # Random time-of-day factor
            time_factor = np.random.uniform(0.7, 1.5)
            
            # Occasional volume spikes (news, events)
            spike_factor = np.random.uniform(2, 5) if random.random() < 0.05 else 1
            
            volumes[i] = int(base_vol * vol_factor * time_factor * spike_factor)
        
        # Create DataFrame with proper index
        df = pd.DataFrame({
            'Open': opens,
            'High': highs,
            'Low': lows,
            'Close': closes,
            'Volume': volumes.astype(int)
        }, index=pd.DatetimeIndex(dates, name='Timestamp'))
        
        # Add metadata attributes
        df.attrs['symbol'] = symbol
        df.attrs['generated'] = True
        df.attrs['generation_date'] = datetime.now()
        df.attrs['params'] = params
        df.attrs['data_source'] = 'EnhancedSampleDataGenerator'
        
        return df
    
    def generate_multiple_indices(self, symbols=None, days=365, start_date=None):
        """
        Generate data for multiple indices with cross-correlation
        
        Args:
            symbols: List of symbols to generate (None for all)
            days: Number of trading days
            start_date: Start date
        
        Returns:
            Dict of DataFrames keyed by symbol
        """
        
        if symbols is None:
            symbols = list(self.index_params.keys())
        
        data = {}
        base_returns = None  # For correlation simulation
        
        for i, symbol in enumerate(symbols):
            print(f"📊 Generating {days} days of data for {symbol}...")
            
            # Generate individual data
            df = self.generate_sample_data(symbol, days, start_date)
            
            # Add some cross-correlation with other indices (simplified)
            if i > 0 and base_returns is not None:
                correlation = self.index_params[symbol]['sector_correlation']
                df_returns = df['Close'].pct_change().dropna()
                
                # Apply correlation adjustment (simplified)
                min_len = min(len(base_returns), len(df_returns))
                if min_len > 10:
                    corr_adjustment = base_returns.iloc[-min_len:] * correlation * 0.1
                    df_returns.iloc[-min_len:] += corr_adjustment
                    
                    # Reconstruct prices from adjusted returns
                    df['Close'].iloc[1:] = df['Close'].iloc[0] * (1 + df_returns).cumprod()
                    
                    # Adjust OHLC accordingly
                    for j in range(1, len(df)):
                        adjustment_ratio = df['Close'].iloc[j] / df['Close'].iloc[j]
                        df.loc[df.index[j], ['Open', 'High', 'Low']] *= adjustment_ratio
            
            if base_returns is None:
                base_returns = df['Close'].pct_change().dropna()
            
            data[symbol] = df
        
        print(f"✅ Generated data for {len(symbols)} indices")
        return data
    
    def _is_indian_holiday(self, date):
        """
        Simple check for major Indian holidays (simplified implementation)
        
        Args:
            date: datetime object
            
        Returns:
            bool: True if it's a holiday
        """
        
        # Major Indian holidays (approximate dates)
        holidays = [
            (1, 26),   # Republic Day
            (8, 15),   # Independence Day
            (10, 2),   # Gandhi Jayanti
        ]
        
        # Diwali and other lunar holidays would need a more complex calculation
        for month, day in holidays:
            if date.month == month and date.day == day:
                return True
        
        return False
    
    def add_market_regimes(self, df, regime_periods=None):
        """
        Add market regime information to the data
        
        Args:
            df: DataFrame to modify
            regime_periods: List of (start_idx, end_idx, regime) tuples
        
        Returns:
            Modified DataFrame with regime column
        """
        
        df = df.copy()
        df['Market_Regime'] = 'normal'
        
        if regime_periods:
            for start_idx, end_idx, regime in regime_periods:
                df.iloc[start_idx:end_idx, df.columns.get_loc('Market_Regime')] = regime
        else:
            # Auto-detect regimes based on volatility
            returns = df['Close'].pct_change()
            vol = returns.rolling(window=20).std() * np.sqrt(252)
            
            vol_75 = vol.quantile(0.75)
            vol_25 = vol.quantile(0.25)
            
            df.loc[vol > vol_75, 'Market_Regime'] = 'high_volatility'
            df.loc[vol < vol_25, 'Market_Regime'] = 'low_volatility'
        
        return df
    
    def save_to_csv(self, data, filename_prefix="sample_data"):
        """
        Save generated data to CSV files
        
        Args:
            data: Single DataFrame or dict of DataFrames
            filename_prefix: Prefix for filenames
        """
        
        if isinstance(data, dict):
            # Multiple indices
            for symbol, df in data.items():
                filename = f"{filename_prefix}_{symbol}_{datetime.now().strftime('%Y%m%d')}.csv"
                df.to_csv(filename)
                print(f"💾 Saved {symbol} data to {filename}")
        else:
            # Single DataFrame
            symbol = data.attrs.get('symbol', 'UNKNOWN')
            filename = f"{filename_prefix}_{symbol}_{datetime.now().strftime('%Y%m%d')}.csv"
            data.to_csv(filename)
            print(f"💾 Saved data to {filename}")

def main():
    """Example usage of the sample data generator"""
    
    print("🚀 Indian Market Sample Data Generator")
    print("="*50)
    
    # Initialize generator
    generator = EnhancedSampleDataGenerator()
    
    # Example 1: Generate single index data
    print("\n📊 Generating NIFTY data...")
    nifty_data = generator.generate_sample_data('NIFTY', days=252)  # 1 year
    print(f"Generated {len(nifty_data)} days of NIFTY data")
    print(f"Price range: ₹{nifty_data['Close'].min():.2f} - ₹{nifty_data['Close'].max():.2f}")
    print(f"Average volume: {nifty_data['Volume'].mean():,.0f}")
    
    # Example 2: Generate multiple indices
    print(f"\n📈 Generating multi-index portfolio data...")
    portfolio_data = generator.generate_multiple_indices(
        symbols=['NIFTY', 'BANKNIFTY', 'FINNIFTY'],
        days=100
    )
    
    # Example 3: Add market regimes
    print(f"\n🎯 Adding market regime analysis...")
    nifty_with_regimes = generator.add_market_regimes(nifty_data)
    regime_counts = nifty_with_regimes['Market_Regime'].value_counts()
    print("Market regime distribution:")
    for regime, count in regime_counts.items():
        print(f"  {regime}: {count} days ({count/len(nifty_with_regimes)*100:.1f}%)")
    
    # Example 4: Save data
    print(f"\n💾 Saving generated data...")
    generator.save_to_csv(portfolio_data, "indian_indices")
    
    print(f"\n✅ Sample data generation complete!")
    print(f"Use this data with your backtesting system:")
    print(f"  from sample_data import EnhancedSampleDataGenerator")
    print(f"  generator = EnhancedSampleDataGenerator()")
    print(f"  data = generator.generate_sample_data('NIFTY', 365)")

if __name__ == "__main__":
    main()

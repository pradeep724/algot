from backtesting import TradingSignal
import numpy as np
import pandas as pd

class SupportResistanceBounceStrategy:
    def __init__(self, config):
        self.name = "support_resistance_bounce"
        self.config = config.get('support_resistance_bounce', {})
        self.lookback = self.config.get('lookback', 50)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.03)
        self.max_holding_period = self.config.get('max_holding_period', 7)

    def calculate_support_resistance(self, df):
        """Calculate dynamic support and resistance levels using pivot points"""
        df = df.copy()
        pivots_high = []
        pivots_low = []
        window = 5
        
        # Find pivot highs and lows
        for i in range(window, len(df) - window):
            # Pivot high: price is higher than surrounding prices
            if (all(df['High'][i] >= df['High'][i - j] for j in range(1, window + 1)) and 
                all(df['High'][i] >= df['High'][i + j] for j in range(1, window + 1))):
                pivots_high.append((i, df['High'][i]))
            
            # Pivot low: price is lower than surrounding prices
            if (all(df['Low'][i] <= df['Low'][i - j] for j in range(1, window + 1)) and 
                all(df['Low'][i] <= df['Low'][i + j] for j in range(1, window + 1))):
                pivots_low.append((i, df['Low'][i]))
        
        # Initialize support and resistance columns
        df['Support'] = pd.Series([np.nan]*len(df))
        df['Resistance'] = pd.Series([np.nan]*len(df))
        
        # Mark pivot points
        for idx, val in pivots_high:
            df.at[df.index[idx], 'Resistance'] = val
        for idx, val in pivots_low:
            df.at[df.index[idx], 'Support'] = val
        
        # Forward fill support and backward fill resistance for current levels
        df['Support'].fillna(method='ffill', inplace=True)
        df['Resistance'].fillna(method='bfill', inplace=True)
        
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < self.lookback:
            return None
        
        df = self.calculate_support_resistance(df)
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Define conditions
        near_support = abs(current['Close'] - current['Support']) <= current['Close'] * 0.01
        near_resistance = abs(current['Resistance'] - current['Close']) <= current['Close'] * 0.01
        volume_surge = current['Volume'] > df['Volume'].rolling(window=20).mean().iloc[-1] * 1.1
        
        # SUPPORT BOUNCE (BUY SIGNAL)
        if near_support and volume_surge and current['Close'] > prev['Close']:
            entry = current['Close']
            target = min(entry * (1 + self.profit_target_pct), current['Resistance'])
            stop = entry * (1 - self.stop_loss_pct)
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            
            if rr >= 1.0:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='BUY',
                    strength=0.75,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=0.7,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Support bounce, near {current['Support']:.2f}"
                )
        
        # RESISTANCE BOUNCE (SELL SIGNAL)
        elif near_resistance and volume_surge and current['Close'] < prev['Close']:
            entry = current['Close']
            target = max(entry * (1 - self.profit_target_pct), current['Support'])
            stop = entry * (1 + self.stop_loss_pct)
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            
            if rr >= 1.0:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='SELL',
                    strength=0.75,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=0.7,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Resistance bounce, near {current['Resistance']:.2f}"
                )
        
        return None


from backtesting import TradingSignal
import numpy as np

class PriceActionBreakoutStrategy:
    def __init__(self, config):
        self.name = "price_action_breakout"
        self.config = config.get('price_action_breakout', {})
        self.lookback = self.config.get('lookback', 15)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.04)
        self.max_holding_period = self.config.get('max_holding_period', 5)

    def calculate_indicators(self, df):
        """Calculate price action indicators and pattern recognition"""
        df = df.copy()
        
        # Breakout levels
        df['Highest_High'] = df['High'].rolling(window=self.lookback).max()
        df['Lowest_Low'] = df['Low'].rolling(window=self.lookback).min()
        
        # Price action components
        df['Prev_Close'] = df['Close'].shift(1)
        df['Prev_High'] = df['High'].shift(1)  
        df['Prev_Low'] = df['Low'].shift(1)
        df['Range'] = df['High'] - df['Low']
        df['Body'] = abs(df['Close'] - df['Open'])
        df['Upper_Wick'] = df['High'] - df[['Close', 'Open']].max(axis=1)
        df['Lower_Wick'] = df[['Close', 'Open']].min(axis=1) - df['Low']
        
        # Candlestick patterns
        df['Is_Bullish'] = df['Close'] > df['Open']
        df['Is_Bearish'] = df['Close'] < df['Open']
        df['Body_Size_Ratio'] = df['Body'] / df['Range']
        
        # Engulfing patterns
        df['Bullish_Engulfing'] = ((df['Is_Bullish']) & 
                                   (df['Prev_Close'] < df['Open']) &
                                   (df['Close'] > df['Prev_High']) &
                                   (df['Open'] < df['Prev_Low']))
        
        df['Bearish_Engulfing'] = ((df['Is_Bearish']) & 
                                   (df['Prev_Close'] > df['Open']) &
                                   (df['Close'] < df['Prev_Low']) &
                                   (df['Open'] > df['Prev_High']))
        
        # Momentum indicators
        df['Close_Above_HH'] = df['Close'] > df['Highest_High'].shift(1)
        df['Close_Below_LL'] = df['Close'] < df['Lowest_Low'].shift(1)
        
        # Volume analysis
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < self.lookback + 5:
            return None
        
        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        previous = df_with_indicators.iloc[-2]
        
        # Breakout conditions
        upward_breakout = current['Close_Above_HH']
        downward_breakout = current['Close_Below_LL']
        
        # Volume confirmation
        strong_volume = current['Volume_Ratio'] >= 1.2
        
        # Price action confirmation
        strong_bullish_candle = (current['Is_Bullish'] and 
                                current['Body_Size_Ratio'] > 0.6 and
                                current['Close'] > previous['Close'])
        
        strong_bearish_candle = (current['Is_Bearish'] and 
                                current['Body_Size_Ratio'] > 0.6 and
                                current['Close'] < previous['Close'])
        
        # Pattern confirmation
        bullish_pattern = (current['Bullish_Engulfing'] or 
                          strong_bullish_candle)
        
        bearish_pattern = (current['Bearish_Engulfing'] or 
                          strong_bearish_candle)

        # UPWARD BREAKOUT (BUY SIGNAL)
        if upward_breakout and strong_volume and bullish_pattern:
            entry = current['Close']
            target = entry * (1 + self.profit_target_pct)
            stop = max(entry * (1 - self.stop_loss_pct), previous['Highest_High'])
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            
            # Calculate confidence based on breakout strength
            breakout_strength = (current['Close'] - previous['Highest_High']) / previous['Highest_High']
            confidence = min(0.85, 0.6 + breakout_strength * 10)
            
            if rr >= 1.0:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='BUY',
                    strength=0.8,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Upward breakout above {previous['Highest_High']:.2f}, Vol: {current['Volume_Ratio']:.1f}x"
                )

        # DOWNWARD BREAKOUT (SELL SIGNAL)
        elif downward_breakout and strong_volume and bearish_pattern:
            entry = current['Close']
            target = entry * (1 - self.profit_target_pct)
            stop = min(entry * (1 + self.stop_loss_pct), previous['Lowest_Low'])
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            
            # Calculate confidence based on breakdown strength
            breakdown_strength = (previous['Lowest_Low'] - current['Close']) / previous['Lowest_Low']
            confidence = min(0.85, 0.6 + breakdown_strength * 10)
            
            if rr >= 1.0:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='SELL',
                    strength=0.8,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Downward breakout below {previous['Lowest_Low']:.2f}, Vol: {current['Volume_Ratio']:.1f}x"
                )
        
        return None


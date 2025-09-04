from backtesting import TradingSignal
import numpy as np

class OptionsFlowMomentumStrategy:
    def __init__(self, config):
        self.name = "options_flow_momentum"
        self.config = config.get('options_flow_momentum', {})
        self.volume_threshold = self.config.get('volume_threshold', 2.0)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.025)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.035)
        self.max_holding_period = self.config.get('max_holding_period', 3)

    def calculate_indicators(self, df):
        df = df.copy()
        df['Volume_MA_5'] = df['Volume'].rolling(window=5).mean()
        df['Volume_MA_20'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA_20']
        df['Volume_Momentum'] = df['Volume_MA_5'] / df['Volume_MA_20']
        df['Price_Change'] = df['Close'].pct_change()
        df['Price_Momentum_3'] = df['Close'].pct_change(3)
        df['Price_Momentum_5'] = df['Close'].pct_change(5)
        df['Momentum_Acceleration'] = df['Price_Momentum_3'] - df['Price_Momentum_5']
        df['RS_Index'] = df['Close'] / df['Close'].rolling(window=20).mean()
        df['ATR'] = df['High'].combine(df['Low'], max) - df['Low'].combine(df['High'], min)
        df['ATR'] = df['ATR'].rolling(window=14).mean()
        df['Volatility'] = df['Price_Change'].rolling(window=10).std() * np.sqrt(252)
        df['Vol_Ratio'] = df['Volatility'] / df['Volatility'].rolling(window=20).mean()
        df['Higher_High'] = (df['High'] > df['High'].shift(1)) & (df['High'].shift(1) > df['High'].shift(2))
        df['Lower_Low'] = (df['Low'] < df['Low'].shift(1)) & (df['Low'].shift(1) < df['Low'].shift(2))
        df['Gap_Up'] = df['Open'] > df['Close'].shift(1) * 1.005
        df['Gap_Down'] = df['Open'] < df['Close'].shift(1) * 0.995
        return df

    def generate_signal(self, df, regime_info):
      if len(df) < 30:
        return None
    
      df = self.calculate_indicators(df)
      current = df.iloc[-1]
    
      # Define conditions
      strong_volume = current['Volume_Ratio'] >= self.volume_threshold
      accelerating_volume = current['Volume_Momentum'] > 1.1
      strong_upward_momentum = current['Price_Momentum_3'] > 0.01 and current['Momentum_Acceleration'] > 0
      strong_downward_momentum = current['Price_Momentum_3'] < -0.01 and current['Momentum_Acceleration'] < 0
      outperforming = current['RS_Index'] > 1.02
      underperforming = current['RS_Index'] < 0.98
      vol_expanding = current['Vol_Ratio'] > 1.1
      bullish_pattern = current['Higher_High'] or current['Gap_Up']
      bearish_pattern = current['Lower_Low'] or current['Gap_Down']

      # BULLISH SIGNAL
      if (strong_volume and accelerating_volume and strong_upward_momentum and 
        outperforming and vol_expanding and bullish_pattern):
        
        entry = current['Close']
        target = entry * (1 + self.profit_target_pct)
        stop = entry * (1 - self.stop_loss_pct)
        risk = entry - stop
        reward = target - entry
        rr = reward / risk if risk > 0 else 0
        momentum_strength = (current['Volume_Ratio'] + current['Vol_Ratio'] + abs(current['Price_Momentum_3']) * 20) / 3
        confidence = min(0.9, 0.6 + momentum_strength / 5)
        
        if rr >= 1.0:
            return TradingSignal(
                timestamp=current.name,
                symbol=df.attrs.get('symbol', 'UNKNOWN'),
                strategy=self.name,
                signal_type='BUY',
                strength=min(0.9, 0.7 + momentum_strength / 10),
                entry_price=entry,
                target_price=target,
                stop_loss=stop,
                position_size=1,
                expected_pnl=self.profit_target_pct,
                risk_reward_ratio=rr,
                confidence=confidence,
                market_regime=regime_info.get('regime', 'normal'),
                reasons=f"Strong bullish momentum, Vol: {current['Volume_Ratio']:.1f}x, Mom: {current['Price_Momentum_3']*100:.1f}%"
            )
    
      # BEARISH SIGNAL        
      elif (strong_volume and accelerating_volume and strong_downward_momentum and 
          underperforming and vol_expanding and bearish_pattern):
        
        entry = current['Close']
        target = entry * (1 - self.profit_target_pct)
        stop = entry * (1 + self.stop_loss_pct)
        risk = stop - entry
        reward = entry - target
        rr = reward / risk if risk > 0 else 0
        momentum_strength = (current['Volume_Ratio'] + current['Vol_Ratio'] + abs(current['Price_Momentum_3']) * 20) / 3
        confidence = min(0.9, 0.6 + momentum_strength / 5)
        
        if rr >= 1.0:
            return TradingSignal(
                timestamp=current.name,
                symbol=df.attrs.get('symbol', 'UNKNOWN'),
                strategy=self.name,
                signal_type='SELL',
                strength=min(0.9, 0.7 + momentum_strength / 10),
                entry_price=entry,
                target_price=target,
                stop_loss=stop,
                position_size=1,
                expected_pnl=self.profit_target_pct,
                risk_reward_ratio=rr,
                confidence=confidence,
                market_regime=regime_info.get('regime', 'normal'),
                reasons=f"Strong bearish momentum, Vol: {current['Volume_Ratio']:.1f}x, Mom: {current['Price_Momentum_3']*100:.1f}%"
            )
    
      return None



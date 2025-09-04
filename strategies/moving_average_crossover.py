from backtesting import TradingSignal
import numpy as np

class MovingAverageCrossoverStrategy:
    def __init__(self, config):
        self.name = "moving_average_crossover"
        self.config = config.get('moving_average_crossover', {})
        self.short_ma = self.config.get('short_ma', 10)
        self.long_ma = self.config.get('long_ma', 20)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.03)
        self.max_holding_period = self.config.get('max_holding_period', 5)

    def calculate_indicators(self, df):
        df = df.copy()
        df['MA_short'] = df['Close'].rolling(window=self.short_ma).mean()
        df['MA_long'] = df['Close'].rolling(window=self.long_ma).mean()
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < max(self.short_ma, self.long_ma) + 10:
            return None
        
        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        previous = df_with_indicators.iloc[-2]
        
        # Detect crossovers
        bullish_crossover = (current['MA_short'] > current['MA_long'] and 
                           previous['MA_short'] <= previous['MA_long'])
        bearish_crossover = (current['MA_short'] < current['MA_long'] and 
                           previous['MA_short'] >= previous['MA_long'])
        
        volume_confirmation = current['Volume'] > current['Volume_MA'] * 1.2
        price_above_long_ma = current['Close'] > current['MA_long']

        # BULLISH CROSSOVER SIGNAL
        if bullish_crossover and volume_confirmation and price_above_long_ma:
            entry_price = current['Close']
            target_price = entry_price * (1 + self.profit_target_pct)
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            risk = entry_price - stop_loss
            reward = target_price - entry_price
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            if risk_reward_ratio >= 1.2:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='BUY',
                    strength=0.7,
                    entry_price=entry_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=risk_reward_ratio,
                    confidence=0.75,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Bullish MA crossover with volume confirmation, RR: {risk_reward_ratio:.2f}"
                )

        # BEARISH CROSSOVER SIGNAL
        elif bearish_crossover and volume_confirmation and not price_above_long_ma:
            entry_price = current['Close']
            target_price = entry_price * (1 - self.profit_target_pct)
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            risk = stop_loss - entry_price
            reward = entry_price - target_price
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            if risk_reward_ratio >= 1.2:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='SELL',
                    strength=0.7,
                    entry_price=entry_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=risk_reward_ratio,
                    confidence=0.75,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Bearish MA crossover with volume confirmation, RR: {risk_reward_ratio:.2f}"
                )
        
        return None

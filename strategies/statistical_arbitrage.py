from backtesting import TradingSignal
import numpy as np

class StatisticalArbitrageStrategy:
    def __init__(self, config):
        self.name = "statistical_arbitrage"
        self.config = config.get('statistical_arbitrage', {})
        self.lookback_period = self.config.get('lookback_period', 50)
        self.entry_zscore = self.config.get('entry_zscore', 2.0)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.015)
        self.max_holding_period = self.config.get('max_holding_period', 3)

    def calculate_indicators(self, df):
        df = df.copy()
        df['Price_Mean'] = df['Close'].rolling(window=self.lookback_period).mean()
        df['Price_Std'] = df['Close'].rolling(window=self.lookback_period).std()
        df['Z_Score'] = (df['Close'] - df['Price_Mean']) / df['Price_Std']
        df['Returns'] = df['Close'].pct_change()
        df['Returns_Mean'] = df['Returns'].rolling(window=self.lookback_period).mean()
        df['Returns_Std'] = df['Returns'].rolling(window=self.lookback_period).std()
        df['Returns_Z_Score'] = (df['Returns'] - df['Returns_Mean']) / df['Returns_Std']
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        df['BB_Std'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * 2)
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Z_Score'] = (df['Volume'] - df['Volume_MA']) / df['Volume'].rolling(window=20).std()
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < self.lookback_period + 20:
            return None
        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        extreme_high = current['Z_Score'] >= self.entry_zscore
        extreme_low = current['Z_Score'] <= -self.entry_zscore
        volume_confirmation = current['Volume_Z_Score'] > 0.5
        below_bb_lower = current['Close'] < current['BB_Lower']
        above_bb_upper = current['Close'] > current['BB_Upper']

        if extreme_high and volume_confirmation and above_bb_upper:
            entry = current['Close']
            target = max(entry * (1 - 0.03), current['Price_Mean'])
            stop = entry * (1 + self.stop_loss_pct)
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            if rr >= 1.2:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='SELL',
                    strength=0.7,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=0.03,
                    risk_reward_ratio=rr,
                    confidence=0.7,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Statistical arb SHORT, Z:{current['Z_Score']:.2f}"
                )
        elif extreme_low and volume_confirmation and below_bb_lower:
            entry = current['Close']
            target = min(entry * (1 + 0.03), current['Price_Mean'])
            stop = entry * (1 - self.stop_loss_pct)
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            if rr >= 1.2:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='BUY',
                    strength=0.7,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=0.03,
                    risk_reward_ratio=rr,
                    confidence=0.7,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Statistical arb LONG, Z:{current['Z_Score']:.2f}"
                )
        return None

from backtesting import TradingSignal
import numpy as np

class BollingerSqueezeStrategy:
    def __init__(self, config):
        self.name = "bollinger_squeeze"
        self.config = config.get('bollinger_squeeze', {})
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std = self.config.get('bb_std', 2.0)
        self.squeeze_threshold = self.config.get('squeeze_threshold', 0.05)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.035)
        self.max_holding_days = self.config.get('max_holding_days', 10)

    def calculate_indicators(self, df):
        df = df.copy()
        df['BB_Middle'] = df['Close'].rolling(window=self.bb_period).mean()
        df['BB_Std'] = df['Close'].rolling(window=self.bb_period).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * self.bb_std)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * self.bb_std)
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        df['ATR'] = df['High'].sub(df['Low']).rolling(window=14).mean()
        df['KC_Upper'] = df['BB_Middle'] + (df['ATR'] * 1.5)
        df['KC_Lower'] = df['BB_Middle'] - (df['ATR'] * 1.5)
        df['True_Squeeze'] = (df['BB_Upper'] < df['KC_Upper']) & (df['BB_Lower'] > df['KC_Lower'])
        df['Momentum'] = df['Close'] - df['Close'].shift(12)
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        df['Percent_B'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < self.bb_period + 20:
            return None
        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        previous = df_with_indicators.iloc[-2]
        was_in_squeeze = previous['True_Squeeze']
        squeeze_ending = was_in_squeeze and not current['True_Squeeze']
        bb_width_percentile = (df_with_indicators['BB_Width'].tail(50).rank(pct=True).iloc[-1]) * 100
        low_volatility = bb_width_percentile <= 20
        upside_breakout = current['Close'] > current['BB_Upper']
        downside_breakout = current['Close'] < current['BB_Lower']
        volume_confirmation = current['Volume_Ratio'] >= 1.2
        momentum_bullish = current['Momentum'] > 0
        momentum_bearish = current['Momentum'] < 0

        if (squeeze_ending or low_volatility) and upside_breakout and volume_confirmation and momentum_bullish:
            entry = current['Close']
            target = entry * (1 + self.profit_target_pct)
            stop = max(entry * (1 - self.stop_loss_pct), current['BB_Middle'])
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            confidence = 0.8 if was_in_squeeze else 0.6
            strength = min(0.9, 0.6 + (current['Volume_Ratio'] - 1.2) / 3)
            if rr >= 1.0:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='BUY',
                    strength=strength,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"BB squeeze upside breakout, Width: {bb_width_percentile:.0f}%ile, Momentum: {current['Momentum']:.2f}"
                )
        elif (squeeze_ending or low_volatility) and downside_breakout and volume_confirmation and momentum_bearish:
            entry = current['Close']
            target = entry * (1 - self.profit_target_pct)
            stop = min(entry * (1 + self.stop_loss_pct), current['BB_Middle'])
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            confidence = 0.8 if was_in_squeeze else 0.6
            strength = min(0.9, 0.6 + (current['Volume_Ratio'] - 1.2) / 3)
            if rr >= 1.0:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='SELL',
                    strength=strength,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"BB squeeze downside breakout, Width: {bb_width_percentile:.0f}%ile, Momentum: {current['Momentum']:.2f}"
                )
        return None

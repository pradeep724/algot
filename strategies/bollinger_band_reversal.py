from backtesting import TradingSignal
import numpy as np

class BollingerBandReversalStrategy:
    def __init__(self, config):
        self.name = "bollinger_band_reversal"
        self.config = config.get('bollinger_band_reversal', {})
        self.period = self.config.get('period', 20)
        self.std_dev = self.config.get('std_dev', 2.0)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.025)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.03)
        self.max_holding_period = self.config.get('max_holding_period', 5)

    def calculate_indicators(self, df):
        df = df.copy()
        df['BB_Middle'] = df['Close'].rolling(window=self.period).mean()
        df['BB_Std'] = df['Close'].rolling(window=self.period).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * self.std_dev)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * self.std_dev)
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        df['Percent_B'] = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
        df['RSI'] = self.calculate_rsi(df['Close'])
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        df['Above_Upper'] = df['Close'] > df['BB_Upper']
        df['Below_Lower'] = df['Close'] < df['BB_Lower']
        return df

    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def generate_signal(self, df, regime_info):
        if len(df) < self.period + 20:
            return None
        
        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        previous = df_with_indicators.iloc[-2]
        
        # Bollinger Band reversal conditions
        bullish_reversal = (previous['Below_Lower'] and not current['Below_Lower'] and 
                           current['Close'] > previous['Close'] and current['RSI'] < 50)
        bearish_reversal = (previous['Above_Upper'] and not current['Above_Upper'] and 
                           current['Close'] < previous['Close'] and current['RSI'] > 50)
        
        # Volume confirmation
        volume_confirmation = current['Volume_Ratio'] >= 1.1
        
        # BB width percentile (avoid trading in very tight bands)
        bb_width_percentile = (df_with_indicators['BB_Width'].tail(50).rank(pct=True).iloc[-1]) * 100
        suitable_width = bb_width_percentile > 30

        # BULLISH REVERSAL (Buy after touching lower band)
        if bullish_reversal and volume_confirmation and suitable_width:
            entry = current['Close']
            target = min(entry * (1 + self.profit_target_pct), current['BB_Middle'])
            stop = entry * (1 - self.stop_loss_pct)
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            
            # Distance from band affects confidence
            distance_from_band = abs(current['Percent_B'] - 0) if current['Percent_B'] < 0.2 else 0.2
            confidence = min(0.85, 0.5 + distance_from_band * 2)
            
            if rr >= 0.8:
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
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"BB lower band reversal, %B: {current['Percent_B']:.2f}, RSI: {current['RSI']:.1f}"
                )
        
        # BEARISH REVERSAL (Sell after touching upper band)
        elif bearish_reversal and volume_confirmation and suitable_width:
            entry = current['Close']
            target = max(entry * (1 - self.profit_target_pct), current['BB_Middle'])
            stop = entry * (1 + self.stop_loss_pct)
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            
            # Distance from band affects confidence
            distance_from_band = abs(current['Percent_B'] - 1) if current['Percent_B'] > 0.8 else 0.2
            confidence = min(0.85, 0.5 + distance_from_band * 2)
            
            if rr >= 0.8:
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
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"BB upper band reversal, %B: {current['Percent_B']:.2f}, RSI: {current['RSI']:.1f}"
                )
        
        return None


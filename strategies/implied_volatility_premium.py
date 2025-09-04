from backtesting import TradingSignal
import numpy as np

class ImpliedVolatilityPremiumStrategy:
    def __init__(self, config):
        self.name = "implied_volatility_premium"
        self.config = config.get('implied_volatility_premium', {})
        self.threshold = self.config.get('threshold', 60)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.profit_target_pct = self.config.get('profit_target_pct', 0.035)
        self.max_holding_period = self.config.get('max_holding_period', 5)

    def calculate_indicators(self, df):
        df = df.copy()
        df['Returns'] = df['Close'].pct_change()
        df['HV_10'] = df['Returns'].rolling(window=10).std() * np.sqrt(252) * 100
        df['HV_20'] = df['Returns'].rolling(window=20).std() * np.sqrt(252) * 100
        df['HV_30'] = df['Returns'].rolling(window=30).std() * np.sqrt(252) * 100
        df['HV_Percentile_50'] = df['HV_20'].rolling(window=50).rank(pct=True) * 100
        df['Vol_Term_Structure'] = df['HV_10'] - df['HV_30']
        df['Vol_of_Vol'] = df['HV_20'].rolling(window=10).std()
        df['ATR'] = df['High'].combine(df['Low'], max) - df['Low'].combine(df['High'], min)
        df['ATR'] = df['ATR'].rolling(window=14).mean()
        df['ATR_Percentile'] = df['ATR'].rolling(window=50).rank(pct=True) * 100
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        df['Daily_Range'] = (df['High'] - df['Low']) / df['Close']
        df['Range_Percentile'] = df['Daily_Range'].rolling(window=50).rank(pct=True) * 100
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        df['BB_Std'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * 2)
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        df['RSI'] = self.calculate_rsi(df['Close'])
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
        if len(df) < 50:
            return None
        
        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        previous = df_with_indicators.iloc[-2]
        
        # High volatility conditions (for SELL signals)
        high_vol_condition = (current['HV_Percentile_50'] >= self.threshold and 
                             current['ATR_Percentile'] >= self.threshold)
        vol_mean_reversion = (current['HV_20'] > current['HV_30'] * 1.2 and 
                             current['Vol_Term_Structure'] > 0)
        volume_confirmation = current['Volume_Ratio'] >= 1.2
        range_expansion = current['Range_Percentile'] >= 70
        near_upper_band = current['Close'] > current['BB_Upper'] * 0.98
        near_lower_band = current['Close'] < current['BB_Lower'] * 1.02

        # HIGH IV PREMIUM SELL SIGNAL
        if (high_vol_condition and vol_mean_reversion and volume_confirmation and 
            range_expansion and (current['RSI'] > 70 or near_upper_band)):
            
            entry = current['Close']
            target = entry * (1 - self.profit_target_pct * 0.8)
            stop = entry * (1 + self.stop_loss_pct * 1.2)
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            vol_premium = (current['HV_Percentile_50'] - 50) / 50
            confidence = min(0.85, 0.6 + vol_premium / 2)
            
            if rr >= 0.8:
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
                    expected_pnl=self.profit_target_pct * 0.8,
                    risk_reward_ratio=rr,
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"High IV premium sell, HV%ile: {current['HV_Percentile_50']:.0f}%, Vol ratio: {current['Volume_Ratio']:.2f}"
                )
        
        # Low volatility conditions (for BUY signals)
        low_vol_condition = (current['HV_Percentile_50'] <= 30 and 
                            current['ATR_Percentile'] <= 40)
        vol_expansion_signs = (current['Vol_of_Vol'] > previous['Vol_of_Vol'] and 
                              current['BB_Width'] < previous['BB_Width'] * 1.1)
        
        # LOW IV EXPANSION BUY SIGNAL
        if (low_vol_condition and vol_expansion_signs and volume_confirmation and 
            (current['RSI'] < 35 and near_lower_band)):
            
            entry = current['Close']
            target = entry * (1 + self.profit_target_pct)
            stop = entry * (1 - self.stop_loss_pct)
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            confidence = 0.65
            
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
                    expected_pnl=self.profit_target_pct,
                    risk_reward_ratio=rr,
                    confidence=confidence,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Low IV expansion setup, HV%ile: {current['HV_Percentile_50']:.0f}%, Vol of Vol: {current['Vol_of_Vol']:.3f}"
                )
        
        return None

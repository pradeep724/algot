from strategies.base_strategy import BaseStrategy
from utils.logger import log
import pandas as pd

class ProtectiveStraddleStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies']['event_risk_high']

    def generate(self, historical_data, live_data):
        """
        Research-based protective straddle for high volatility/event risk:
        - Enter when VIX > 25 (high uncertainty)
        - Profit from large moves in either direction
        - Used for earnings, events, market stress
        """
        try:
            if len(historical_data) < 30:
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]

            # 1. HIGH VOLATILITY THRESHOLD (Research: VIX > 25 for straddles)
            vix = live_data.get('vix', {}).get('value', 15)
            if vix < self.params['vix_threshold']:
                return None

            # 2. VOLATILITY SPIKE DETECTION (Research: Recent VIX expansion)
            if not self._detect_volatility_spike(historical_data, vix):
                return None

            # 3. RSI NOT AT EXTREMES (Research: Avoid oversold/overbought)
            if latest['rsi'] < self.params['rsi_lower'] or latest['rsi'] > self.params['rsi_upper']:
                return None

            # 4. ATR EXPANSION (Research: Price volatility increasing)
            if not self._confirm_atr_expansion(df):
                return None

            return {
                'direction': 'protective',
                'strategy_type': 'ProtectiveStraddle',
                'confidence': self._calculate_confidence(df, latest, vix),
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'max_dte': self.params['max_dte'],
                'min_dte': self.params['min_dte']
            }

        except Exception as e:
            log.error(f"Error in ProtectiveStraddleStrategy: {e}")
            return None

    def _detect_volatility_spike(self, historical_data, current_vix):
        """Research: Detect recent volatility expansion"""
        # Simplified - in practice, track VIX history
        return current_vix > 25

    def _confirm_atr_expansion(self, df):
        """Research: Confirm price volatility is expanding"""
        recent_atr = df['atr'].tail(5).mean()
        longer_atr = df['atr'].tail(20).mean()
        return recent_atr > longer_atr * 1.3

    def _calculate_confidence(self, df, latest, vix):
        confidence = 70
        
        # Higher VIX = higher confidence for straddles
        if vix > 30:
            confidence += 15
        elif vix > 27:
            confidence += 10
            
        # ATR expansion bonus
        atr_ratio = latest['atr'] / df['atr'].tail(20).mean()
        if atr_ratio > 1.5:
            confidence += 10
            
        return min(90, confidence)

    def calculate_position_size(self, signal, account_value):
        # Conservative sizing for high-risk strategies
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade'] * 0.6
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 20000))  # Higher premium cost

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }

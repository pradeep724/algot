from strategies.base_strategy import BaseStrategy
from utils.logger import log

class ShortStraddleStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies']['volatility_crush']

    def generate(self, historical_data, live_data):
        """
        Research-based short straddle for volatility crush:
        - Enter when VIX > 30 expecting mean reversion
        - Profit from volatility decline and time decay
        - High risk/reward strategy
        """
        try:
            if len(historical_data) < 30:
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]

            # 1. HIGH VIX FOR CRUSH (Research: VIX > 30 often mean reverts)
            vix = live_data.get('vix', {}).get('value', 15)
            if vix < self.params['vix_threshold']:
                return None

            # 2. RSI NEUTRAL (Research: Avoid directional bias)
            if latest['rsi'] < self.params['rsi_lower'] or latest['rsi'] > self.params['rsi_upper']:
                return None

            # 3. SHORT-TERM SETUP (Research: 7 DTE optimal for vol crush)
            # This would be checked during execution

            # 4. MARKET NOT TRENDING STRONGLY (Research: Range-bound preferred)
            if not self._confirm_range_bound(df, latest):
                return None

            return {
                'direction': 'short_vol',
                'strategy_type': 'ShortStraddle',
                'confidence': self._calculate_confidence(df, latest, vix),
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'max_dte': self.params['max_dte']
            }

        except Exception as e:
            log.error(f"Error in ShortStraddleStrategy: {e}")
            return None

    def _confirm_range_bound(self, df, latest):
        """Confirm market is range-bound (good for short straddles)"""
        # Similar to iron condor logic but more permissive
        sma_20 = latest['sma_20']
        sma_50 = latest['sma_50']
        price = latest['Close']
        
        ma_avg = (sma_20 + sma_50) / 2
        return abs(price - ma_avg) / ma_avg < 0.04  # Within 4% of MA average

    def _calculate_confidence(self, df, latest, vix):
        confidence = 60  # Base confidence for high-risk strategy
        
        # Extreme VIX bonus (higher chance of mean reversion)
        if vix > 35:
            confidence += 20
        elif vix > 32:
            confidence += 15
            
        return min(85, confidence)

    def calculate_position_size(self, signal, account_value):
        # Very conservative sizing for naked short strategies
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade'] * 0.3
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 30000))  # High margin requirement

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }

from strategies.base_strategy import BaseStrategy
from utils.logger import log

class LongOptionsStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies']['trending_low_vol']

    def generate(self, historical_data, live_data):
        """
        Research-based long options strategy:
        - Buy options in low IV environments during trends
        - Target strong momentum with RSI 50-70 range
        - Avoid vol expansion (buy when vol is cheap)
        """
        try:
            if len(historical_data) < 50:
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]

            # 1. TREND IDENTIFICATION (Research: Clear trend required)
            if latest['Close'] > latest['sma_20'] > latest['sma_50']:
                direction = 'bullish'
            elif latest['Close'] < latest['sma_20'] < latest['sma_50']:
                direction = 'bearish'
            else:
                return None

            # 2. RSI MOMENTUM (Research: 50-70 for bullish, 30-50 for bearish)
            rsi_threshold = self.params['rsi_entry_threshold']
            if direction == 'bullish':
                if latest['rsi'] < 50 or latest['rsi'] > rsi_threshold:
                    return None
            else:  # bearish
                if latest['rsi'] > 50 or latest['rsi'] < (100 - rsi_threshold):
                    return None

            # 3. LOW VOLATILITY ENVIRONMENT (Research: Buy options when IV low)
            vix = live_data.get('vix', {}).get('value', 20)
            if vix > 20:  # Want low vol to buy options cheap
                return None

            # 4. VOLUME CONFIRMATION (Research: Above average but not excessive)
            volume_ratio = latest['Volume'] / latest['volume_avg']
            if volume_ratio < 1.1 or volume_ratio > 3.0:
                return None

            # 5. TREND PERSISTENCE CHECK (Research: Recent 5-day trend alignment)
            if not self._check_trend_persistence(df, direction):
                return None

            return {
                'direction': direction,
                'strategy_type': 'LongOptions',
                'confidence': self._calculate_confidence(df, latest, vix),
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'max_dte': self.params['max_dte'],
                'min_dte': self.params['min_dte']
            }

        except Exception as e:
            log.error(f"Error in LongOptionsStrategy: {e}")
            return None

    def _check_trend_persistence(self, df, direction):
        """Research: Check if trend has been consistent recently"""
        recent_closes = df['Close'].tail(5)
        if direction == 'bullish':
            return (recent_closes.iloc[-1] > recent_closes.iloc[0]) and (recent_closes.diff().sum() > 0)
        else:
            return (recent_closes.iloc[-1] < recent_closes.iloc[0]) and (recent_closes.diff().sum() < 0)

    def _calculate_confidence(self, df, latest, vix):
        """Research-based confidence for long options"""
        confidence = 60
        
        # Low VIX bonus (cheaper options)
        if vix < 15:
            confidence += 15
        elif vix < 18:
            confidence += 10
            
        # Trend momentum bonus
        price_change = (latest['Close'] - df['Close'].iloc[-5]) / df['Close'].iloc[-5]
        if abs(price_change) > 0.02:  # 2% move in 5 days
            confidence += 10
            
        return min(85, confidence)

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 8000))  # Higher premium for long options

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }

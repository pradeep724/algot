from strategies.base_strategy import BaseStrategy
from utils.logger import log

class LongOptionsStrategy(BaseStrategy):
    def generate(self, data, live_data):
        df = self._calculate_technical_indicators(data.copy())
        latest = df.iloc[-1]

        # Condition for trending market
        if latest['Close'] > latest['sma_20'] > latest['sma_50']:
            direction = 'bullish'
        elif latest['Close'] < latest['sma_20'] < latest['sma_50']:
            direction = 'bearish'
        else:
            return None

        # RSI filter stronger for entries
        rsi_thresh = self.config['strategies']['long_options']['rsi_entry_threshold']
        if direction == 'bullish' and latest['rsi'] < rsi_thresh:
            return None
        if direction == 'bearish' and latest['rsi'] > (100 - rsi_thresh):
            return None

        # Volatility check (low vol preferred)
        vix = live_data.get('vix', {}).get('value', 20)
        if vix > 22:
            return None

        signal = {
            'direction': direction,
            'confidence': 70,
            'type': 'long_option',
            'entry_price': latest['Close'],
            'timestamp': latest.name
        }
        log.info(f"LongOptionsStrategy generated signal: {signal}")
        return signal

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 10000))
        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }



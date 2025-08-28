from strategies.base_strategy import BaseStrategy
from utils.logger import log

class IronCondorStrategy(BaseStrategy):
    def generate(self, data, live_data):
        df = self._calculate_technical_indicators(data.copy())
        latest = df.iloc[-1]

        # Check for neutral RSI range
        if latest['rsi'] < 35 or latest['rsi'] > 65:
            return None

        # Volatility check - moderate to high vol preferred
        vix = live_data.get('vix', {}).get('value', 15)
        if vix < 20:
            return None

        signal = {
            'direction': 'neutral',
            'confidence': 75,
            'type': 'iron_condor',
            'entry_price': latest['Close'],
            'timestamp': latest.name
        }
        log.info(f"IronCondorStrategy generated signal: {signal}")
        return signal

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 10000))  # Adjust 10000 as per avg contract price
        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }

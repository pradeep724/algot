from strategies.base_strategy import BaseStrategy
from utils.logger import log

class ProtectiveStraddleStrategy(BaseStrategy):
    def generate(self, data, live_data):
        # Generally prefer to stay flat or protective straddles in high-risk events
        vix = live_data.get('vix', {}).get('value', 15)
        if vix > 25:
            signal = {
                'direction': 'flat',
                'confidence': 90,
                'type': 'protective_straddle',
                'timestamp': pd.Timestamp.now()
            }
            log.info(f"ProtectiveStraddleStrategy activated: {signal}")
            return signal
        return None

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 10000))
        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }

from strategies.base_strategy import BaseStrategy
from utils.logger import log

class DebitSpreadStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies']['trending_high_vol']

    def generate(self, historical_data, live_data):
        try:
            if len(historical_data) < 50:
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]

            if latest['Close'] > latest['sma_20'] > latest['sma_50']:
                direction = 'bullish'
            elif latest['Close'] < latest['sma_20'] < latest['sma_50']:
                direction = 'bearish'
            else:
                return None

            if direction == 'bullish' and latest['rsi'] < self.params['rsi_entry_threshold']:
                return None
            if direction == 'bearish' and latest['rsi'] > (100 - self.params['rsi_entry_threshold']):
                return None

            if latest['Volume'] < latest['volume_avg'] * 1.2:
                return None

            vix = live_data.get('vix', {}).get('value', 0)
            if vix < 18:
                return None

            return {
                'direction': direction,
                'strategy_type': 'DebitSpreads',
                'confidence': 75,
                'spot_price': latest['Close'],
                'entry_time': latest.name
            }

        except Exception as e:
            log.error(f"Error generating debit spreads signal: {e}")
            return None

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal['confidence'] / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 10000))

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots,
            'confidence_adjusted': True
        }

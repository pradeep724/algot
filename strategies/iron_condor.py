from strategies.base_strategy import BaseStrategy
from utils.logger import log

class IronCondorStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        # Use default values if config missing
        self.params = config['strategies'].get('range_low_vol', {
            'rsi_upper': 70,
            'rsi_lower': 30, 
            'wing_width': 100,
            'max_dte': 14
        })

    def generate(self, historical_data, live_data):
        """Simplified iron condor - very permissive for testing"""
        try:
            if len(historical_data) < 20:
                log.debug("Not enough data for iron condor")
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]
            
            log.debug(f"Iron Condor check - RSI: {latest['rsi']:.1f}, Close: {latest['Close']:.2f}")

            # SIMPLIFIED CONDITIONS - Very permissive
            
            # 1. RSI in reasonable range (very wide)
            if latest['rsi'] < 20 or latest['rsi'] > 80:
                log.debug(f"RSI {latest['rsi']:.1f} outside 20-80 range")
                return None

            # 2. VIX check (very permissive)
            vix = live_data.get('vix', {}).get('value', 18)
            if vix > 25:  # Only avoid very high vol
                log.debug(f"VIX {vix} too high for iron condor")
                return None

            # 3. Volume check (handle division by zero)
            volume_avg = df['Volume'].tail(20).mean()
            if volume_avg == 0 or pd.isna(volume_avg):
                log.debug("Volume average is 0 or NaN, skipping volume check")
            else:
                volume_ratio = latest['Volume'] / volume_avg
                if volume_ratio > 5.0:  # Only avoid extreme volume spikes
                    log.debug(f"Volume ratio {volume_ratio:.1f} too high")
                    return None

            log.info(f"✅ Iron Condor signal generated - RSI: {latest['rsi']:.1f}, VIX: {vix}")
            
            return {
                'direction': 'neutral',
                'strategy_type': 'IronCondor',
                'confidence': 70,
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'wing_width': self.params.get('wing_width', 100),
                'max_dte': self.params.get('max_dte', 14)
            }

        except Exception as e:
            log.error(f"Error in IronCondorStrategy: {e}")
            return None

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 12000))

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }

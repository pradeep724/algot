from strategies.base_strategy import BaseStrategy
from utils.logger import log
import pandas as pd

class IronCondorStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies'].get('range_low_vol', {
            'rsi_upper': 65,
            'rsi_lower': 35, 
            'wing_width': 100,
            'max_dte': 14
        })

    def generate(self, historical_data, live_data):
        """
        Professional Iron Condor Strategy:
        - Optimal for low volatility, range-bound markets
        - Profit from time decay and low price movement
        - Enter when market shows sideways consolidation
        """
        try:
            if len(historical_data) < 50:
                log.debug("Insufficient data for iron condor analysis")
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]
            
            # Professional Iron Condor Entry Criteria
            
            # 1. VOLATILITY ENVIRONMENT (Professional: VIX 12-20 optimal)
            vix = live_data.get('vix', {}).get('value', 18)
            if vix < 10 or vix > 22:
                log.debug(f"VIX {vix:.1f} outside optimal range 10-22 for Iron Condor")
                return None

            # 2. RANGE-BOUND MARKET CONFIRMATION
            if not self._confirm_ranging_market(df, latest):
                log.debug("Market not in ranging condition")
                return None

            # 3. RSI IN NEUTRAL ZONE (Professional: 35-65 range)
            rsi_lower = self.params.get('rsi_lower', 35)
            rsi_upper = self.params.get('rsi_upper', 65)
            
            if latest['rsi'] < rsi_lower or latest['rsi'] > rsi_upper:
                log.debug(f"RSI {latest['rsi']:.1f} outside neutral zone {rsi_lower}-{rsi_upper}")
                return None

            # 4. VOLUME PROFILE (Avoid high volume breakouts)
            if not self._validate_volume_profile(df, latest):
                log.debug("Volume profile not suitable for Iron Condor")
                return None

            # 5. PRICE POSITION IN RECENT RANGE
            if not self._validate_price_position(df, latest):
                log.debug("Price position not optimal for Iron Condor")
                return None

            # 6. MOVING AVERAGE CONVERGENCE (Professional filter)
            if not self._check_ma_convergence(df, latest):
                log.debug("Moving averages not converged enough")
                return None

            confidence = self._calculate_professional_confidence(df, latest, vix)
            
            log.info(f"✅ Iron Condor signal - RSI: {latest['rsi']:.1f}, VIX: {vix:.1f}, Confidence: {confidence}%")
            
            return {
                'direction': 'neutral',
                'strategy_type': 'IronCondor',
                'confidence': confidence,
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'wing_width': self.params.get('wing_width', 100),
                'max_dte': self.params.get('max_dte', 14),
                'expected_range': self._calculate_expected_range(df, latest, vix)
            }

        except Exception as e:
            log.error(f"Error in professional IronCondorStrategy: {e}")
            return None

    def _confirm_ranging_market(self, df, latest):
        """Professional ranging market confirmation"""
        try:
            # 1. Moving average alignment (should be close)
            sma_20 = latest['sma_20']
            sma_50 = latest['sma_50']
            
            ma_divergence = abs(sma_20 - sma_50) / latest['Close']
            if ma_divergence > 0.025:  # 2.5% divergence max
                return False

            # 2. Recent price range analysis
            lookback = 20
            recent_high = df['High'].tail(lookback).max()
            recent_low = df['Low'].tail(lookback).min()
            range_pct = (recent_high - recent_low) / latest['Close']
            
            # Range should be reasonable but not too tight
            if range_pct < 0.02 or range_pct > 0.08:  # 2-8% range
                return False

            # 3. Price within middle 60% of recent range
            current_position = (latest['Close'] - recent_low) / (recent_high - recent_low)
            if current_position < 0.25 or current_position > 0.75:
                return False

            return True
            
        except Exception as e:
            log.error(f"Error confirming ranging market: {e}")
            return False

    def _validate_volume_profile(self, df, latest):
        """Professional volume validation with robust error handling"""
        try:
            current_volume = latest['Volume']
            
            # Calculate volume average with error handling
            volume_series = df['Volume'].tail(20)
            volume_series = volume_series.replace(0, pd.NA).dropna()
            
            if len(volume_series) < 10:
                log.debug("Insufficient volume data")
                return True  # Allow if we can't determine volume profile
                
            avg_volume = volume_series.mean()
            
            if pd.isna(avg_volume) or avg_volume <= 0:
                log.debug("Invalid average volume, allowing trade")
                return True
                
            volume_ratio = current_volume / avg_volume
            
            # Iron Condors prefer normal to slightly below average volume
            if volume_ratio > 2.5:  # Avoid volume spikes (potential breakouts)
                log.debug(f"Volume ratio {volume_ratio:.1f} too high for Iron Condor")
                return False
                
            return True
            
        except Exception as e:
            log.error(f"Error validating volume profile: {e}")
            return True  # Default to allowing trade if volume check fails

    def _validate_price_position(self, df, latest):
        """Validate price position for Iron Condor setup"""
        try:
            # Price shouldn't be at recent extremes
            lookback = 15
            recent_high = df['High'].tail(lookback).max()
            recent_low = df['Low'].tail(lookback).min()
            
            # Current price position in recent range
            price_percentile = (latest['Close'] - recent_low) / (recent_high - recent_low)
            
            # Prefer price in middle 50% of recent range
            if 0.25 <= price_percentile <= 0.75:
                return True
                
            log.debug(f"Price at {price_percentile:.2f} percentile of recent range")
            return False
            
        except Exception as e:
            log.error(f"Error validating price position: {e}")
            return True

    def _check_ma_convergence(self, df, latest):
        """Check moving average convergence for ranging market"""
        try:
            sma_20 = latest['sma_20']
            sma_50 = latest['sma_50']
            current_price = latest['Close']
            
            # All should be relatively close (within 3% of each other)
            values = [sma_20, sma_50, current_price]
            max_val = max(values)
            min_val = min(values)
            
            convergence_ratio = (max_val - min_val) / current_price
            
            return convergence_ratio < 0.03  # Within 3%
            
        except Exception as e:
            log.error(f"Error checking MA convergence: {e}")
            return True

    def _calculate_expected_range(self, df, latest, vix):
        """Calculate expected price range for the trade duration"""
        try:
            # Use ATR and VIX to estimate expected range
            daily_move = latest['atr']
            days_to_expiry = self.params.get('max_dte', 14)
            
            # Expected range based on volatility
            expected_daily_move = daily_move * (vix / 20)  # Adjust for VIX
            expected_range = expected_daily_move * (days_to_expiry ** 0.5)  # Square root of time
            
            return {
                'upper_bound': latest['Close'] + expected_range,
                'lower_bound': latest['Close'] - expected_range,
                'daily_move_estimate': expected_daily_move
            }
            
        except Exception as e:
            log.error(f"Error calculating expected range: {e}")
            return {}

    def _calculate_professional_confidence(self, df, latest, vix):
        """Professional confidence calculation for Iron Condor"""
        base_confidence = 60
        
        try:
            # VIX in sweet spot (14-18)
            if 14 <= vix <= 18:
                base_confidence += 15
            elif 12 <= vix <= 20:
                base_confidence += 10
                
            # RSI in neutral zone
            rsi = latest['rsi']
            if 40 <= rsi <= 60:
                base_confidence += 10
            elif 35 <= rsi <= 65:
                base_confidence += 5
                
            # Range stability (lower volatility = higher confidence)
            recent_range = (df['High'].tail(10).max() - df['Low'].tail(10).min()) / latest['Close']
            if recent_range < 0.03:
                base_confidence += 10
            elif recent_range < 0.05:
                base_confidence += 5
                
            # Moving average convergence bonus
            ma_spread = abs(latest['sma_20'] - latest['sma_50']) / latest['Close']
            if ma_spread < 0.015:  # Very close MAs
                base_confidence += 5
                
            return min(85, base_confidence)  # Cap at 85%
            
        except Exception as e:
            log.error(f"Error calculating confidence: {e}")
            return 60

    def calculate_position_size(self, signal, account_value):
        """Professional position sizing for Iron Condor"""
        try:
            base_risk = account_value * self.config['risk']['max_risk_per_trade']
            
            # Adjust for confidence
            confidence_factor = signal.get('confidence', 60) / 100.0
            adjusted_risk = base_risk * confidence_factor
            
            # Iron Condor specific adjustments
            wing_width = signal.get('wing_width', 100)
            max_loss_per_lot = wing_width * 0.8  # Assume 80% of wing width as max loss
            
            suggested_lots = max(1, int(adjusted_risk / max_loss_per_lot))
            
            return {
                'max_risk': adjusted_risk,
                'suggested_lots': suggested_lots,
                'max_loss_per_lot': max_loss_per_lot,
                'wing_width': wing_width
            }
            
        except Exception as e:
            log.error(f"Error calculating position size: {e}")
            return {'max_risk': 5000, 'suggested_lots': 1}

from strategies.base_strategy import BaseStrategy
from utils.logger import log
import os

class LongStraddleStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies']['momentum_breakout']

    def generate(self, historical_data, live_data):
        """
        Research-based long straddle for momentum breakouts:
        - Enter before expected large moves (earnings, events)
        - Profit from directional momentum in either direction
        - Buy when vol is reasonable, expect expansion
        """
        try:
            if len(historical_data) < 30:
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]

            # 1. REASONABLE VIX (Research: Not too high to buy straddles)
            vix = live_data.get('vix', {}).get('value', 15)
            if vix > self.params['vix_threshold']:
                return None

            # 2. BREAKOUT SETUP (Research: Consolidation before move)
            if not self._detect_consolidation_breakout(df, latest):
                return None

            # 3. VOLUME CONFIRMATION (Research: Volume spike indicates move)
            if not self._confirm_volume_breakout(df, latest):
                return None

            # 4. MOMENTUM BUILDING (Research: Price approaching key levels)
            if not self._confirm_momentum_setup(df, latest):
                return None

            return {
                'direction': 'long_vol',
                'strategy_type': 'LongStraddle',
                'confidence': self._calculate_confidence(df, latest, vix),
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'max_dte': self.params['max_dte']
            }

        except Exception as e:
            log.error(f"Error in LongStraddleStrategy: {e}")
            return None

    def _detect_consolidation_breakout(self, df, latest):
        """Research: Detect consolidation followed by breakout"""
        # Look for recent tight range
        lookback = 10
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()
        range_pct = (recent_high - recent_low) / latest['Close']
        
        # Tight consolidation
        if range_pct > 0.04:
            return False
            
        # Price near range boundaries (breakout imminent)
        current_pos = (latest['Close'] - recent_low) / (recent_high - recent_low)
        return current_pos < 0.2 or current_pos > 0.8

    def _confirm_volume_breakout(self, df, latest):
        """Research: Volume expansion signals move coming"""
        return latest['Volume'] > df['Volume'].tail(20).mean() * 1.5

    def _confirm_momentum_setup(self, df, latest):
        """Research: Price momentum building"""
        # ATR expansion
        atr_ratio = latest['atr'] / df['atr'].tail(20).mean()
        return atr_ratio > 1.1

    def _calculate_confidence(self, df, latest, vix):
        confidence = 65
        
        # Lower VIX = cheaper straddles
        if vix < 15:
            confidence += 15
        elif vix < 18:
            confidence += 10
            
        # Volume spike bonus
        volume_ratio = latest['Volume'] / df['Volume'].tail(20).mean()
        if volume_ratio > 2.0:
            confidence += 15
            
        return min(85, confidence)

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal.get('confidence', 50) / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 15000))  # High premium cost

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots
        }


# MODIFY your existing generate method:
    def generate_signal(self, historical_data, live_data):
        """Enhanced with instrument-specific volatility logic"""
        
        instrument = os.environ.get('CURRENT_INSTRUMENT', 'NIFTY')
        
        try:
            if len(historical_data) < 30:
                return None
    
            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]
    
            # Apply instrument filters
            filters_passed, filter_reason = self.apply_instrument_filters(df, latest, live_data, instrument)
            if not filters_passed:
                return None
    
            params = self.get_instrument_parameters(instrument)
    
            # Instrument-specific volatility strategy
            if instrument == 'FINNIFTY':
                # For FINNIFTY, use volatility-based approach
                return self._generate_finnifty_volatility_signal(df, latest, live_data, params)
            elif instrument == 'BANKNIFTY':
                # For BANKNIFTY, be much more selective
                return self._generate_banknifty_selective_signal(df, latest, live_data, params)
            else:
                # Standard approach for NIFTY and MIDCPNIFTY
                return self._generate_standard_straddle_signal(df, latest, live_data, params, instrument)
    
        except Exception as e:
            log.error(f"Error in LongStraddleStrategy for {instrument}: {e}")
            return None
    
    def _generate_finnifty_volatility_signal(self, df, latest, live_data, params):
        """FINNIFTY-specific volatility strategy"""
        vix = live_data.get('vix', {}).get('value', 15)
        
        # Only trade FINNIFTY straddles when volatility is cheap (VIX < 15)
        if vix >= params.get('vix_low_threshold', 15):
            return None
        
        # Look for tight consolidation before breakout
        lookback = 5
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()
        range_pct = (recent_high - recent_low) / latest['Close']
        
        if range_pct > 0.015:  # Must be very tight (1.5%)
            return None
            
        return {
            'direction': 'long_vol',
            'strategy_type': 'FinniftyVolatilityStraddle',
            'confidence': 65,
            'spot_price': latest['Close'],
            'vix_at_entry': vix,
            'reason': 'Low vol environment with tight consolidation'
        }
    
    def _generate_banknifty_selective_signal(self, df, latest, live_data, params):
        """BANKNIFTY-specific selective approach"""
        vix = live_data.get('vix', {}).get('value', 15)
        
        # For BANKNIFTY, only trade when VIX is very high (premium rich)
        if vix < 20:
            return None
            
        # Require very tight consolidation
        lookback = 8
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()
        range_pct = (recent_high - recent_low) / latest['Close']
        
        if range_pct > 0.02:  # Very tight requirement
            return None
            
        # Additional volume filter
        if latest['Volume'] < df['Volume'].tail(20).mean() * 2.0:
            return None
            
        return {
            'direction': 'long_vol',
            'strategy_type': 'BankNiftySelectiveStraddle', 
            'confidence': 75,
            'spot_price': latest['Close'],
            'vix_at_entry': vix,
            'reason': 'High VIX with very tight consolidation'
        }
    
    def _generate_standard_straddle_signal(self, df, latest, live_data, params, instrument):
        """Standard straddle logic for NIFTY and MIDCPNIFTY"""
        vix = live_data.get('vix', {}).get('value', 15)
        
        if vix > params.get('vix_threshold', 20):
            return None
    
        if not self._detect_consolidation_breakout(df, latest):
            return None
    
        if not self._confirm_volume_breakout(df, latest):
            return None
    
        confidence = self._calculate_confidence(df, latest, vix)
        
        # Adjust confidence based on instrument performance
        if instrument == 'NIFTY':
            confidence += 5  # Working better
        elif instrument == 'MIDCPNIFTY':
            confidence *= 0.9  # Slightly less confident
    
        return {
            'direction': 'long_vol',
            'strategy_type': 'LongStraddle',
            'confidence': confidence,
            'spot_price': latest['Close'],
            'entry_time': latest.name,
            'max_dte': params.get('max_dte', 30)
        }


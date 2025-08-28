from strategies.base_strategy import BaseStrategy
from utils.logger import log
import os

class DebitSpreadStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.params = config['strategies']['trending_high_vol']

    def generate(self, historical_data, live_data):
        """
        Research-based debit spread strategy:
        - Best in trending + high vol environments
        - Enter on momentum breakouts with volume confirmation
        - RSI filter to avoid overextended entries
        """
        try:
            if len(historical_data) < 50:
                return None

            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]

            # 1. TREND IDENTIFICATION (Research: Use multiple timeframes)
            # Short-term trend (20 SMA) vs Medium-term trend (50 SMA)
            if latest['Close'] > latest['sma_20'] > latest['sma_50']:
                direction = 'bullish'
                trend_strength = (latest['Close'] - latest['sma_50']) / latest['sma_50']
            elif latest['Close'] < latest['sma_20'] < latest['sma_50']:
                direction = 'bearish'  
                trend_strength = (latest['sma_50'] - latest['Close']) / latest['sma_50']
            else:
                return None  # No clear trend

            # 2. MOMENTUM FILTER (Research: RSI 40-80 for bullish, 20-60 for bearish)
            rsi_threshold = self.params['rsi_entry_threshold']
            if direction == 'bullish':
                if latest['rsi'] < 40 or latest['rsi'] > rsi_threshold:
                    return None
            else:  # bearish
                if latest['rsi'] > 60 or latest['rsi'] < (100 - rsi_threshold):
                    return None

            # 3. VOLATILITY ENVIRONMENT (Research: VIX > 18 for debit spreads)
            vix = live_data.get('vix', {}).get('value', 15)
            if vix < 18:
                return None

            # 4. VOLUME CONFIRMATION (Research: 1.5x avg volume for breakouts)
            if latest['Volume'] < latest['volume_avg'] * 1.5:
                return None

            # 5. BREAKOUT CONFIRMATION (Research: Price beyond recent range)
            if not self._confirm_breakout(df, latest, direction):
                return None

            # 6. TREND STRENGTH CHECK (Research: Min 2% trend strength)
            if trend_strength < 0.02:
                return None

            return {
                'direction': direction,
                'strategy_type': 'DebitSpreads',
                'confidence': self._calculate_confidence(df, latest, trend_strength),
                'spot_price': latest['Close'],
                'entry_time': latest.name,
                'spread_width': self.params['spread_width'],
                'max_dte': self.params['max_dte'],
                'min_dte': self.params['min_dte']
            }

        except Exception as e:
            log.error(f"Error in DebitSpreadStrategy: {e}")
            return None

    def _confirm_breakout(self, df, latest, direction):
        """Research: Confirm price breakout beyond recent high/low"""
        lookback = 20
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()
        
        if direction == 'bullish' and latest['Close'] > recent_high * 1.002:
            return True
        elif direction == 'bearish' and latest['Close'] < recent_low * 0.998:
            return True
        return False

    def _calculate_confidence(self, df, latest, trend_strength):
        """Research-based confidence calculation"""
        confidence = 50
        
        # Trend strength factor (max +25)
        confidence += min(25, trend_strength * 500)
        
        # Volume factor (max +15)
        volume_ratio = latest['Volume'] / latest['volume_avg']
        confidence += min(15, (volume_ratio - 1) * 30)
        
        # Volatility expansion factor (max +10)
        atr_ratio = latest['atr'] / df['atr'].tail(20).mean()
        if atr_ratio > 1.2:
            confidence += 10
            
        return min(90, confidence)

    def calculate_position_size(self, signal, account_value):
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade']
        adjusted_risk = risk_per_trade * (signal['confidence'] / 100.0)
        suggested_lots = max(1, int(adjusted_risk / 10000))

        return {
            'max_risk': adjusted_risk,
            'suggested_lots': suggested_lots,
            'confidence_adjusted': True
        }


# MODIFY your existing generate_signal method like this:
    def generate_signal(self, historical_data, live_data):
         """Enhanced with instrument-specific logic"""
         
         # Add instrument detection
         instrument = os.environ.get('CURRENT_INSTRUMENT', 'NIFTY')
         
         try:
             if len(historical_data) < 50:
                 return None
     
             df = self._calculate_technical_indicators(historical_data.copy())
             latest = df.iloc[-1]
     
             # Apply instrument-specific filters FIRST
             filters_passed, filter_reason = self.apply_instrument_filters(df, latest, live_data, instrument)
             if not filters_passed:
                 return None
     
             # Get instrument-specific parameters
             params = self.get_instrument_parameters(instrument)
     
             # Enhanced entry conditions based on instrument
             signal = self._check_enhanced_entry_conditions(df, latest, live_data, params, instrument)
     
             if signal:
                 # Calculate position size based on historical performance
                 position_info = self.calculate_position_size_by_performance(signal, 500000, instrument)
                 
                 signal.update({
                     'strategy_type': 'DebitSpreads',
                     'underlying': instrument,
                     'spot_price': latest['Close'],
                     'entry_time': pd.Timestamp.now(),
                     'position_info': position_info,
                     'instrument_params': params
                 })
     
             return signal
     
         except Exception as e:
             log.error(f"Error in DebitSpreadStrategy for {instrument}: {e}")
             return None
     
    def _check_enhanced_entry_conditions(self, df, latest, live_data, params, instrument):
         """Enhanced entry conditions per instrument"""
         
         # Trend confirmation
         if latest['Close'] > latest['sma_20'] > latest['sma_50']:
             direction = 'bullish'
         elif latest['Close'] < latest['sma_20'] < latest['sma_50']:
             direction = 'bearish'
         else:
             return None
     
         # Instrument-specific RSI checks
         rsi = latest['rsi']
         if instrument == 'BANKNIFTY':
             # More conservative for BANKNIFTY (your worst performer)
             if direction == 'bullish' and rsi < 45:
                 return None
             if direction == 'bearish' and rsi > 55:
                 return None
         elif instrument == 'FINNIFTY':
             # For FINNIFTY, look for volatility extremes
             if not (rsi < 30 or rsi > 70):
                 return None  # Only trade extremes
         else:
             # Standard logic for NIFTY and MIDCPNIFTY
             if direction == 'bullish' and rsi < 40:
                 return None
             if direction == 'bearish' and rsi > 60:
                 return None
     
         # Volume confirmation with instrument params
         if latest['Volume'] < latest['volume_avg'] * params.get('volume_multiplier', 1.2):
             return None
     
         # Breakout confirmation
         if not self._check_breakout_level(df, latest):
             return None
     
         confidence = self._calculate_enhanced_confidence(df, latest, params, instrument)
         
         # Instrument-specific confidence thresholds
         min_confidence = {
             'NIFTY': 55,        # Higher (it's working)
             'BANKNIFTY': 70,    # Much higher (it's failing)
             'FINNIFTY': 60,     # Higher (it's failing)
             'MIDCPNIFTY': 45    # Lower (barely working)
         }.get(instrument, 50)
         
         if confidence < min_confidence:
             return None
     
         return {
             'direction': direction,
             'confidence': confidence,
             'entry_reason': f"{direction} {instrument} breakout",
             'instrument': instrument
         }
     
    def _calculate_enhanced_confidence(self, df, latest, params, instrument):
         """Calculate confidence based on instrument performance"""
         confidence = 50
         
         # Standard factors
         if abs(latest['Close'] - latest['sma_50']) / latest['sma_50'] > 0.05:
             confidence += 15
         
         if latest['Volume'] > latest['volume_avg'] * params.get('volume_multiplier', 1.2) * 1.2:
             confidence += 10
         
         if latest['atr'] > df['atr'].tail(10).mean() * 1.2:
             confidence += 15
     
         # Instrument-specific adjustments based on your actual performance
         if instrument == 'NIFTY':
             confidence += 5  # Slight bonus (it's working)
         elif instrument == 'BANKNIFTY':
             confidence -= 10  # Penalty (it's failing)
         elif instrument == 'FINNIFTY':
             confidence -= 5   # Penalty (it's failing)
         elif instrument == 'MIDCPNIFTY':
             confidence += 2   # Small bonus (marginally working)
     
         return min(confidence, 100)
     

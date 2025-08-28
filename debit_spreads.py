from strategies.base_strategy import BaseStrategy
from utils.logger import log
import pandas as pd

class DebitSpreadStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.strategy_config = config['strategies']['trending_high_vol']

    def generate_signal(self, historical_data, live_data):
        """Generate debit spread signal for trending high volatility markets."""
        try:
            # Ensure we have enough data
            if len(historical_data) < 50:
                return None

            # Calculate indicators
            df = self._calculate_technical_indicators(historical_data.copy())
            latest = df.iloc[-1]
            
            # Check entry conditions
            signal = self._check_entry_conditions(df, latest, live_data)
            
            if signal:
                signal.update({
                    'strategy_type': 'DebitSpreads',
                    'underlying': live_data.get('instrument', 'NIFTY'),
                    'spot_price': latest['Close'],
                    'entry_time': pd.Timestamp.now(),
                    'max_dte': self.strategy_config['max_dte'],
                    'min_dte': self.strategy_config['min_dte']
                })
                
            return signal
            
        except Exception as e:
            log.error(f"Error in DebitSpreadStrategy.generate_signal: {e}")
            return None

    def _check_entry_conditions(self, df, latest, live_data):
        """Check all entry conditions for debit spread."""
        
        # 1. Trend confirmation (price above/below key moving averages)
        if latest['Close'] > latest['sma_20'] > latest['sma_50']:
            direction = 'bullish'
        elif latest['Close'] < latest['sma_20'] < latest['sma_50']:
            direction = 'bearish'
        else:
            return None  # No clear trend
            
        # 2. Momentum confirmation (RSI)
        rsi_threshold = self.strategy_config['rsi_entry_threshold']
        if direction == 'bullish' and latest['rsi'] < rsi_threshold:
            return None
        if direction == 'bearish' and latest['rsi'] > (100 - rsi_threshold):
            return None
            
        # 3. Volume confirmation
        if latest['Volume'] < latest['volume_avg'] * 1.2:
            return None  # Insufficient volume
            
        # 4. Volatility environment check
        vix_data = live_data.get('vix')
        if not vix_data or vix_data['value'] < 18:  # Want higher volatility
            return None
            
        # 5. Check if we're not near support/resistance
        if not self._check_breakout_level(df, latest):
            return None
            
        return {
            'direction': direction,
            'confidence': self._calculate_confidence(df, latest),
            'entry_reason': f"{direction.title()} breakout with volume confirmation"
        }

    def _check_breakout_level(self, df, latest):
        """Check if price is breaking out of a significant level."""
        # Look for breakout above recent highs or below recent lows
        lookback = 20
        recent_high = df['High'].tail(lookback).max()
        recent_low = df['Low'].tail(lookback).min()
        
        current_price = latest['Close']
        
        # Bullish breakout: price above recent high
        if current_price > recent_high * 1.002:  # 0.2% buffer
            return True
            
        # Bearish breakdown: price below recent low  
        if current_price < recent_low * 0.998:  # 0.2% buffer
            return True
            
        return False

    def _calculate_confidence(self, df, latest):
        """Calculate signal confidence (0-100)."""
        confidence = 50  # Base confidence
        
        # Add confidence based on various factors
        
        # Strong trend
        if abs(latest['Close'] - latest['sma_50']) / latest['sma_50'] > 0.05:
            confidence += 15
            
        # Good volume
        if latest['Volume'] > latest['volume_avg'] * 1.5:
            confidence += 10
            
        # RSI not overbought/oversold
        if 30 < latest['rsi'] < 70:
            confidence += 10
            
        # Recent volatility expansion
        if latest['atr'] > df['atr'].tail(10).mean() * 1.2:
            confidence += 15
            
        return min(confidence, 100)

    def calculate_position_size(self, signal, account_value):
        """Calculate position size based on risk management rules."""
        # Risk per trade from config
        risk_per_trade = account_value * self.config['risk']['max_risk_per_trade_pct']
        
        # Adjust based on confidence
        confidence_multiplier = signal['confidence'] / 100.0
        adjusted_risk = risk_per_trade * confidence_multiplier
        
        return {
            'max_risk': adjusted_risk,
            'suggested_lots': max(1, int(adjusted_risk / 10000)),  # Simplified calculation
            'confidence_adjusted': True
        }

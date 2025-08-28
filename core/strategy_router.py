from strategies.debit_spreads import DebitSpreadStrategy
from strategies.long_options import LongOptionsStrategy  
from strategies.iron_condor import IronCondorStrategy
from strategies.protective_straddle import ProtectiveStraddleStrategy
from utils.logger import log
import pandas as pd

class StrategyRouter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.strategies = {
            'trending_high_vol': DebitSpreadStrategy(cfg),
            'trending_low_vol': LongOptionsStrategy(cfg),
            'range_low_vol': IronCondorStrategy(cfg),
            'event_risk_high': ProtectiveStraddleStrategy(cfg) if 'event_risk_high' in cfg['strategies'] else None
        }
        
        # Remove None strategies
        self.strategies = {k: v for k, v in self.strategies.items() if v is not None}
        
        # Professional market condition analyzers
        self.market_analyzer = MarketConditionAnalyzer()

    def generate_signal(self, regime, historical_data, live_data):
        """
        Professional multi-strategy signal generation with market condition analysis
        """
        try:
            # Get primary strategy signal
            primary_signal = self._get_primary_signal(regime, historical_data, live_data)
            
            # Analyze market conditions for secondary strategies
            market_conditions = self._analyze_market_conditions(historical_data, live_data)
            
            # Check for complementary strategies
            secondary_signals = self._get_complementary_strategies(
                regime, market_conditions, historical_data, live_data
            )
            
            # Apply professional signal filtering
            final_signal = self._apply_signal_filters(
                primary_signal, secondary_signals, market_conditions
            )
            
            if final_signal:
                log.info(f"📊 Final signal: {final_signal['strategy_type']} - {final_signal['direction']} (confidence: {final_signal['confidence']}%)")
            
            return final_signal
            
        except Exception as e:
            log.error(f"Error in professional strategy router: {e}")
            return None

    def _get_primary_signal(self, regime, historical_data, live_data):
        """Get signal from primary regime-based strategy"""
        strategy = self.strategies.get(regime)
        if not strategy:
            log.warning(f"No primary strategy for regime '{regime}', using Iron Condor")
            strategy = self.strategies.get('range_low_vol')
            
        if strategy:
            return strategy.generate(historical_data, live_data)
        return None

    def _analyze_market_conditions(self, historical_data, live_data):
        """Professional market condition analysis"""
        try:
            df = historical_data.tail(50).copy()  # Last 50 bars
            latest = df.iloc[-1]
            vix = live_data.get('vix', {}).get('value', 15)
            
            # Calculate market metrics
            volatility_regime = self._classify_volatility_regime(vix)
            trend_strength = self._calculate_trend_strength(df)
            momentum_state = self._analyze_momentum(df)
            volume_profile = self._analyze_volume_profile(df)
            
            return {
                'vix': vix,
                'volatility_regime': volatility_regime,
                'trend_strength': trend_strength,
                'momentum_state': momentum_state,
                'volume_profile': volume_profile,
                'price_level': latest['Close'],
                'recent_range': (df['High'].tail(20).max() - df['Low'].tail(20).min()) / latest['Close']
            }
            
        except Exception as e:
            log.error(f"Error analyzing market conditions: {e}")
            return {}

    def _classify_volatility_regime(self, vix):
        """Classify volatility regime professionally"""
        if vix < 12:
            return 'ultra_low'
        elif vix < 16:
            return 'low'
        elif vix < 22:
            return 'moderate'
        elif vix < 30:
            return 'high'
        else:
            return 'extreme'

    def _calculate_trend_strength(self, df):
        """Calculate professional trend strength indicator"""
        try:
            sma_20 = df['Close'].rolling(20).mean().iloc[-1]
            sma_50 = df['Close'].rolling(50).mean().iloc[-1]
            current_price = df['Close'].iloc[-1]
            
            # Trend alignment score
            if current_price > sma_20 > sma_50:
                strength = (current_price - sma_50) / sma_50
                return min(1.0, strength * 10)  # Normalize to 0-1
            elif current_price < sma_20 < sma_50:
                strength = (sma_50 - current_price) / sma_50
                return -min(1.0, strength * 10)  # Negative for bearish
            else:
                return 0.0  # No clear trend
                
        except Exception as e:
            log.error(f"Error calculating trend strength: {e}")
            return 0.0

    def _analyze_momentum(self, df):
        """Professional momentum analysis"""
        try:
            # RSI momentum
            rsi = self._calculate_rsi(df['Close'], 14).iloc[-1]
            
            # Price momentum (5-day rate of change)
            price_momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-6]) / df['Close'].iloc[-6]
            
            if rsi > 70 and price_momentum > 0.02:
                return 'strong_bullish'
            elif rsi < 30 and price_momentum < -0.02:
                return 'strong_bearish'
            elif 40 <= rsi <= 60:
                return 'neutral'
            else:
                return 'moderate'
                
        except Exception as e:
            log.error(f"Error analyzing momentum: {e}")
            return 'neutral'

    def _analyze_volume_profile(self, df):
        """Professional volume analysis with safety checks"""
        try:
            current_volume = df['Volume'].iloc[-1]
            avg_volume = df['Volume'].tail(20).mean()
            
            # Handle zero/NaN volume safely
            if pd.isna(avg_volume) or avg_volume == 0:
                return 'unknown'
                
            volume_ratio = current_volume / avg_volume
            
            if volume_ratio > 2.0:
                return 'high'
            elif volume_ratio > 1.5:
                return 'elevated'
            elif volume_ratio > 0.5:
                return 'normal'
            else:
                return 'low'
                
        except Exception as e:
            log.error(f"Error analyzing volume: {e}")
            return 'unknown'

    def _get_complementary_strategies(self, regime, market_conditions, historical_data, live_data):
        """Get complementary strategies based on market conditions"""
        complementary = []
        
        try:
            # High volatility situations
            if (market_conditions.get('volatility_regime') == 'extreme' and 
                'event_risk_high' in self.strategies and regime != 'event_risk_high'):
                
                protective_signal = self.strategies['event_risk_high'].generate(historical_data, live_data)
                if protective_signal:
                    complementary.append(protective_signal)
            
            # Strong trending markets
            if (abs(market_conditions.get('trend_strength', 0)) > 0.5 and 
                regime == 'range_low_vol'):
                
                # Switch to trending strategy
                trending_strategy = (self.strategies['trending_high_vol'] 
                                   if market_conditions.get('volatility_regime') in ['high', 'extreme']
                                   else self.strategies['trending_low_vol'])
                
                trending_signal = trending_strategy.generate(historical_data, live_data)
                if trending_signal:
                    complementary.append(trending_signal)
                    
        except Exception as e:
            log.error(f"Error getting complementary strategies: {e}")
            
        return complementary

    def _apply_signal_filters(self, primary_signal, secondary_signals, market_conditions):
        """Apply professional signal filtering and selection"""
        
        # No signals case
        if not primary_signal and not secondary_signals:
            return None
            
        # Only primary signal
        if primary_signal and not secondary_signals:
            return self._validate_signal(primary_signal, market_conditions)
            
        # Only secondary signals
        if not primary_signal and secondary_signals:
            best_secondary = max(secondary_signals, key=lambda x: x.get('confidence', 0))
            return self._validate_signal(best_secondary, market_conditions)
            
        # Both primary and secondary - apply professional logic
        return self._combine_signals_professionally(primary_signal, secondary_signals, market_conditions)

    def _validate_signal(self, signal, market_conditions):
        """Professional signal validation"""
        if not signal:
            return None
            
        # Risk management filters
        vix = market_conditions.get('vix', 15)
        
        # Don't trade in extreme conditions unless it's a protective strategy
        if vix > 35 and signal.get('strategy_type') not in ['ProtectiveStraddle']:
            log.warning(f"Signal blocked due to extreme VIX: {vix}")
            return None
            
        # Adjust confidence based on market conditions
        confidence_adjustment = self._calculate_confidence_adjustment(market_conditions)
        signal['confidence'] = min(95, signal['confidence'] + confidence_adjustment)
        
        return signal

    def _combine_signals_professionally(self, primary, secondary_signals, market_conditions):
        """Professional signal combination logic"""
        
        # If secondary signal has much higher confidence, use it
        best_secondary = max(secondary_signals, key=lambda x: x.get('confidence', 0))
        
        if best_secondary['confidence'] > primary['confidence'] + 20:
            log.info(f"Using secondary strategy due to higher confidence: {best_secondary['strategy_type']}")
            return self._validate_signal(best_secondary, market_conditions)
            
        # Otherwise, enhance primary signal with secondary info
        enhanced_primary = primary.copy()
        enhanced_primary['secondary_confirmation'] = [s['strategy_type'] for s in secondary_signals]
        enhanced_primary['confidence'] = min(95, primary['confidence'] + 10)
        
        return self._validate_signal(enhanced_primary, market_conditions)

    def _calculate_confidence_adjustment(self, market_conditions):
        """Calculate confidence adjustment based on market conditions"""
        adjustment = 0
        
        # Volume confirmation
        if market_conditions.get('volume_profile') == 'elevated':
            adjustment += 5
        elif market_conditions.get('volume_profile') == 'high':
            adjustment += 10
            
        # Trend strength confirmation
        trend_strength = abs(market_conditions.get('trend_strength', 0))
        adjustment += min(10, trend_strength * 20)
        
        return adjustment

    def _calculate_rsi(self, series, period):
        """Professional RSI calculation with error handling"""
        try:
            delta = series.diff()
            gain = delta.clip(lower=0).rolling(period).mean()
            loss = -delta.clip(upper=0).rolling(period).mean()
            
            # Handle division by zero
            rs = gain / loss.replace(0, 1e-10)  # Avoid division by zero
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(50)
            
        except Exception as e:
            log.error(f"Error calculating RSI: {e}")
            return pd.Series([50] * len(series), index=series.index)


class MarketConditionAnalyzer:
    """Professional market condition analysis helper"""
    
    def __init__(self):
        self.volatility_bands = {
            'ultra_low': (0, 12),
            'low': (12, 16), 
            'moderate': (16, 22),
            'high': (22, 30),
            'extreme': (30, 100)
        }

import os
import pandas as pd
from utils.logger import log

# Import all your strategies
from strategies.iron_condor import IronCondorStrategy
from strategies.long_straddle import LongStraddleStrategy
from strategies.debit_spreads import DebitSpreadStrategy
from strategies.long_options import LongOptionsStrategy
from strategies.short_straddle import ShortStraddleStrategy
from strategies.protective_straddle import ProtectiveStraddleStrategy

class AdvancedStrategyRouter:
    """
    Advanced strategy router that selects optimal strategy based on:
    1. Market conditions (VIX, trend, volatility)
    2. Instrument characteristics
    3. Historical performance per instrument
    """
    
    def __init__(self, config):
        self.config = config
        
        # Initialize all strategies
        self.strategies = {
            'iron_condor': IronCondorStrategy(config),
            'long_straddle': LongStraddleStrategy(config),
            'debit_spreads': DebitSpreadStrategy(config),
            'long_options': LongOptionsStrategy(config),
            'short_straddle': ShortStraddleStrategy(config),
            'protective_straddle': ProtectiveStraddleStrategy(config)
        }
        
        # Strategy performance mapping per instrument (based on your actual results)
        self.instrument_strategy_preference = {
            'NIFTY': ['iron_condor', 'debit_spreads', 'long_options'],  # Your best performer
            'BANKNIFTY': ['short_straddle', 'protective_straddle'],      # Needs premium selling
            'FINNIFTY': ['long_straddle', 'protective_straddle'],       # Volatility plays
            'MIDCPNIFTY': ['iron_condor', 'long_options'],              # Range-bound
            'NIFTYNXT50': []  # Avoid completely
        }
        
        # Market condition thresholds
        self.vix_thresholds = {
            'low': 15,      # VIX < 15
            'medium': 22,   # 15 <= VIX < 22
            'high': 30      # VIX >= 22
        }

    def select_optimal_strategy(self, historical_data, live_data, instrument):
        """Select the best strategy based on current market conditions and instrument"""
        
        # Don't trade NIFTYNXT50
        if instrument == 'NIFTYNXT50':
            return None, "NIFTYNXT50 trading suspended"
        
        # Analyze market conditions
        market_conditions = self._analyze_market_conditions(historical_data, live_data)
        
        # Get preferred strategies for this instrument
        preferred_strategies = self.instrument_strategy_preference.get(instrument, ['iron_condor'])
        
        # Select strategy based on market conditions
        selected_strategy_name = self._select_strategy_by_conditions(
            market_conditions, preferred_strategies, instrument
        )
        
        if not selected_strategy_name:
            return None, "No suitable strategy for current conditions"
        
        # Get the strategy instance
        strategy = self.strategies[selected_strategy_name]
        
        # Set environment variable for instrument-specific parameters
        os.environ['CURRENT_INSTRUMENT'] = instrument
        
        try:
            # Generate signal using selected strategy
            signal = strategy.generate(historical_data, live_data)
            
            if signal:
                # Add strategy selection metadata
                signal.update({
                    'selected_strategy': selected_strategy_name,
                    'market_conditions': market_conditions,
                    'instrument': instrument,
                    'selection_reason': self._get_selection_reason(
                        selected_strategy_name, market_conditions, instrument
                    )
                })
                
                log.info(f"✅ {instrument}: Selected {selected_strategy_name} - {signal.get('direction', 'neutral')}")
            
            return signal, selected_strategy_name
            
        except Exception as e:
            log.error(f"Error generating signal with {selected_strategy_name} for {instrument}: {e}")
            return None, f"Strategy error: {e}"
        finally:
            # Clean up environment variable
            if 'CURRENT_INSTRUMENT' in os.environ:
                del os.environ['CURRENT_INSTRUMENT']

    def _analyze_market_conditions(self, historical_data, live_data):
        """Analyze current market conditions"""
        try:
            df = historical_data.tail(50)  # Last 50 days
            latest = df.iloc[-1]
            
            # VIX analysis
            vix = live_data.get('vix', {}).get('value', 18)
            if vix < self.vix_thresholds['low']:
                vix_regime = 'low'
            elif vix < self.vix_thresholds['medium']:
                vix_regime = 'medium'
            else:
                vix_regime = 'high'
            
            # Trend analysis
            if len(df) >= 20:
                sma_20 = df['Close'].rolling(20).mean().iloc[-1]
                sma_50 = df['Close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else sma_20
                
                if latest['Close'] > sma_20 > sma_50:
                    trend = 'uptrend'
                elif latest['Close'] < sma_20 < sma_50:
                    trend = 'downtrend'
                else:
                    trend = 'sideways'
            else:
                trend = 'sideways'
            
            # Volatility regime
            if len(df) >= 20:
                recent_volatility = df['Close'].pct_change().rolling(20).std().iloc[-1]
                historical_volatility = df['Close'].pct_change().std()
                
                if recent_volatility > historical_volatility * 1.2:
                    vol_regime = 'expanding'
                elif recent_volatility < historical_volatility * 0.8:
                    vol_regime = 'contracting'
                else:
                    vol_regime = 'stable'
            else:
                vol_regime = 'stable'
            
            # Range-bound detection
            if len(df) >= 20:
                recent_high = df['High'].tail(20).max()
                recent_low = df['Low'].tail(20).min()
                range_pct = (recent_high - recent_low) / latest['Close']
                
                if range_pct < 0.04:
                    range_condition = 'tight'
                elif range_pct < 0.08:
                    range_condition = 'normal'
                else:
                    range_condition = 'wide'
            else:
                range_condition = 'normal'
            
            return {
                'vix': vix,
                'vix_regime': vix_regime,
                'trend': trend,
                'volatility_regime': vol_regime,
                'range_condition': range_condition,
                'current_price': latest['Close']
            }
            
        except Exception as e:
            log.error(f"Error analyzing market conditions: {e}")
            return {
                'vix': 18, 'vix_regime': 'medium', 'trend': 'sideways',
                'volatility_regime': 'stable', 'range_condition': 'normal'
            }

    def _select_strategy_by_conditions(self, conditions, preferred_strategies, instrument):
        """Select strategy based on market conditions"""
        
        vix_regime = conditions['vix_regime']
        trend = conditions['trend']
        vol_regime = conditions['volatility_regime']
        range_condition = conditions['range_condition']
        
        # Strategy selection logic based on conditions
        if instrument == 'BANKNIFTY':
            # For BANKNIFTY (your worst performer), be very selective
            if vix_regime == 'high' and range_condition == 'tight':
                return 'short_straddle'  # High premium collection
            elif vix_regime == 'high':
                return 'protective_straddle'  # High vol protection
            else:
                return None  # Don't trade BANKNIFTY in other conditions
                
        elif instrument == 'FINNIFTY':
            # For FINNIFTY, focus on volatility strategies
            if vix_regime == 'low' and range_condition == 'tight':
                return 'long_straddle'  # Buy cheap volatility
            elif vix_regime == 'high':
                return 'protective_straddle'  # High vol environment
            else:
                return None
                
        elif instrument == 'NIFTY':
            # For NIFTY (your best performer), use broader strategy set
            if vix_regime == 'low' and range_condition in ['tight', 'normal']:
                return 'iron_condor'  # Range-bound, low vol
            elif trend in ['uptrend', 'downtrend'] and vix_regime == 'medium':
                return 'debit_spreads'  # Trending market
            elif vix_regime == 'low' and trend != 'sideways':
                return 'long_options'  # Trending + low vol
            else:
                return 'iron_condor'  # Default for NIFTY
                
        elif instrument == 'MIDCPNIFTY':
            # For MIDCPNIFTY (marginally profitable), be conservative
            if range_condition == 'tight' and vix_regime in ['low', 'medium']:
                return 'iron_condor'
            elif trend != 'sideways' and vix_regime == 'low':
                return 'long_options'
            else:
                return None
        
        # Default fallback
        if preferred_strategies:
            return preferred_strategies[0]
        
        return None

    def _get_selection_reason(self, strategy_name, conditions, instrument):
        """Get human-readable reason for strategy selection"""
        vix = conditions['vix_regime']
        trend = conditions['trend']
        vol = conditions['volatility_regime']
        
        reasons = {
            'iron_condor': f"Range-bound market, {vix} VIX, suitable for premium collection",
            'long_straddle': f"Tight range with {vix} VIX, expecting breakout",
            'debit_spreads': f"{trend.title()} trend with {vix} VIX, directional play",
            'long_options': f"{trend.title()} trend with {vix} VIX, low cost directional",
            'short_straddle': f"High VIX ({conditions['vix']:.1f}), premium rich environment",
            'protective_straddle': f"High volatility protection, VIX {conditions['vix']:.1f}"
        }
        
        return reasons.get(strategy_name, f"Default strategy for {instrument}")

    def get_strategy_performance_summary(self, instrument):
        """Get performance summary for strategies on this instrument"""
        preferred = self.instrument_strategy_preference.get(instrument, [])
        return {
            'instrument': instrument,
            'preferred_strategies': preferred,
            'total_available_strategies': len(self.strategies),
            'active_strategies': len(preferred) if preferred else 0
        }

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import os
from utils.logger import log

class BaseStrategy(ABC):
    def __init__(self, config):
        self.config = config
        self.indicator_cache = {}

    @abstractmethod
    def generate(self, historical_data, live_data):
        """Generate trade signal. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def calculate_position_size(self, signal, account_value):
        """Calculate position size. Must be implemented by subclasses."""
        pass

    def get_instrument_parameters(self, instrument=None):
        """Get instrument-specific parameters based on actual performance analysis"""
        if instrument is None:
            instrument = os.environ.get('CURRENT_INSTRUMENT', 'NIFTY')
        
        # Based on your REAL performance data analysis
        if instrument == 'BANKNIFTY':
            # Your BANKNIFTY is losing ₹5,419 with 46.8% win rate - needs major changes
            return {
                'stop_loss': 250,           # Tighter than current
                'target': 450,              # Higher than current
                'position_size': 1,         # Smaller than current
                'vix_threshold': 18,        # Don't trade in high vol
                'rsi_upper': 60,            # More conservative
                'rsi_lower': 40,            # More conservative
                'volume_multiplier': 1.8,   # Higher volume needed
                'avoid_first_hour': True,   # Skip 9:15-10:15
                'max_trades_per_day': 1     # Limit exposure
            }
        elif instrument == 'NIFTY':
            # Your NIFTY is profitable +₹3,401 with 49% win rate - optimize this
            return {
                'stop_loss': 180,           # Slightly tighter
                'target': 320,              # Slightly higher
                'position_size': 3,         # Increase (it's working)
                'vix_threshold': 25,        # Current seems OK
                'rsi_upper': 65,
                'rsi_lower': 35,
                'volume_multiplier': 1.3,
                'confidence_threshold': 55  # Require higher confidence
            }
        elif instrument == 'FINNIFTY':
            # Your FINNIFTY is losing ₹1,812 with 41.2% win rate - needs new approach
            return {
                'stop_loss': 300,
                'target': 500,              # Higher risk/reward needed
                'position_size': 1,         # Small size while testing
                'vix_low_threshold': 15,    # Buy vol when cheap
                'vix_high_threshold': 25,   # Sell vol when expensive
                'rsi_extreme_upper': 75,    # Look for extremes
                'rsi_extreme_lower': 25     # Look for extremes
            }
        elif instrument == 'MIDCPNIFTY':
            # Your MIDCPNIFTY is barely profitable +₹907 with 37.5% win rate - improve win rate
            return {
                'stop_loss': 120,           # Tighter stops
                'target': 200,              # Moderate targets
                'position_size': 3,         # Can increase size
                'rsi_upper': 62,            # Tighter range
                'rsi_lower': 38,            # Tighter range
                'volume_multiplier': 1.5,
                'trend_strength_min': 0.01  # Require clear trend
            }
        elif instrument == 'NIFTYNXT50':
            # Your NIFTYNXT50 is losing ₹1,340 with 42.1% win rate - AVOID
            return {
                'active': False,            # Don't trade this
                'reason': 'Poor liquidity and performance'
            }
        
        # Default to NIFTY parameters
        return self.get_instrument_parameters('NIFTY')

    def apply_instrument_filters(self, df, latest, live_data, instrument=None):
        """Apply instrument-specific filters based on actual performance issues"""
        if instrument is None:
            instrument = os.environ.get('CURRENT_INSTRUMENT', 'NIFTY')
        
        params = self.get_instrument_parameters(instrument)
        
        # Don't trade NIFTYNXT50 at all
        if instrument == 'NIFTYNXT50':
            return False, "NIFTYNXT50 suspended due to poor performance"
        
        # VIX filter
        vix_data = live_data.get('vix', {})
        current_vix = vix_data.get('value', 15)
        
        if instrument == 'BANKNIFTY':
            # BANKNIFTY specific filters (your worst performer)
            if current_vix > params.get('vix_threshold', 18):
                return False, f"BANKNIFTY VIX too high: {current_vix}"
                
            # Time filter for BANKNIFTY
            current_time = pd.Timestamp.now()
            if params.get('avoid_first_hour', False):
                if current_time.hour == 9 or (current_time.hour == 10 and current_time.minute < 15):
                    return False, "BANKNIFTY: Avoiding first hour"
                    
        elif instrument == 'FINNIFTY':
            # FINNIFTY volatility-based filters
            vix_low = params.get('vix_low_threshold', 15)
            vix_high = params.get('vix_high_threshold', 25)
            
            if not (current_vix < vix_low or current_vix > vix_high):
                return False, f"FINNIFTY VIX in dead zone: {current_vix}"
                
        else:
            # Standard VIX filter for others
            if current_vix > params.get('vix_threshold', 25):
                return False, f"VIX too high: {current_vix}"
        
        # Volume filter
        volume_multiplier = params.get('volume_multiplier', 1.2)
        if latest['Volume'] < latest['volume_avg'] * volume_multiplier:
            return False, "Volume too low"
        
        # RSI filter
        rsi = latest.get('rsi', 50)
        rsi_upper = params.get('rsi_upper', 65)
        rsi_lower = params.get('rsi_lower', 35)
        
        if not (rsi_lower <= rsi <= rsi_upper):
            return False, f"RSI outside range: {rsi}"
        
        return True, "All filters passed"

    def calculate_position_size_by_performance(self, signal, account_value, instrument=None):
        """Calculate position size based on historical performance"""
        if instrument is None:
            instrument = signal.get('instrument', 'NIFTY')
        
        params = self.get_instrument_parameters(instrument)
        
        # Base risk per trade
        base_risk = account_value * 0.02  # 2%
        
        # Adjust based on historical performance
        performance_multipliers = {
            'NIFTY': 1.2,       # Increase (profitable)
            'MIDCPNIFTY': 1.0,  # Keep same (marginally profitable)
            'BANKNIFTY': 0.5,   # Reduce significantly (big loser)
            'FINNIFTY': 0.6,    # Reduce (loser)
            'NIFTYNXT50': 0.0   # Avoid completely
        }
        
        multiplier = performance_multipliers.get(instrument, 1.0)
        adjusted_risk = base_risk * multiplier
        
        # Calculate position size
        stop_loss = params.get('stop_loss', 200)
        target = params.get('target', 300)
        position_size = params.get('position_size', 1)
        
        # Final position size
        final_position_size = int(position_size * multiplier)
        final_position_size = max(1, final_position_size)  # Minimum 1
        
        return {
            'position_size': final_position_size,
            'max_risk': stop_loss * final_position_size,
            'target': target * final_position_size,
            'stop_loss': stop_loss,
            'risk_multiplier': multiplier,
            'instrument': instrument
        }

    def _calculate_technical_indicators(self, df):
        """Professional technical indicator calculation with robust error handling"""
        try:
            # Ensure minimum data length
            if len(df) < 20:
                log.warning("Insufficient data for technical indicators")
                return df

            # Basic moving averages
            df['sma_20'] = df['Close'].rolling(window=20, min_periods=10).mean()
            df['sma_50'] = df['Close'].rolling(window=min(50, len(df)), min_periods=20).mean()

            # RSI calculation with error handling
            rsi_period = self.config.get('indicators', {}).get('rsi_period', 14)
            df['rsi'] = self._calculate_rsi_robust(df['Close'], rsi_period)

            # Volume average with robust handling
            volume_period = self.config.get('indicators', {}).get('volume_avg', 20)
            df['volume_avg'] = self._calculate_volume_avg_robust(df['Volume'], volume_period)

            # ATR calculation
            atr_period = self.config.get('indicators', {}).get('atr_period', 14)
            df['atr'] = self._calculate_atr_robust(df, atr_period)

            # Additional professional indicators
            df['bb_upper'], df['bb_lower'] = self._calculate_bollinger_bands(df['Close'])
            df['macd'], df['macd_signal'] = self._calculate_macd(df['Close'])

            return df

        except Exception as e:
            log.error(f"Error calculating technical indicators: {e}")
            return df

    def _calculate_rsi_robust(self, series, period):
        """Robust RSI calculation with error handling"""
        try:
            if len(series) < period + 1:
                return pd.Series([50] * len(series), index=series.index)

            delta = series.diff()
            gain = delta.clip(lower=0).rolling(window=period, min_periods=period//2).mean()
            loss = -delta.clip(upper=0).rolling(window=period, min_periods=period//2).mean()

            # Handle division by zero and infinity
            loss = loss.replace(0, 1e-10)  # Avoid division by zero
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            # Fill NaN values with neutral RSI
            rsi = rsi.fillna(50)

            # Clamp values to valid range
            rsi = rsi.clip(0, 100)

            return rsi

        except Exception as e:
            log.error(f"Error calculating RSI: {e}")
            return pd.Series([50] * len(series), index=series.index)

    def _calculate_volume_avg_robust(self, volume_series, period):
        """Robust volume average calculation"""
        try:
            # Handle zero and negative volumes
            clean_volume = volume_series.replace(0, np.nan)
            clean_volume = clean_volume[clean_volume > 0]

            if len(clean_volume) < period // 2:
                # If insufficient data, use overall mean
                fallback_avg = volume_series.mean() if volume_series.sum() > 0 else 1000
                return pd.Series([fallback_avg] * len(volume_series), index=volume_series.index)

            volume_avg = clean_volume.rolling(window=period, min_periods=period//2).mean()

            # Forward fill for missing values
            volume_avg = volume_avg.fillna(method='ffill').fillna(clean_volume.mean())

            # Ensure no zero values
            volume_avg = volume_avg.replace(0, clean_volume.mean())

            return volume_avg.reindex(volume_series.index).fillna(volume_series.mean())

        except Exception as e:
            log.error(f"Error calculating volume average: {e}")
            fallback = volume_series.mean() if volume_series.sum() > 0 else 1000
            return pd.Series([fallback] * len(volume_series), index=volume_series.index)

    def _calculate_atr_robust(self, df, period):
        """Robust ATR calculation with error handling"""
        try:
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift(1))
            low_close = np.abs(df['Low'] - df['Close'].shift(1))

            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(window=period, min_periods=period//2).mean()

            # Fill NaN values with reasonable estimates
            atr = atr.bfill().fillna(df['Close'] * 0.02)  # 2% of price as fallback

            return atr

        except Exception as e:
            log.error(f"Error calculating ATR: {e}")
            return pd.Series(df['Close'] * 0.02, index=df.index)

    def _calculate_bollinger_bands(self, series, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        try:
            sma = series.rolling(window=period).mean()
            std = series.rolling(window=period).std()

            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)

            return upper_band.fillna(series), lower_band.fillna(series)

        except Exception as e:
            log.error(f"Error calculating Bollinger Bands: {e}")
            return series, series

    def _calculate_macd(self, series, fast=12, slow=26, signal=9):
        """Calculate MACD indicator"""
        try:
            ema_fast = series.ewm(span=fast).mean()
            ema_slow = series.ewm(span=slow).mean()

            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()

            return macd_line.fillna(0), signal_line.fillna(0)

        except Exception as e:
            log.error(f"Error calculating MACD: {e}")
            zeros = pd.Series([0] * len(series), index=series.index)
            return zeros, zeros

    def get_strategy_metadata(self):
        """Return strategy metadata for monitoring"""
        return {
            'strategy_name': self.__class__.__name__,
            'config_params': getattr(self, 'params', {}),
            'last_calculation_time': getattr(self, '_last_calc_time', None)
        }

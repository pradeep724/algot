from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from utils.logger import log

class BaseStrategy(ABC):
    def __init__(self, config):
        self.config = config
        self.indicator_cache = {}  # Cache for expensive calculations

    @abstractmethod
    def generate(self, data, live_data):
        """Generate trade signal. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def calculate_position_size(self, signal, account_value):
        """Calculate position size. Must be implemented by subclasses."""
        pass

    def generate_signal_for_instrument(self, historical_data, live_data, instrument):
        """Generate signal with instrument-specific parameters."""
        try:
            # Get instrument-specific strategy config
            strategy_name = self._get_strategy_name()
            base_config = self.config.get('strategies', {}).get(strategy_name, {})
            instrument_config = base_config.get(instrument, {})
            
            # Merge base config with instrument-specific config
            merged_config = {**base_config, **instrument_config}
            
            # Apply BANKNIFTY enhancements
            if instrument == 'BANKNIFTY':
                merged_config = self._apply_banknifty_enhancements(merged_config)
            
            # Store the merged config temporarily
            original_config = getattr(self, 'strategy_config', None)
            self.strategy_config = merged_config
            
            # Generate signal with enhanced config
            signal = self.generate(historical_data, live_data)
            
            # Restore original config
            if original_config:
                self.strategy_config = original_config
            
            # Add instrument-specific metadata
            if signal:
                signal.update({
                    'instrument': instrument,
                    'config_used': merged_config,
                    'enhanced_for_banknifty': instrument == 'BANKNIFTY'
                })
            
            return signal
            
        except Exception as e:
            log.error(f"Error generating signal for {instrument}: {e}")
            return None

    def _get_strategy_name(self):
        """Get strategy name from class name."""
        class_name = self.__class__.__name__
        # Convert CamelCase to snake_case
        import re
        return re.sub('(.)([A-Z][a-z]+)', r'\1_\2', class_name).lower().replace('_strategy', '')

    def _apply_banknifty_enhancements(self, config):
        """Apply specific enhancements for BANKNIFTY performance improvement."""
        enhanced_config = config.copy()
        
        # BANKNIFTY improvements based on analysis
        banknifty_enhancements = {
            'vix_threshold': min(config.get('vix_threshold', 20), 18),  # Lower VIX requirement
            'rsi_entry_threshold': max(config.get('rsi_entry_threshold', 35), 40),  # More selective
            'volume_multiplier': config.get('volume_multiplier', 1.2) * 1.3,  # Higher volume requirement
            'confidence_threshold': max(config.get('confidence_threshold', 60), 70),  # Higher confidence
            'max_risk_reduction': 0.8,  # 20% less risk
            'target_increase': 1.15,  # 15% higher targets
        }
        
        enhanced_config.update(banknifty_enhancements)
        
        log.debug(f"Applied BANKNIFTY enhancements: {banknifty_enhancements}")
        return enhanced_config

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

            # Volatility indicators (important for options trading)
            df['volatility'] = df['Close'].pct_change().rolling(20).std() * np.sqrt(252)
            
            # Price momentum
            df['momentum_5'] = df['Close'] / df['Close'].shift(5) - 1
            df['momentum_10'] = df['Close'] / df['Close'].shift(10) - 1

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

    def _validate_data_quality(self, df):
        """Professional data quality validation"""
        issues = []

        try:
            # Check for missing data
            missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
            if missing_pct > 5:
                issues.append(f"High missing data: {missing_pct:.1f}%")

            # Check for zero volumes
            if 'Volume' in df.columns:
                zero_volume_pct = (df['Volume'] == 0).sum() / len(df) * 100
                if zero_volume_pct > 10:
                    issues.append(f"High zero volume bars: {zero_volume_pct:.1f}%")

            # Check for suspicious price movements
            price_changes = df['Close'].pct_change().abs()
            extreme_moves = (price_changes > 0.1).sum()  # >10% moves
            if extreme_moves > len(df) * 0.05:  # More than 5% of bars
                issues.append(f"Many extreme price moves: {extreme_moves}")

            if issues:
                log.warning(f"Data quality issues: {'; '.join(issues)}")

            return len(issues) == 0

        except Exception as e:
            log.error(f"Error validating data quality: {e}")
            return True  # Default to accepting data

    def _check_instrument_specific_conditions(self, df, latest, live_data, instrument):
        """Check instrument-specific entry conditions."""
        try:
            # BANKNIFTY specific conditions
            if instrument == 'BANKNIFTY':
                return self._check_banknifty_conditions(df, latest, live_data)
            
            # NIFTY specific conditions  
            elif instrument == 'NIFTY':
                return self._check_nifty_conditions(df, latest, live_data)
                
            # SENSEX specific conditions
            elif instrument == 'SENSEX':
                return self._check_sensex_conditions(df, latest, live_data)
                
            # Default conditions for other instruments
            else:
                return self._check_default_conditions(df, latest, live_data)
                
        except Exception as e:
            log.error(f"Error checking instrument conditions for {instrument}: {e}")
            return True  # Default to allowing trade

    def _check_banknifty_conditions(self, df, latest, live_data):
        """Enhanced conditions specific to BANKNIFTY."""
        try:
            # 1. VIX condition (stricter for BANKNIFTY)
            vix_data = live_data.get('vix', {})
            if vix_data.get('value', 15) > 18:
                log.debug("BANKNIFTY: VIX too high")
                return False
            
            # 2. Trend strength requirement
            if latest['sma_20'] and latest['sma_50']:
                trend_strength = abs(latest['sma_20'] - latest['sma_50']) / latest['Close']
                if trend_strength < 0.02:  # Require 2% trend strength
                    log.debug("BANKNIFTY: Insufficient trend strength")
                    return False
            
            # 3. Volume requirement (higher for BANKNIFTY)
            volume_ratio = latest['Volume'] / latest['volume_avg']
            if volume_ratio < 1.5:  # Require 50% above average
                log.debug("BANKNIFTY: Insufficient volume")
                return False
                
            # 4. Volatility expansion check
            if latest['volatility'] and len(df) > 20:
                vol_percentile = (df['volatility'].tail(20) < latest['volatility']).mean()
                if vol_percentile < 0.7:  # Require volatility in top 30%
                    log.debug("BANKNIFTY: Insufficient volatility expansion")
                    return False
            
            return True
            
        except Exception as e:
            log.error(f"Error in BANKNIFTY conditions: {e}")
            return True

    def _check_nifty_conditions(self, df, latest, live_data):
        """Conditions specific to NIFTY."""
        # NIFTY generally performs well, so standard conditions
        return True

    def _check_sensex_conditions(self, df, latest, live_data):
        """Conditions specific to SENSEX."""
        # Similar to NIFTY but may have different characteristics
        return True

    def _check_default_conditions(self, df, latest, live_data):
        """Default conditions for other instruments."""
        return True

    def calculate_position_size_for_instrument(self, signal, account_value, instrument):
        """Calculate position size with instrument-specific adjustments."""
        try:
            # Get base position size
            base_size = self.calculate_position_size(signal, account_value)
            
            # Apply instrument-specific adjustments
            if instrument == 'BANKNIFTY':
                # Reduce BANKNIFTY position size by 20%
                base_size['max_risk'] *= 0.8
                base_size['suggested_lots'] = max(1, int(base_size['suggested_lots'] * 0.8))
                base_size['banknifty_adjusted'] = True
                
                log.debug(f"Applied BANKNIFTY position size reduction: {base_size}")
            
            elif instrument in ['MIDCPNIFTY', 'NIFTYNXT50']:
                # These might allow slightly larger positions due to lower individual risk
                base_size['suggested_lots'] = int(base_size['suggested_lots'] * 1.2)
                
            return base_size
            
        except Exception as e:
            log.error(f"Error calculating position size for {instrument}: {e}")
            return self.calculate_position_size(signal, account_value)

    def get_strategy_metadata(self):
        """Return enhanced strategy metadata for monitoring"""
        return {
            'strategy_name': self.__class__.__name__,
            'config_params': getattr(self, 'strategy_config', {}),
            'last_calculation_time': getattr(self, '_last_calc_time', None),
            'supports_multi_index': True,
            'banknifty_enhanced': True,
            'instrument_specific': True
        }

    def log_signal_details(self, signal, instrument, df, latest):
        """Enhanced logging for debugging and monitoring."""
        if signal:
            log.info(f"âœ… {instrument} Signal Generated:")
            log.info(f"   Direction: {signal.get('direction')}")
            log.info(f"   Confidence: {signal.get('confidence', 'Unknown')}%")
            log.info(f"   Strategy: {signal.get('strategy_type', 'Unknown')}")
            log.info(f"   RSI: {latest.get('rsi', 'Unknown'):.1f}")
            log.info(f"   Volume Ratio: {latest.get('Volume', 0) / latest.get('volume_avg', 1):.1f}")
            if 'vix' in signal:
                log.info(f"   VIX: {signal['vix']}")
        else:
            log.debug(f"âŒ {instrument}: No signal generated")

# Enhanced base class for Iron Condor strategies with multi-index support
class EnhancedIronCondorStrategy(BaseStrategy):
    """Enhanced Iron Condor base class with instrument-specific optimizations."""
    
    def __init__(self, config):
        super().__init__(config)
        self.strategy_config = config.get('strategies', {}).get('range_bound', {})

    def _check_range_bound_conditions(self, df, latest, live_data, instrument):
        """Enhanced range-bound detection with instrument-specific parameters."""
        try:
            # Get instrument-specific thresholds
            config = self.strategy_config.get(instrument, self.strategy_config)
            
            # 1. RSI range check
            rsi = latest.get('rsi', 50)
            rsi_upper = config.get('rsi_upper', 65)
            rsi_lower = config.get('rsi_lower', 35)
            
            if not (rsi_lower < rsi < rsi_upper):
                return False, f"RSI {rsi:.1f} outside range {rsi_lower}-{rsi_upper}"
            
            # 2. VIX check
            vix = live_data.get('vix', {}).get('value', 15)
            vix_threshold = config.get('vix_threshold', 22)
            
            if vix > vix_threshold:
                return False, f"VIX {vix:.1f} > threshold {vix_threshold}"
            
            # 3. Price range analysis
            if not self._analyze_price_range(df, latest, instrument):
                return False, "Price not in suitable range"
                
            return True, "All conditions met"
            
        except Exception as e:
            log.error(f"Error checking range-bound conditions for {instrument}: {e}")
            return False, f"Error: {e}"

    def _analyze_price_range(self, df, latest, instrument):
        """Analyze if price is in suitable range for Iron Condor."""
        try:
            # Look for consolidation period
            lookback = 20
            recent_data = df.tail(lookback)
            
            price_range = (recent_data['High'].max() - recent_data['Low'].min()) / latest['Close']
            
            # Instrument-specific range thresholds
            range_thresholds = {
                'NIFTY': 0.06,      # 6% range
                'BANKNIFTY': 0.08,  # 8% range (more volatile)
                'SENSEX': 0.06,     # 6% range
                'FINNIFTY': 0.07,   # 7% range
                'MIDCPNIFTY': 0.05, # 5% range (less volatile)
                'BANKEX': 0.08,     # 8% range
                'NIFTYNXT50': 0.06  # 6% range
            }
            
            max_range = range_thresholds.get(instrument, 0.06)
            
            return price_range <= max_range
            
        except Exception as e:
            log.error(f"Error analyzing price range for {instrument}: {e}")
            return True

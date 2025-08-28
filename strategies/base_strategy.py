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
            rsi_period = self.config['indicators'].get('rsi_period', 14)
            df['rsi'] = self._calculate_rsi_robust(df['Close'], rsi_period)
            
            # Volume average with robust handling
            volume_period = self.config['indicators'].get('volume_avg', 20)
            df['volume_avg'] = self._calculate_volume_avg_robust(df['Volume'], volume_period)
            
            # ATR calculation
            atr_period = self.config['indicators'].get('atr_period', 14)
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

    def _validate_data_quality(self, df):
        """Professional data quality validation"""
        issues = []
        
        try:
            # Check for missing data
            missing_pct = df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100
            if missing_pct > 5:
                issues.append(f"High missing  {missing_pct:.1f}%")
            
            # Check for zero volumes
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

    def get_strategy_metadata(self):
        """Return strategy metadata for monitoring"""
        return {
            'strategy_name': self.__class__.__name__,
            'config_params': getattr(self, 'params', {}),
            'last_calculation_time': getattr(self, '_last_calc_time', None)
        }

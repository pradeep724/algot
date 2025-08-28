from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from utils.logger import log

class BaseStrategy(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def generate(self, data, live_data):
        """Generate trade signal. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def calculate_position_size(self, signal, account_value):
        """Calculate position size. Must be implemented by subclasses."""
        pass

    def _calculate_technical_indicators_test(self, df):
        try:
            df['sma_20'] = df['Close'].rolling(window=20).mean()
            df['sma_50'] = df['Close'].rolling(window=50).mean()
            df['rsi'] = self._calculate_rsi(df['Close'], self.config['indicators']['rsi_period'])
            df['volume_avg'] = df['Volume'].rolling(window=self.config['indicators']['volume_avg']).mean()
            df['atr'] = self._calculate_atr(df, self.config['indicators']['atr_period'])
            return df
        except Exception as e:
            log.error(f"Error calculating indicators: {e}")
            return df

    def _calculate_rsi(self, series, period):
        delta = series.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = -delta.clip(upper=0).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _calculate_atr(self, df, period):
        high_low = df['High'] - df['Low']
        high_close_prev = np.abs(df['High'] - df['Close'].shift(1))
        low_close_prev = np.abs(df['Low'] - df['Close'].shift(1))
        tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.bfill()  # Fixed deprecation warning

    def _calculate_technical_indicators(self, df):
      try:
        df['sma_20'] = df['Close'].rolling(window=20).mean()
        df['sma_50'] = df['Close'].rolling(window=50).mean()
        df['rsi'] = self._calculate_rsi(df['Close'], self.config['indicators']['rsi_period'])
        
        # Handle volume_avg calculation with error handling
        volume_window = self.config['indicators'].get('volume_avg', 20)
        df['volume_avg'] = df['Volume'].rolling(window=volume_window).mean()
        
        # Fill NaN values in volume_avg
        df['volume_avg'] = df['volume_avg'].fillna(df['Volume'].mean())
        
        df['atr'] = self._calculate_atr(df, self.config['indicators']['atr_period'])
        return df
      except Exception as e:
        log.error(f"Error calculating indicators: {e}")
        return df

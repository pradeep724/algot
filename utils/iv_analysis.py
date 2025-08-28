import pandas as pd

class IVAnalyzer:
    @staticmethod
    def calculate_iv_percentile(iv_series, lookback=252):
        """
        Calculate IV percentile over past 'lookback' days (default 1 year)
        """
        if len(iv_series) < lookback:
            return 0.5  # Neutral placeholder
        recent_iv = iv_series[-1]
        iv_history = iv_series[-lookback:]
        percentile = (iv_history < recent_iv).mean()
        return percentile

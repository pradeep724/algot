"""
dynamic_mode.py
---------------
Dynamic selection of trading mode (intraday or swing) based on market trend.
Uses one or more index symbols and recent candles to compute trend and volatility.
"""

import pandas as pd
import numpy as np

def choose_mode_dynamic(index_dfs: list, short_window=12, long_window=26, adx_window=14, slope_threshold=0.05):
    """
    Determine trading mode based on trend analysis of index(es).
    
    Parameters:
    -----------
    index_dfs : list of pd.DataFrame
        List of index dataframes with indicators already added (ema_fast, ema_slow, adx)
    short_window, long_window : int
        EMA windows used for trend calculation
    adx_window : int
        ADX window used for trend strength
    slope_threshold : float
        Minimum EMA slope (percent) to consider as intraday trend
    
    Returns:
    --------
    str : "intraday" or "swing"
    """
    if not index_dfs:
        return "swing"  # fallback
    
    mode_votes = []

    for df in index_dfs:
        if df is None or df.empty:
            continue

        # Ensure necessary columns exist
        if not all(col in df.columns for col in ["ema_fast", "ema_slow", "adx"]):
            continue

        # Calculate EMA slope in percent
        slope = (df["ema_fast"].iloc[-1] / df["ema_fast"].iloc[-min(len(df), 10)] - 1.0) * 100
        adx = df["adx"].iloc[-1]

        # Heuristic: intraday if strong short-term trend and moderate ADX
        if abs(slope) > slope_threshold and adx > 15:
            mode_votes.append("intraday")
        else:
            mode_votes.append("swing")

    # Majority vote
    if mode_votes.count("intraday") > mode_votes.count("swing"):
        return "intraday"
    else:
        return "swing"

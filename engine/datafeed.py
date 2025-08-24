import pandas as pd
import numpy as np
import ta  # pip install ta

def candles_to_df(candles):
    """
    Convert raw AngelOne candles (list of [time, open, high, low, close, volume])
    to pandas DataFrame with proper dtypes and timestamp index.
    """
    if not candles:
        return pd.DataFrame()
    
    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.set_index("timestamp").dropna()
    return df


def add_indicators(df, fast=12, slow=26, atr_period=14):
    """
    Add technical indicators (EMA fast/slow, ATR, ADX) safely to a DataFrame.
    Handles small datasets and returns numeric columns only when possible.
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    # Ensure numeric columns
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    # Drop rows with NaN
    out = out.dropna(subset=["high", "low", "close"])
    if out.empty:
        return out

    min_rows = max(2 * atr_period, slow, fast, 28)
    if len(out) < min_rows:
        print(f"Not enough data to calculate indicators: {len(out)} rows (need {min_rows})")
        return out

    # ----------------- EMA -----------------
    try:
        out["ema_fast"] = ta.trend.EMAIndicator(close=out["close"], window=fast).ema_indicator()
        out["ema_slow"] = ta.trend.EMAIndicator(close=out["close"], window=slow).ema_indicator()
    except Exception as e:
        print(f"EMA calculation failed: {e}")
        out["ema_fast"] = np.nan
        out["ema_slow"] = np.nan

    # ----------------- ATR -----------------
    try:
        out["atr"] = ta.volatility.AverageTrueRange(
            high=out["high"], low=out["low"], close=out["close"], window=atr_period
        ).average_true_range()
    except Exception as e:
        print(f"ATR calculation failed: {e}")
        out["atr"] = np.nan

    # ----------------- ADX -----------------
    try:
        out["adx"] = ta.trend.ADXIndicator(
            high=out["high"], low=out["low"], close=out["close"], window=atr_period
        ).adx()
    except Exception as e:
        print(f"ADX calculation failed: {e}")
        out["adx"] = np.nan

    return out

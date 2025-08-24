# engine/datafeed.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import pandas_ta as ta

def candles_to_df(candles):
    """Angel returns [[ts, o, h, l, c, v], ...]. Convert to DataFrame with UTC index."""
    if not candles:
        return pd.DataFrame(columns=["open","high","low","close","volume"])
    df = pd.DataFrame(candles, columns=["ts","open","high","low","close","volume"]).astype({
        "open":float,"high":float,"low":float,"close":float,"volume":float
    })
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    return df

def add_indicators(df: pd.DataFrame, fast=12, slow=26, atr_period=14):
    out = df.copy()
    out["ema_fast"] = ta.ema(out["close"], length=fast)
    out["ema_slow"] = ta.ema(out["close"], length=slow)
    out["adx"] = ta.adx(high=out["high"], low=out["low"], close=out["close"], length=14)["ADX_14"]
    out["atr"] = ta.atr(high=out["high"], low=out["low"], close=out["close"], length=atr_period)
    out["returns"] = out["close"].pct_change()
    return out.dropna()

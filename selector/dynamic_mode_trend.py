# selectors/dynamic_mode_trend.py
import os
import json
from typing import Dict
import pandas as pd

HISTORY_FILE = "data/mode_history_trend.json"
MAX_HISTORY = 10  # number of past runs to smooth

def load_mode_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"last_mode": "swing", "scores": [], "atr_pct_history": []}
    return {"last_mode": "swing", "scores": [], "atr_pct_history": []}

def save_mode_history(last_mode: str, scores: list, atr_history: list):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    data = {
        "last_mode": last_mode,
        "scores": scores[-MAX_HISTORY:],
        "atr_pct_history": atr_history[-MAX_HISTORY:]
    }
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f)

def compute_index_trend_score(df: pd.DataFrame) -> tuple[float, float, float, float]:
    """
    Compute trend-based score using ADX, slope, ATR%, and momentum alignment
    Returns: trend_score, adx, slope, momentum_pct
    """
    if df is None or df.empty or "adx" not in df.columns or "atr" not in df.columns:
        return -1e9, 0, 0, 0

    atr_pct = (df["atr"].iloc[-1] / df["close"].iloc[-1]) * 100
    adx = df["adx"].iloc[-1]
    slope = (df["ema_fast"].iloc[-1] / df["ema_fast"].iloc[-5] - 1) * 100 if len(df) > 5 else 0
    # momentum: price change over last 5 candles
    momentum_pct = (df["close"].iloc[-1] / df["close"].iloc[-6] - 1) * 100 if len(df) > 6 else 0
    trend_score = 0.4 * adx + 0.3 * abs(slope) + 0.2 * atr_pct + 0.1 * abs(momentum_pct)
    return trend_score, adx, slope, momentum_pct

def choose_mode_trend(indices_dfs: Dict[str, pd.DataFrame]) -> str:
    """
    Choose mode based on trend strength, slope, ATR% volatility, and momentum alignment.
    Returns "intraday" or "swing".
    """
    history = load_mode_history()
    last_mode = history.get("last_mode", "swing")
    past_scores = history.get("scores", [])
    past_atr = history.get("atr_pct_history", [])

    current_scores = []
    current_atr = []

    for df in indices_dfs.values():
        score, adx, slope, momentum_pct = compute_index_trend_score(df)
        current_scores.append(score)
        atr_pct = (df["atr"].iloc[-1] / df["close"].iloc[-1]) * 100 if df is not None and not df.empty else 0
        current_atr.append(atr_pct)

    if not current_scores:
        return last_mode

    avg_score = sum(current_scores) / len(current_scores)
    avg_atr = sum(current_atr) / len(current_atr)

    # append to history
    past_scores.append(avg_score)
    past_atr.append(avg_atr)

    # adaptive thresholds
    atr_mean = sum(past_atr[-MAX_HISTORY:]) / len(past_atr[-MAX_HISTORY:])
    trend_threshold = max(0.5, atr_mean * 1.2)
    min_adx_for_intraday = 20
    min_slope_for_intraday = 0.1
    min_momentum_pct = 0.05  # require some aligned price movement

    # check trend + momentum for intraday
    intraday_ok = avg_score >= trend_threshold
    for df in indices_dfs.values():
        if df is None or df.empty or "adx" not in df.columns or "ema_fast" not in df.columns:
            continue
        adx = df["adx"].iloc[-1]
        slope = (df["ema_fast"].iloc[-1] / df["ema_fast"].iloc[-5] - 1) * 100 if len(df) > 5 else 0
        momentum_pct = (df["close"].iloc[-1] / df["close"].iloc[-6] - 1) * 100 if len(df) > 6 else 0
        # intraday requires trend, slope, and momentum to be aligned
        if adx < min_adx_for_intraday or abs(slope) < min_slope_for_intraday or abs(momentum_pct) < min_momentum_pct:
            intraday_ok = False

    mode = "intraday" if intraday_ok else "swing"

    save_mode_history(mode, past_scores, past_atr)
    return mode

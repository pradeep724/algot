# selector/auto_selector.py
from typing import List, Dict, Tuple
import os
import pandas as pd
from engine.datafeed import add_indicators
from engine.risk import default_sl_target

# ---------------- Safe helper ----------------
def safe_last(df: pd.DataFrame, col: str, default=0.0, n: int = 1) -> float:
    """
    Safely get the last value of a column, or nth-last value.
    Returns default if column missing or DataFrame too short.
    """
    if col not in df.columns or len(df) < n:
        return default
    return df[col].iloc[-n]

# ---------------- Scoring ----------------
def score_intraday(df: pd.DataFrame) -> float:
    if df.empty:
        return -1e9

    atrp = (safe_last(df, "atr") / safe_last(df, "close", default=1.0)) * 100
    adx = safe_last(df, "adx")
    mom = (safe_last(df, "ema_fast") - safe_last(df, "ema_slow")) / safe_last(df, "close", default=1.0) * 100
    vol = df["volume"].rolling(20).mean().iloc[-1] if "volume" in df.columns and len(df) >= 20 else 0

    # Weighted score: volatility (atr%), trend strength (adx), momentum, volume
    return 0.45 * atrp + 0.35 * adx + 0.15 * mom + 0.05 * (vol / 1e5)

def score_swing(df: pd.DataFrame) -> float:
    if df.empty:
        return -1e9

    adx = safe_last(df, "adx")
    slope = (safe_last(df, "ema_fast") / safe_last(df, "ema_fast", n=10, default=1.0) - 1.0) * 100
    trend_gap = (safe_last(df, "ema_fast") - safe_last(df, "ema_slow")) / safe_last(df, "close", default=1.0) * 100

    return 0.5 * adx + 0.3 * slope + 0.2 * trend_gap

# ---------------- Mode selection ----------------
def choose_mode_now(now_ist):
    hm = now_ist.hour * 100 + now_ist.minute
    return "intraday" if 915 <= hm <= 1530 else "swing"

# ---------------- Interval picker ----------------
def pick_preferred_intraday_interval(df_5m: pd.DataFrame, df_15m: pd.DataFrame, cfg: Dict) -> str:
    threshold = cfg.get("intraday_vol_threshold_pct", 0.35)

    if df_5m is None or df_15m is None or df_5m.empty:
        return "FIFTEEN_MINUTE"
    if df_15m.empty:
        return "FIVE_MINUTE"

    atr5p = (safe_last(df_5m, "atr") / safe_last(df_5m, "close", default=1.0)) * 100
    atr15p = (safe_last(df_15m, "atr") / safe_last(df_15m, "close", default=1.0)) * 100

    return "FIVE_MINUTE" if atr5p >= threshold else "FIFTEEN_MINUTE"

# ---------------- LLM re-rank (unchanged) ----------------
def llm_rerank(candidates: List[Tuple[str, float]], prompt_context: str, cfg: Dict) -> List[str]:
    if not cfg.get("enabled", False):
        return [s for s, _ in candidates]

    provider = cfg.get("provider", "openai")
    api_env = cfg.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.getenv(api_env, "")
    topk = cfg.get("max_symbols", 10)
    tops = candidates[:topk]
    symbols = [s for s, _ in tops]

    if not api_key:
        return symbols

    prompt_lines = [f"Rank these symbols from best to worst for {prompt_context}. Provide only the ranked list in CSV order.\n"]
    for s, sc in tops:
        prompt_lines.append(f"{s}: score={sc:.4f}")
    prompt = "\n".join(prompt_lines)

    try:
        if provider == "openai":
            try:
                import openai
            except Exception:
                return symbols
            openai.api_key = api_key
            model = cfg.get("model", "gpt-4o-mini")
            resp = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert quant trader. Rank symbols by short-term tradability and momentum."},
                    {"role": "user", "content": prompt}
                ],
                temperature=float(cfg.get("temperature", 0.2)),
                max_tokens=200
            )
            txt = resp["choices"][0]["message"]["content"].strip()
            out = []
            for part in txt.replace("\n", ",").split(","):
                token = part.strip().split()[0].strip()
                if token in symbols and token not in out:
                    out.append(token)
            if len(out) >= 1:
                return out
    except Exception:
        return symbols
    return symbols

# ---------------- Trade plan builder ----------------
def build_trade_plan(symbol: str, df: pd.DataFrame, cfg: Dict):
    if df is None or df.empty:
        return None
    price = float(safe_last(df, "close", default=0.0))
    atr = float(safe_last(df, "atr", default=max(0.25, price * 0.005)))
    atr_mult = cfg.get("strategy", {}).get("atr_mult", 2.0)
    rr = cfg.get("strategy", {}).get("rr", 2.0)
    min_stop = cfg.get("strategy", {}).get("min_stop_abs", 0.5)
    stop_price, target_price, stop_dist = default_sl_target(price, atr, atr_mult=atr_mult, rr=rr, min_stop_abs=min_stop)

    return dict(
        symbol=symbol,
        price=price,
        stop_price=stop_price,
        target_price=target_price,
        stop_dist=stop_dist,
        rr=rr
    )

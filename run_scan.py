"""
run_scan.py
------------
Scan your universe and auto-pick symbols for intraday or swing.
Builds trade plans with preferred timeframe, default SL and targets and qty.
- Fetches candles from AngelOne API (live) or from CSV (backtest mode).
- Stores candles and trade plans into CSVs for future backtesting.
- Automatically re-logins if session expires.
- Skips symbols with insufficient candles for indicator calculation.
- Dynamically selects trading mode based on multiple index trends.
"""

import os
import time
import random
import pandas as pd
from datetime import datetime, timedelta

from engine.utils import load_config, load_universe
from engine.datafeed import add_indicators, candles_to_df
from selector.auto_selector import (
    score_intraday,
    score_swing,
    pick_preferred_intraday_interval,
    llm_rerank,
    build_trade_plan,
    choose_mode_now,
)
from selector.dynamic_mode import choose_mode_dynamic
from engine.risk import position_size
from engine.broker_angel import AngelBroker


def fetch_history_for_interval(symbol, interval, cfg, broker, backtest=False, max_retries=5):
    """
    Fetch candles for given symbol/interval with caching + retry and auto re-login.
    Skips symbols with insufficient candles for indicator calculation.
    """
    tradingsymbol = symbol["tradingsymbol"]
    token = symbol.get("symboltoken", None)

    # Path for caching CSV
    data_dir = os.path.join("data", "candles")
    os.makedirs(data_dir, exist_ok=True)
    csv_path = os.path.join(data_dir, f"{tradingsymbol}_{interval}.csv")

    # Load from cache if available
    if backtest and os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path, parse_dates=["timestamp"], index_col="timestamp")
            if not df.empty:
                return df
        except Exception as e:
            print(f"Cache read error for {csv_path}: {e}")

    to_date = datetime.now()
    from_date = to_date - timedelta(days=30 if interval != "ONE_DAY" else 365)

    attempt = 0
    session_retry_done = False

    while attempt < max_retries:
        try:
            candles = broker.historical_candles(
                exchange="NSE",
                symbol=tradingsymbol,
                interval=interval,
                from_dt=from_date.strftime("%Y-%m-%d %H:%M"),
                to_dt=to_date.strftime("%Y-%m-%d %H:%M"),
            )
            df = candles_to_df(candles)

            if not df.empty:
                # Minimum rows needed for indicators
                MIN_CANDLES = max(cfg["strategy"]["fast"], cfg["strategy"]["slow"], cfg["strategy"]["atr_period"], 28)
                if len(df) < MIN_CANDLES:
                    print(f"Skipping {tradingsymbol} {interval}: only {len(df)} rows (need {MIN_CANDLES})")
                    return pd.DataFrame()
                df.to_csv(csv_path)
            return df

        except Exception as e:
            err_str = str(e).lower()
            if ("session" in err_str or "access" in err_str) and not session_retry_done:
                print(f"Session expired or access denied. Re-login and retry for {tradingsymbol}...")
                try:
                    broker._login()
                    session_retry_done = True
                    continue
                except Exception as login_e:
                    print(f"Re-login failed: {login_e}")

            wait_time = (2 ** attempt) + random.uniform(0, 1)
            print(f"Error fetching {tradingsymbol} {interval}: {e}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
            attempt += 1

    print(f"Failed to fetch {tradingsymbol} {interval} after {max_retries} retries.")
    return pd.DataFrame()


if __name__ == "__main__":
    cfg = load_config()
    universe = load_universe(cfg["run"]["universe_csv"])
    backtest_mode = cfg["run"].get("backtest", False)
    now = datetime.now()

    # Create broker instance
    broker = AngelBroker.get_instance(
        cfg["broker"]["api_key"],
        cfg["broker"]["client_id"],
        cfg["broker"]["password"],
        cfg["broker"]["totp_secret"],
    )

    # --- Dynamic Mode Selection ---
    index_symbols = [s for s in universe if s.get("is_index", False)]
    index_dfs = []

    for idx_sym in index_symbols:
        df = fetch_history_for_interval(idx_sym, "FIFTEEN_MINUTE", cfg, broker, backtest=backtest_mode)
        if not df.empty:
            df = add_indicators(df,
                                fast=cfg["strategy"]["fast"],
                                slow=cfg["strategy"]["slow"],
                                atr_period=cfg["strategy"]["atr_period"])
            index_dfs.append(df)

    if index_dfs:
        mode = choose_mode_dynamic(index_dfs)  # Accepts list of index DataFrames
    else:
        mode = choose_mode_now(now)  # Fallback to time-based mode

    print(f"Mode dynamically selected: {mode.upper()} at {now}, backtest={backtest_mode}")

    scored = []
    trade_plans = []

    for sym in universe:
        if mode == "intraday":
            df5 = fetch_history_for_interval(sym, "FIVE_MINUTE", cfg, broker, backtest=backtest_mode)
            if df5 is not None and not df5.empty:
                df5 = add_indicators(df5,
                                     fast=cfg["strategy"]["fast"],
                                     slow=cfg["strategy"]["slow"],
                                     atr_period=cfg["strategy"]["atr_period"])

            df15 = fetch_history_for_interval(sym, "FIFTEEN_MINUTE", cfg, broker, backtest=backtest_mode)
            if df15 is not None and not df15.empty:
                df15 = add_indicators(df15,
                                      fast=cfg["strategy"]["fast"],
                                      slow=cfg["strategy"]["slow"],
                                      atr_period=cfg["strategy"]["atr_period"])

            pref_interval = pick_preferred_intraday_interval(df5, df15, cfg["scan"])
            df = df5 if pref_interval == "FIVE_MINUTE" else df15
            score = score_intraday(df) if not df.empty else -1e9

        else:  # swing mode
            df = fetch_history_for_interval(sym, "ONE_DAY", cfg, broker, backtest=backtest_mode)
            if df is not None and not df.empty:
                df = add_indicators(df,
                                    fast=cfg["strategy"]["fast"],
                                    slow=cfg["strategy"]["slow"],
                                    atr_period=cfg["strategy"]["atr_period"])
            score = score_swing(df) if not df.empty else -1e9
            pref_interval = "ONE_DAY"

        if df is None or df.empty:
            continue

        scored.append((sym, float(score), pref_interval, df))

    # Sort and pick top-N
    top_n = cfg["scan"]["intraday_top_n"] if mode == "intraday" else cfg["scan"]["swing_top_n"]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_n]

    # Optional LLM-based re-rank
    top_symbols = llm_rerank([(s, sc) for s, sc, _, _ in top], prompt_context=f"mode={mode}", cfg=cfg["llm"])
    print("Top symbols selected:", [t[0] for t in top])

    # Build trade plans
    for sym, score, pref_interval, df in top:
        plan = build_trade_plan(sym, df, cfg)
        if plan:
            total_cap = cfg["run"]["capital"]
            reserved = cfg["run"].get("reserved_ratio", 0.20)
            qty = position_size(total_cap,
                                plan["price"],
                                cfg["run"]["risk_per_trade"],
                                plan["stop_dist"],
                                reserved_ratio=reserved)
            plan["qty"] = qty
            plan["interval"] = pref_interval
            plan["score"] = score
            plan["timestamp"] = now.strftime("%Y-%m-%d %H:%M")
            trade_plans.append(plan)

    print("Trade plans (top):")
    for p in trade_plans:
        print(p)

    # Save trade plans to CSV
    out_dir = os.path.join("data", "trade_plans")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{now.strftime('%Y%m%d_%H%M')}_{mode}.csv")
    pd.DataFrame(trade_plans).to_csv(out_file, index=False)
    print(f"Trade plans saved to {out_file}")

# run_scan.py
"""Scan your universe and auto-pick symbols for intraday or swing.
Builds trade plans with preferred timeframe, default SL and targets and qty.
This does NOT place orders; it's a planning/scanning tool. Implement broker fetch to make it live.
"""
from datetime import datetime
import pandas as pd
from engine.utils import load_config, load_universe
from engine.datafeed import add_indicators, candles_to_df
from selector.auto_selector import score_intraday, score_swing, choose_mode_now, pick_preferred_intraday_interval, llm_rerank, build_trade_plan

# Placeholder: implement this using AngelBroker.getCandleData and engine.datafeed.candles_to_df
def fetch_history_for_interval(symbol, interval, cfg):
    """Return DataFrame with columns open, high, low, close, volume indexed by timestamp.
    interval: 'FIVE_MINUTE', 'FIFTEEN_MINUTE', 'ONE_DAY'
    Currently a placeholder: return empty DataFrame.
    Replace with AngelBroker.historical_candles -> candles_to_df -> add_indicators
    """
    return pd.DataFrame()

if __name__ == "__main__":
    cfg = load_config()
    universe = load_universe(cfg["run"]["universe_csv"])
    now = datetime.now()
    mode = choose_mode_now(now)
    print(f"Mode now: {mode.upper()} at {now}")

    scored = []
    trade_plans = []

    for sym in universe:
        if mode == "intraday":
            df5 = fetch_history_for_interval(sym, "FIVE_MINUTE", cfg)
            if df5 is not None and not df5.empty:
                df5 = add_indicators(df5, fast=cfg["strategy"]["fast"], slow=cfg["strategy"]["slow"], atr_period=cfg["strategy"]["atr_period"])
            df15 = fetch_history_for_interval(sym, "FIFTEEN_MINUTE", cfg)
            if df15 is not None and not df15.empty:
                df15 = add_indicators(df15, fast=cfg["strategy"]["fast"], slow=cfg["strategy"]["slow"], atr_period=cfg["strategy"]["atr_period"])

            pref_interval = pick_preferred_intraday_interval(df5, df15, cfg["scan"])
            df = df5 if pref_interval == "FIVE_MINUTE" else df15
            score = score_intraday(df) if not df.empty else -1e9

        else:  # swing
            df = fetch_history_for_interval(sym, "ONE_DAY", cfg)
            if df is not None and not df.empty:
                df = add_indicators(df, fast=cfg["strategy"]["fast"], slow=cfg["strategy"]["slow"], atr_period=cfg["strategy"]["atr_period"])
            score = score_swing(df) if not df.empty else -1e9
            pref_interval = "ONE_DAY"

        if df is None or df.empty:
            continue

        scored.append((sym, float(score), pref_interval, df))

    # sort and pick top-N
    top_n = cfg["scan"]["intraday_top_n"] if mode == "intraday" else cfg["scan"]["swing_top_n"]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_n]

    # optional LLM-based re-rank (cfg['llm'])
    top_symbols = llm_rerank([(s, sc) for s, sc, _, _ in top], prompt_context=f"mode={mode}", cfg=cfg["llm"])
    print("Top symbols selected:", [t[0] for t in top])

    # build trade plans for top symbols using their df and default SL/Targets
    for sym, score, pref_interval, df in top:
        plan = build_trade_plan(sym, df, cfg)
        if plan:
            # compute quantity using engine.risk.position_size
            from engine.risk import position_size
            total_cap = cfg["run"]["capital"]
            reserved = cfg["run"].get("reserved_ratio", 0.20)
            qty = position_size(total_cap, plan["price"], cfg["run"]["risk_per_trade"], plan["stop_dist"], reserved_ratio=reserved)
            plan["qty"] = qty
            plan["interval"] = pref_interval
            trade_plans.append(plan)

    print("Trade plans (top):")
    for p in trade_plans:
        print(p)

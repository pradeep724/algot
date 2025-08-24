import os
import pandas as pd
from datetime import datetime

TRADE_PLAN_DIR = "data/trade_plans"
CANDLE_DIR = "data/candles"
PAPER_TRADE_DIR = "data/paper_trades"
os.makedirs(PAPER_TRADE_DIR, exist_ok=True)

def load_trade_plans():
    plans = []
    for f in os.listdir(TRADE_PLAN_DIR):
        if f.endswith(".csv"):
            df = pd.read_csv(os.path.join(TRADE_PLAN_DIR, f))
            plans.append(df)
    return pd.concat(plans, ignore_index=True) if plans else pd.DataFrame()

def simulate_trade_backtest(plan, candles_df):
    entry, stop, target = plan["price"], plan["stop_price"], plan["target_price"]
    for ts, row in candles_df.iterrows():
        if row["high"] >= target:
            return "Target Hit", target-entry, ts
        if row["low"] <= stop:
            return "SL Hit", stop-entry, ts
    return "Open", 0, candles_df.index[-1] if not candles_df.empty else None

def run_backtest():
    plans_df = load_trade_plans()
    if plans_df.empty:
        print("No trade plans found!")
        return

    results = []
    for _, plan in plans_df.iterrows():
        sym = plan["symbol"]
        candle_path = os.path.join(CANDLE_DIR, f"{sym}_{plan['interval']}.csv")
        if os.path.exists(candle_path):
            df = pd.read_csv(candle_path, parse_dates=["timestamp"], index_col="timestamp")
            status, pnl, hit_time = simulate_trade_backtest(plan, df)
        else:
            status, pnl, hit_time = "No Data", 0, None

        record = plan.to_dict()
        record.update({"status": status, "pnl": pnl, "hit_time": hit_time})
        results.append(record)

    out_file = os.path.join(PAPER_TRADE_DIR, f"backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    pd.DataFrame(results).to_csv(out_file, index=False)
    print(f"Backtest results saved to {out_file}")

if __name__ == "__main__":
    run_backtest()

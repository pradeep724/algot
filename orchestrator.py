import os
import pandas as pd
from datetime import datetime, timedelta

from engine.utils import load_config
from engine.broker_angel import AngelBroker
from run_scan import fetch_history_for_interval
from paper_trade import execute_paper_trades
from engine.analysis import analyze_backtest

# Directories
TRADE_PLAN_DIR = "data/trade_plans"
BACKTEST_DIR = "data/backtests"
os.makedirs(TRADE_PLAN_DIR, exist_ok=True)
os.makedirs(BACKTEST_DIR, exist_ok=True)


def run_scan_all_symbols(scan_date, cfg, broker):
    """Run scan for all configured symbols on given date"""
    print(cfg)
    symbols = cfg["symbols"]  # e.g. list of dicts like [{"tradingsymbol": "Nifty IT", "symboltoken": 99926008}, ...]
    all_plans = []

    for sym in symbols:
        try:
            plans = fetch_history_for_interval(sym, scan_date, cfg, broker)  # <-- now passing symbol
            if plans:
                all_plans.extend(plans)
        except Exception as e:
            print(f"⚠️ Scan failed for {sym}: {e}")
    return all_plans


def orchestrate_live(cfg, broker):
    """Run live orchestrator: scan → trade plan → paper trade"""
    now = datetime.now()
    mode = "LIVE"

    print(f"🔎 Running live scan at {now}")
    top_trades = run_scan_all_symbols(now, cfg, broker)

    if not top_trades:
        print("⚠️ No trades found")
        return pd.DataFrame()

    # Save trade plan
    plan_file = os.path.join(TRADE_PLAN_DIR, f"{now.strftime('%Y%m%d_%H%M')}_swing.csv")
    pd.DataFrame(top_trades).to_csv(plan_file, index=False)
    print(f"✅ Trade plan saved → {plan_file}")

    # Simulate trades
    results = execute_paper_trades(top_trades, cfg, broker, now, mode, backtest=False)
    return results


def orchestrate_backtest(cfg, broker):
    """Run backtest over date range from config"""
    start = datetime.strptime(cfg["run"]["backtest_start"], "%Y-%m-%d")
    end = datetime.strptime(cfg["run"]["backtest_end"], "%Y-%m-%d")
    mode = "BACKTEST"

    print(f"⏳ Running backtest from {start.date()} → {end.date()}")
    all_results = []

    cur = start
    while cur <= end:
        print(f"🔄 Backtesting {cur.date()}")

        # Scan all symbols
        top_trades = run_scan_all_symbols(cur, cfg, broker)
        if not top_trades:
            cur += timedelta(days=1)
            continue

        # Save trade plan
        plan_file = os.path.join(TRADE_PLAN_DIR, f"{cur.strftime('%Y%m%d')}_swing.csv")
        pd.DataFrame(top_trades).to_csv(plan_file, index=False)

        # Simulate trades
        results = execute_paper_trades(top_trades, cfg, broker, cur, mode, backtest=True)
        if not results.empty:
            all_results.append(results)

        cur += timedelta(days=1)

    # Aggregate results
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        out_file = os.path.join(BACKTEST_DIR, f"backtest_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.csv")
        final_df.to_csv(out_file, index=False)
        print(f"✅ Backtest results saved → {out_file}")

        analyze_backtest(final_df)
        return final_df
    else:
        print("⚠️ No backtest results")
        return pd.DataFrame()


if __name__ == "__main__":
    cfg = load_config()
    broker = AngelBroker.get_instance(
        cfg["broker"]["api_key"],
        cfg["broker"]["client_id"],
        cfg["broker"]["password"],
        cfg["broker"]["totp_secret"]
    )

    if cfg["run"].get("backtest", False):
        orchestrate_backtest(cfg, broker)
    else:
        orchestrate_live(cfg, broker)

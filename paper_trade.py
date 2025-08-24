import os
import pandas as pd
import ast
from datetime import datetime
from engine.datafeed import candles_to_df, add_indicators
from run_scan import fetch_history_for_interval
from engine.broker_angel import AngelBroker

TRADE_PLAN_DIR = "data/trade_plans"
PAPER_TRADE_DIR = "data/paper_trades"
os.makedirs(PAPER_TRADE_DIR, exist_ok=True)


def load_trade_plans():
    """Load all trade plans CSVs into a single DataFrame"""
    plans = []
    for f in os.listdir(TRADE_PLAN_DIR):
        if f.endswith(".csv"):
            df = pd.read_csv(os.path.join(TRADE_PLAN_DIR, f),quotechar='"',escapechar='\\', quoring=csv.QUOTE_MINIMAL)
            plans.append(df)
    return pd.concat(plans, ignore_index=True) if plans else pd.DataFrame()


def normalize_symbol_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame always has a 'symbol' column."""
    if "symbol" not in df.columns:
        if "tradingsymbol" in df.columns:
            df = df.rename(columns={"tradingsymbol": "symbol"})
        elif "ticker" in df.columns:
            df = df.rename(columns={"ticker": "symbol"})
        else:
            raise KeyError(
                f"No 'symbol' column found. Available columns: {df.columns.tolist()}"
            )
    return df


def clean_symbol_column(df: pd.DataFrame) -> pd.DataFrame:
    """Parse stringified dicts in 'symbol' into tradingsymbol + symboltoken."""
    if "symbol" in df.columns:
        def parse_symbol(val):
            if isinstance(val, str) and val.startswith("{"):
                try:
                    d = ast.literal_eval(val)
                    return d.get("tradingsymbol", val), d.get("symboltoken", None)
                except Exception:
                    return val, None
            return val, None

        parsed = df["symbol"].apply(parse_symbol)
        df["symbol"] = parsed.apply(lambda x: x[0])
        df["symboltoken"] = parsed.apply(lambda x: x[1])
    return df


def simulate_trade(plan, last_price):
    """Determine if SL or Target is hit"""
    entry, stop, target = plan["price"], plan["stop_price"], plan["target_price"]
    if last_price >= target:
        return "Target Hit", target - entry
    elif last_price <= stop:
        return "SL Hit", stop - entry
    return "Open", 0.0


def execute_paper_trades(top_trades=None, cfg=None, broker=None, now=None, mode=None, backtest=False):
    """
    Simulate paper trades for all top trades (from orchestrator) or from trade_plans directory.
    """
    # Handle input
    if top_trades is None:
        plans_df = load_trade_plans()
    elif isinstance(top_trades, pd.DataFrame):
        plans_df = top_trades
    
    elif isinstance(top_trades, list):
      if len(top_trades) > 0 and isinstance(top_trades[0], tuple):
        records = []
        for sym_info, score, interval, candles in top_trades:
            last_price = float(candles["close"].iloc[-1]) if not candles.empty else None

            # define risk/reward levels (can be tuned)
            stop_dist = last_price * 0.03  # 3% stop loss
            stop_price = last_price - stop_dist
            target_price = last_price + (2 * stop_dist)  # RR = 2

            records.append({
                "symbol": sym_info.get("tradingsymbol"),
                "symboltoken": sym_info.get("symboltoken"),
                "score": score,
                "interval": interval,
                "price": last_price,
                "stop_price": stop_price,
                "target_price": target_price,
                "candles": candles
            })
        plans_df = pd.DataFrame(records)
      else:
        plans_df = pd.DataFrame(top_trades)
    else:
        raise ValueError(f"Unsupported top_trades type: {type(top_trades)}")

    if plans_df.empty:
        print("⚠️ No trade plans found!")
        return pd.DataFrame()

    # Normalize & clean
    plans_df = normalize_symbol_column(plans_df)
    plans_df = clean_symbol_column(plans_df)

    # Debug preview
    print(f"📊 Loaded {len(plans_df)} trade plans. Columns: {plans_df.columns.tolist()}")
    print("🔎 First row parsed:", plans_df.iloc[0].to_dict())

    # Load config & broker if not passed
    if cfg is None:
        from engine.utils import load_config
        cfg = load_config()

    if broker is None:
        broker = AngelBroker.get_instance(
            cfg["broker"]["api_key"],
            cfg["broker"]["client_id"],
            cfg["broker"]["password"],
            cfg["broker"]["totp_secret"]
        )

    if now is None:
        now = datetime.now()

    results = []

    for _, plan in plans_df.iterrows():
        sym = {"tradingsymbol": plan["symbol"], "symboltoken": plan.get("symboltoken", None)}
        interval = plan.get("interval", "FIVE_MINUTE")

        # Fetch live or historical candles
        df = fetch_history_for_interval(sym, interval, cfg, broker, backtest=backtest)
        if df.empty:
            last_price = plan["price"]
        else:
            last_price = float(df["close"].iloc[-1])

        status, pnl = simulate_trade(plan, last_price)

        record = plan.to_dict()
        record.update({
            "status": status,
            "pnl": pnl,
            "last_price": last_price,
            "hit_time": now,
            "mode": mode or "N/A"
        })
        results.append(record)

    # Save results
    out_file = os.path.join(PAPER_TRADE_DIR, f"paper_trades_{now.strftime('%Y%m%d_%H%M')}.csv")
    pd.DataFrame(results).to_csv(out_file, index=False)
    print(f"✅ Paper trading results saved to {out_file}")

    return pd.DataFrame(results)


if __name__ == "__main__":
    from engine.utils import load_config

    cfg = load_config()
    broker = AngelBroker.get_instance(
        cfg["broker"]["api_key"],
        cfg["broker"]["client_id"],
        cfg["broker"]["password"],
        cfg["broker"]["totp_secret"]
    )

    execute_paper_trades(cfg=cfg, broker=broker, backtest=cfg["run"].get("backtest", False))

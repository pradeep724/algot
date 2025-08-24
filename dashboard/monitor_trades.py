# monitor_trades.py
import pandas as pd
import time
from engine.broker_angel import AngelBroker
from engine.datafeed import candles_to_df
import os

# Config
TRADE_PLAN_CSV = "data/trade_plans/latest.csv"  # your latest trade plan CSV
UPDATE_INTERVAL = 30  # seconds between updates

# Broker instance (replace with your credentials)
broker = AngelBroker.get_instance(
    api_key="YOUR_API_KEY",
    client_id="YOUR_CLIENT_ID",
    password="YOUR_PASSWORD",
    totp_secret="YOUR_TOTP_SECRET"
)

def fetch_ltp(symbol):
    """Fetch latest price. For backtest, you can load last candle close."""
    try:
        return broker.get_ltp(symbol)
    except Exception:
        return None

def check_status(row):
    if pd.isna(row['ltp']):
        return 'N/A'
    if row['ltp'] <= row['stop_price']:
        return 'STOP_LOSS_HIT'
    elif row['ltp'] >= row['target_price']:
        return 'TARGET_HIT'
    else:
        return 'ACTIVE'

while True:
    if not os.path.exists(TRADE_PLAN_CSV):
        print(f"No trade CSV found at {TRADE_PLAN_CSV}")
        time.sleep(UPDATE_INTERVAL)
        continue

    from glob import glob

    csv_files = glob(os.path.join("../data/trade_plans", "*.csv"))
    if not csv_files:
      print("No trade CSV found.")
      continue

    trades = pd.concat([pd.read_csv(f) for f in csv_files], ignore_index=True)

   # trades = pd.read_csv(TRADE_PLAN_CSV)
    
    ltp_list = []
    for idx, row in trades.iterrows():
        ltp = fetch_ltp(row['symbol'])
        ltp_list.append(ltp)

    trades['ltp'] = ltp_list
    trades['status'] = trades.apply(check_status, axis=1)
    trades['pnl'] = (trades['ltp'] - trades['price']) * trades['qty']

    # Save to monitoring CSV
    os.makedirs("data/trade_monitor", exist_ok=True)
    monitor_file = "data/trade_monitor/latest_status.csv"
    trades.to_csv(monitor_file, index=False)
    print(trades[['symbol','price','ltp','stop_price','target_price','qty','status','pnl']])

    time.sleep(UPDATE_INTERVAL)

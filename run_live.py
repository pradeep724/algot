# run_live.py
"""Live loop skeleton: chooses mode, scans symbols, and (optionally) places orders.
Complete the Angel One token lookup and candle/quote fetching before using live trading.

ALWAYS PAPER-TRADE FIRST.

"""
import time
from datetime import datetime
from engine.utils import load_config, load_universe
from selector.auto_selector import choose_mode_now
# from engine.broker_angel import AngelBroker, Order  # enable after configuring

def within_market_hours(t: datetime) -> bool:
    hm = t.hour*100 + t.minute
    return 915 <= hm <= 1530

if __name__ == "__main__":
    cfg = load_config()
    # broker = AngelBroker(cfg["angel_one"]["api_key"], cfg["angel_one"]["client_code"], cfg["angel_one"]["password"], cfg["angel_one"]["totp_secret"])
    universe = load_universe(cfg["run"]["universe_csv"])

    while True:
        now = datetime.now()
        mode = choose_mode_now(now)
        print(f"[{now}] MODE: {mode}")
        if mode == "intraday" and within_market_hours(now):
            print("Run your intraday scan + signals here and place orders if conditions match.")
        else:
            print("Run your end-of-day swing scan / updates here.")
        time.sleep(60)

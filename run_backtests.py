import os
import yaml
import pandas as pd
from logging import getLogger, StreamHandler, FileHandler, Formatter

from core.regime_detector import RegimeDetector
from core.strategy_router import StrategyRouter

# Setup logger
logger = getLogger("Backtester")
logger.setLevel("INFO")
ch = StreamHandler()
fh = FileHandler("backtester.log")
fmt = Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(fmt)
fh.setFormatter(fmt)
logger.addHandler(ch)
logger.addHandler(fh)

def load_config(path="config.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)

def load_historical_df(instrument):
    filename = f"data/{instrument}_historical.csv"
    if os.path.isfile(filename):
        return pd.read_csv(filename, index_col='Timestamp', parse_dates=True)
    else:
        logger.warning(f"No data for {instrument}: {filename}")
        return None

def backtest_instrument(cfg, instrument, df, regime_detector, strategy_router):
    trades = []
    min_bars = cfg['indicators']['donchian_period'] + 20
    n = len(df)
    
    for i in range(min_bars, n):
        lookback_df = df.iloc[:i+1]
        hist_window = lookback_df[-60:] # Use last 60 days for context
        
        # Detect regime from backwards-looking data
        regime = regime_detector.detect_regime(
            hist_window.tail(30).to_dict('records'), # tailored for your RegimeDetector
            {'value': 18},  # pass dummy VIX for now; refactor to use real VIX if you extract it
            {'advance_decline_ratio': 1.0} # pass dummy market breadth
        )
        # Choose strategy and generate signal
        live_data = {"instrument": instrument}
        signal = strategy_router.generate_signal(regime, lookback_df, live_data)
        
        # Simple backtester logic: open@signal, close after 5 bars or opposite signal
        currow = lookback_df.iloc[-1]
        if trades and 'exit_date' not in trades[-1]:
            days_open = (currow.name - trades[-1]['entry_date']).days
            if days_open >= 5 or (signal and signal['direction'] != trades[-1]["direction"]):
                entry_px = trades[-1]['entry_price']
                pnl = (currow['Close'] - entry_px) if trades[-1]['direction'] == 'bullish' else (entry_px - currow['Close'])
                trades[-1].update({
                    'exit_date': currow.name,
                    'exit_price': currow['Close'],
                    'pnl': pnl
                })
                logger.info(f"{instrument}: Close {trades[-1]['direction']} @ {currow['Close']:.2f}, PnL={pnl:.2f}")
        if not trades or ('exit_date' in trades[-1]):
            if signal and signal.get('direction'):
                trades.append({
                    'entry_date': currow.name,
                    'entry_price': currow['Close'],
                    'direction': signal['direction']
                })
                logger.info(f"{instrument}: Open {signal['direction']} @ {currow['Close']:.2f}")
    return trades

def main():
    cfg = load_config()
    regime_detector = RegimeDetector(cfg)
    strategy_router = StrategyRouter(cfg)
    all_results = {}

    for instrument in cfg['universe']:
        df = load_historical_df(instrument)
        if df is not None:
            trades = backtest_instrument(cfg, instrument, df, regime_detector, strategy_router)
            resdf = pd.DataFrame(trades)
            if not resdf.empty:
                resdf.to_csv(f"backtest_results_{instrument}.csv")
                logger.info(f"Results for {instrument}: {resdf.shape[0]} trades")

if __name__ == "__main__":
    main()

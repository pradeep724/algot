import os
import yaml
import pandas as pd
from logging import getLogger, StreamHandler, FileHandler, Formatter

from core.regime_detector import RegimeDetector
from core.strategy_router import StrategyRouter

# Setup logger
logger = getLogger("Backtester")
logger.setLevel("DEBUG")  # Changed to DEBUG for more detail
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
        df = pd.read_csv(filename, index_col='Timestamp', parse_dates=True)
        logger.info(f"Loaded {len(df)} rows of data for {instrument}")
        return df
    else:
        logger.warning(f"No data for {instrument}: {filename}")
        return None

def backtest_instrument(cfg, instrument, df, regime_detector, strategy_router):
    logger.info(f"🚀 Starting backtest for {instrument} with {len(df)} total bars")
    
    trades = []
    min_bars = cfg['indicators']['donchian_period'] + 20
    n = len(df)
    
    logger.info(f"Backtest will run from bar {min_bars} to {n-1} ({n-min_bars} bars)")
    
    for i in range(min_bars, n):
        lookback_df = df.iloc[:i+1]
        hist_window = lookback_df[-60:] # Use last 60 days for context
        
        # Detect regime from backwards-looking data
        regime = regime_detector.detect_regime(
            hist_window.tail(30).to_dict('records'),
            {'value': 18},  # pass dummy VIX for now
            {'advance_decline_ratio': 1.0} # pass dummy market breadth
        )
        
        # Choose strategy and generate signal
        live_data = {"instrument": instrument}
        signal = strategy_router.generate_signal(regime, lookback_df, live_data)
        
        currow = lookback_df.iloc[-1]
        
        # ENHANCED DEBUGGING
        logger.debug(f"Bar {i}: Date={currow.name}, Price={currow['Close']:.2f}, Regime={regime}")
        logger.info(f"📊 Signal at {currow.name} for {instrument}: {signal}")
        
        # Track trades state before processing
        trades_before = len(trades)
        open_trade_exists = trades and 'exit_date' not in trades[-1]
        
        logger.debug(f"Trades before processing: {trades_before}, Open trade exists: {open_trade_exists}")
        
        # Exit logic for existing open trade
        if trades and 'exit_date' not in trades[-1]:
            days_open = (currow.name - trades[-1]['entry_date']).days
            should_exit = days_open >= 5 or (signal and signal.get('direction') != trades[-1]["direction"])
            
            logger.debug(f"Open trade check: days_open={days_open}, should_exit={should_exit}")
            
            if should_exit:
                entry_px = trades[-1]['entry_price']
                pnl = (currow['Close'] - entry_px) if trades[-1]['direction'] == 'bullish' else (entry_px - currow['Close'])
                trades[-1].update({
                    'exit_date': currow.name,
                    'exit_price': currow['Close'],
                    'pnl': pnl
                })
                logger.info(f"✅ {instrument}: CLOSED {trades[-1]['direction']} @ {currow['Close']:.2f}, PnL={pnl:.2f}")
        
        # Entry logic for new trade
        can_enter_new_trade = not trades or ('exit_date' in trades[-1])
        has_valid_signal = signal and signal.get('direction')
        
        logger.debug(f"Can enter new trade: {can_enter_new_trade}, Has valid signal: {has_valid_signal}")
        
        if can_enter_new_trade and has_valid_signal:
            new_trade = {
                'entry_date': currow.name,
                'entry_price': currow['Close'],
                'direction': signal['direction']
            }
            trades.append(new_trade)
            logger.info(f"🔥 {instrument}: OPENED {signal['direction']} @ {currow['Close']:.2f}")
            logger.debug(f"New trade added: {new_trade}")
        
        # Log trades count after processing
        logger.debug(f"Trades after processing: {len(trades)}")
    
    logger.info(f"🏁 Backtest completed for {instrument}. Total trades: {len(trades)}")
    
    # Log trade summary
    if trades:
        logger.info(f"Trade summary for {instrument}:")
        for idx, trade in enumerate(trades):
            logger.info(f"  Trade {idx+1}: {trade}")
    else:
        logger.warning(f"❌ NO TRADES GENERATED for {instrument}")
    
    return trades

def main():
    logger.info("🚀 Starting ProTraderBot Backtest System")
    
    cfg = load_config()
    regime_detector = RegimeDetector(cfg)
    strategy_router = StrategyRouter(cfg)
    all_results = {}

    instruments = list(cfg['universe'].keys())
    logger.info(f"Processing {len(instruments)} instruments: {instruments}")

    for instrument in instruments:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {instrument}")
        logger.info(f"{'='*50}")
        
        df = load_historical_df(instrument)
        if df is None:
            logger.error(f"Skipping {instrument} - no data loaded")
            continue
            
        trades = backtest_instrument(cfg, instrument, df, regime_detector, strategy_router)
        
        # Enhanced CSV saving with debugging
        logger.info(f"📁 Attempting to save results for {instrument}...")
        
        if trades and len(trades) > 0:
            try:
                df_trades = pd.DataFrame(trades)
                filename = f"results/backtest_results_{instrument}.csv"
                df_trades.to_csv(filename, index=False)
                logger.info(f"✅ SAVED: {filename} with {len(trades)} trades")
                logger.info(f"File size: {os.path.getsize(filename)} bytes")
                all_results[instrument] = df_trades
            except Exception as e:
                logger.error(f"❌ Error saving CSV for {instrument}: {e}")
        else:
            logger.warning(f"❌ No trades to save for {instrument} - CSV not created")
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"BACKTEST SUMMARY")
    logger.info(f"{'='*60}")
    for instrument in instruments:
        if instrument in all_results:
            logger.info(f"{instrument}: {len(all_results[instrument])} trades saved")
        else:
            logger.info(f"{instrument}: No trades generated")
    
    logger.info("Backtest completed!")

if __name__ == "__main__":
    main()

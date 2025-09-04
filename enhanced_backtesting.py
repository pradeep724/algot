import numpy as np
import pandas as pd
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
import importlib
import sys

# ---------------- Data Structures ---------------- #

@dataclass
class TradingSignal:
    timestamp: datetime
    symbol: str
    strategy: str
    signal_type: str  # 'BUY' or 'SELL'
    strength: float
    entry_price: float
    target_price: float
    stop_loss: float
    position_size: int
    expected_pnl: float
    risk_reward_ratio: float
    confidence: float
    market_regime: str
    reasons: str


@dataclass
class Trade:
    signal: TradingSignal
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: str = ""
    pnl: float = 0.0
    status: str = "OPEN"
    holding_period: int = 0


# ---------------- Exit Handler ---------------- #

class ExitHandler:
    def __init__(self, config):
        self.config = config

    def evaluate_exit(self, trade, df, current_idx, market_regime):
        """Check all exit conditions for a given trade at current index."""
        exits = []
        current_price = df['Close'].iloc[current_idx]
        current_time = df.index[current_idx]
        slippage = float(self.config.get("backtesting", {}).get("slippage", 0.0))

        holding_days = (current_time - trade.entry_time).days
        strat_cfg = self.config.get("strategies", {}).get(trade.signal.strategy, {})
        max_hold = int(strat_cfg.get("max_holding_period", 5))

        # --------- 1. Hard Stop Loss / Take Profit --------- #
        if trade.signal.signal_type == "BUY":
            if current_price <= trade.signal.stop_loss:
                exits.append(("STOP_LOSS", current_price * (1 - slippage)))
            elif current_price >= trade.signal.target_price:
                exits.append(("TARGET", current_price * (1 - slippage)))
        else:
            if current_price >= trade.signal.stop_loss:
                exits.append(("STOP_LOSS", current_price * (1 + slippage)))
            elif current_price <= trade.signal.target_price:
                exits.append(("TARGET", current_price * (1 + slippage)))

        # --------- 2. Trailing Stop Loss --------- #
        if current_idx > 15:
            atr = df['High'].iloc[current_idx-14:current_idx].max() - df['Low'].iloc[current_idx-14:current_idx].min()
            tsl_mult = strat_cfg.get("trailing_stop_atr_mult", 1.5)
            if trade.signal.signal_type == "BUY":
                new_sl = current_price - atr * tsl_mult
                if new_sl > trade.signal.stop_loss:
                    trade.signal.stop_loss = new_sl
            else:
                new_sl = current_price + atr * tsl_mult
                if new_sl < trade.signal.stop_loss:
                    trade.signal.stop_loss = new_sl

        # --------- 3. Partial Profit Booking --------- #
        partial_level = strat_cfg.get("partial_profit_pct", 0.02)
        if partial_level:
            target1 = trade.entry_price * (1 + partial_level if trade.signal.signal_type == "BUY" else 1 - partial_level)
            if ((trade.signal.signal_type == "BUY" and current_price >= target1) or
                (trade.signal.signal_type == "SELL" and current_price <= target1)):
                if not hasattr(trade, "partial_exit_done"):
                    trade.partial_exit_done = True
                    exits.append(("PARTIAL_EXIT", current_price))

        # --------- 4. Time-based Exit --------- #
        if holding_days >= max_hold:
            adj = (1 - slippage) if trade.signal.signal_type == "BUY" else (1 + slippage)
            exits.append(("TIME_EXIT", current_price * adj))

        # --------- 5. Volatility / Regime Exit --------- #
        if market_regime["regime"] == "high_volatility":
            adj = (1 - slippage) if trade.signal.signal_type == "BUY" else (1 + slippage)
            exits.append(("REGIME_EXIT", current_price * adj))

        return exits[0] if exits else None


# ---------------- Enhanced Backtester ---------------- #

class EnhancedBacktester:
    def __init__(self, config: Dict):
        self.config = config
        self.strategies = []
        self.trades: List[Trade] = []
        self.daily_pnl: Dict[str, float] = {}
        self.portfolio_value = config.get('risk_management', {}).get('account_capital', 500000)
        self.initial_capital = self.portfolio_value
        self.exit_handler = ExitHandler(config)
        self.load_strategies()

    def load_strategies(self):
        strategies_config = self.config.get('strategies', {})
        strategy_classes = {
            'volatility_breakout': 'VolatilityBreakoutStrategy',
            'rsi_mean_reversion': 'RSIMeanReversionStrategy',
            'bollinger_band_reversal': 'BollingerBandReversalStrategy',
            'moving_average_crossover': 'MovingAverageCrossoverStrategy',
        }

        for strategy_name, class_name in strategy_classes.items():
            if strategies_config.get(strategy_name, {}).get('enabled', False):
                try:
                    if 'strategies' not in sys.path:
                        sys.path.insert(0, 'strategies')
                    module = importlib.import_module(strategy_name)
                    strategy_class = getattr(module, class_name)
                    strategy_instance = strategy_class(self.config)
                    self.strategies.append(strategy_instance)
                    print(f"✅ Loaded strategy: {strategy_name}")
                except Exception as e:
                    print(f"❌ Failed to load strategy {strategy_name}: {e}")

    # -------- Risk Helpers -------- #
    def _get_cost_rates(self):
        bt = self.config.get('backtesting', {})
        commission = float(bt.get('commission', 0.0))
        slippage = float(bt.get('slippage', 0.0))
        return commission, slippage

    def _position_size_from_risk(self, entry_price, stop_loss_price):
        rm = self.config.get('risk_management', {})
        capital = float(rm.get('account_capital', self.initial_capital))
        max_risk_per_trade = float(rm.get('max_risk_per_trade', 0.005))
        risk_rupees = capital * max_risk_per_trade

        if entry_price <= 0 or stop_loss_price is None or stop_loss_price == entry_price:
            return 0

        per_share_risk = abs(entry_price - stop_loss_price)
        if per_share_risk <= 0:
            return 0

        return int(risk_rupees // per_share_risk)

    # -------- Market Regime -------- #
    def detect_market_regime(self, df, current_idx):
        if current_idx < 20:
            return {'regime': 'normal', 'volatility_percentile': 50}

        recent_returns = df['Close'].iloc[current_idx-20:current_idx].pct_change().dropna()
        volatility = recent_returns.std() * np.sqrt(252)

        if current_idx >= 50:
            long_vol = df['Close'].iloc[current_idx-50:current_idx].pct_change().rolling(20).std() * np.sqrt(252)
            vol_percentile = (long_vol.iloc[-1] > long_vol).mean() * 100
        else:
            vol_percentile = 50

        regime = 'high_volatility' if vol_percentile > 80 else 'low_volatility' if vol_percentile < 20 else 'normal'
        return {'regime': regime, 'volatility_percentile': vol_percentile}

    # -------- Backtest Loop -------- #
    def run_enhanced_backtest(self, data_dict: Dict[str, pd.DataFrame], start_date=None, end_date=None):
        print(f"🚀 Starting Backtest for {list(data_dict.keys())}")
        self.trades.clear()
        self.daily_pnl.clear()
        self.portfolio_value = self.initial_capital
        commission_rate, slippage_rate = self._get_cost_rates()

        for symbol, df in data_dict.items():
            if start_date and end_date:
                df = df[(df.index >= start_date) & (df.index <= end_date)]

            df.attrs['symbol'] = symbol
            print(f"📊 Processing {symbol} with {len(df)} data points")
            active_trades: List[Trade] = []

            for i in range(50, len(df)):
                current_date = df.index[i]
                current_data = df.iloc[:i+1]

                # --- Exit Active Trades --- #
                for trade in active_trades[:]:
                    exit_signal = self.exit_handler.evaluate_exit(trade, df, i, self.detect_market_regime(df, i))
                    if exit_signal:
                        reason, price = exit_signal
                        trade.exit_time = current_date
                        trade.exit_price = price
                        trade.exit_reason = reason
                        trade.status = 'CLOSED'
                        size = trade.signal.position_size
                        gross_pnl = (price - trade.entry_price) * size if trade.signal.signal_type == 'BUY' else (trade.entry_price - price) * size
                        exit_commission = price * size * commission_rate
                        trade.pnl = gross_pnl - exit_commission
                        date_str = current_date.strftime('%Y-%m-%d')
                        self.daily_pnl[date_str] = self.daily_pnl.get(date_str, 0.0) + trade.pnl
                        active_trades.remove(trade)
                        self.trades.append(trade)
                        print(f"[{current_date.date()}] EXIT {trade.signal.strategy} {symbol} {reason} PnL={trade.pnl:.2f}")

                # --- New Entries --- #
                market_regime = self.detect_market_regime(df, i)
                for strategy in self.strategies:
                    try:
                        signal = strategy.generate_signal(current_data, market_regime)
                        if not signal:
                            continue
                        if not signal.position_size or signal.position_size <= 0:
                            signal.position_size = self._position_size_from_risk(signal.entry_price, signal.stop_loss)
                        if signal.position_size <= 0:
                            continue

                        raw_entry = signal.entry_price
                        slipped_entry = raw_entry * (1 + slippage_rate) if signal.signal_type == 'BUY' else raw_entry * (1 - slippage_rate)
                        notional = slipped_entry * signal.position_size
                        entry_cost = notional * commission_rate

                        trade = Trade(signal=signal, entry_time=current_date, entry_price=slipped_entry, status='OPEN')
                        date_str = current_date.strftime('%Y-%m-%d')
                        self.daily_pnl[date_str] = self.daily_pnl.get(date_str, 0.0) - entry_cost
                        active_trades.append(trade)
                        print(f"[{current_date.date()}] ENTER {signal.strategy} {symbol} {signal.signal_type} size={signal.position_size} @ {slipped_entry:.2f}")

                    except Exception as e:
                        print(f"⚠️ Strategy {strategy.name} error on {symbol}: {e}")

            # --- Force exit open trades at end --- #
            final_price = df['Close'].iloc[-1]
            for trade in active_trades:
                adj_final = final_price * (1 - slippage_rate) if trade.signal.signal_type == 'BUY' else final_price * (1 + slippage_rate)
                trade.exit_time = df.index[-1]
                trade.exit_price = adj_final
                trade.exit_reason = 'END_OF_DATA'
                trade.status = 'CLOSED'
                size = trade.signal.position_size
                gross_pnl = (adj_final - trade.entry_price) * size if trade.signal.signal_type == 'BUY' else (trade.entry_price - adj_final) * size
                exit_commission = adj_final * size * commission_rate
                trade.pnl = gross_pnl - exit_commission
                date_str = trade.exit_time.strftime('%Y-%m-%d')
                self.daily_pnl[date_str] = self.daily_pnl.get(date_str, 0.0) + trade.pnl
                self.trades.append(trade)

        print(f"✅ Backtest completed. Generated {len(self.trades)} trades")
        return self.calculate_performance_metrics()

    # -------- Metrics -------- #
    def calculate_performance_metrics(self):
        daily_pnl_series = pd.Series(self.daily_pnl).sort_index()
        if daily_pnl_series.empty:
            return self.create_empty_results()

        equity = daily_pnl_series.cumsum() + self.initial_capital
        returns = equity.pct_change().fillna(0.0)

        total_trades = len(self.trades)
        total_pnl = daily_pnl_series.sum()
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl < 0]

        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = sum(abs(t.pnl) for t in losing_trades)
        win_rate = len(winning_trades) / total_trades if total_trades else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        ann_return = (equity.iloc[-1] / equity.iloc[0]) ** (252 / max(1, len(returns))) - 1
        ann_vol = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0.0

        rolling_max = equity.cummax()
        dd = (equity - rolling_max) / rolling_max
        max_dd_pct = dd.min() if len(dd) else 0.0
        calmar = ann_return / abs(max_dd_pct) if max_dd_pct < 0 else 0.0

        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'annual_return_pct': ann_return * 100,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'max_drawdown_pct': max_dd_pct * 100,
            'volatility_pct': ann_vol * 100,
            'trades': self.trades
        }

    def create_empty_results(self):
        return {
            'total_trades': 0, 'win_rate': 0, 'total_pnl': 0,
            'gross_profit': 0, 'gross_loss': 0, 'profit_factor': 0,
            'annual_return_pct': 0, 'sharpe_ratio': 0, 'calmar_ratio': 0,
            'max_drawdown_pct': 0, 'volatility_pct': 0, 'trades': []
        }

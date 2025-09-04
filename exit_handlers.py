"""
exit_handlers.py

Provides pluggable exit handlers for the backtester:
- BaseExitHandler: interface
- FixedSLTPHandler: basic stop loss + take profit
- TrailingWithPartialHandler: partial exits at TP levels + trailing stop for remaining
- CompositeExitHandler: layering: hard stop -> partial TP -> trailing -> time -> volatility/regime exit
"""

from typing import Dict, Any, Tuple, List
import math

class BaseExitHandler:
    """
    Exit handlers must implement:
      - initialize(trade, df, entry_idx): called immediately after entry to set internal state
      - on_bar(i, row, df, market_regime) -> List[ exit_event ]
        where each exit_event = (exit_size, exit_price, reason)
    """
    def __init__(self, params: Dict[str, Any]):
        self.params = params or {}

    def initialize(self, trade, df, entry_idx):
        self.trade = trade
        self.entry_idx = entry_idx
        self.df = df
        # remaining_size on trade
        self.remaining = trade.signal.position_size

    def on_bar(self, i: int, row, df, market_regime) -> List[Tuple[int, float, str]]:
        return []

    def finalize_all(self, last_idx: int, last_price: float) -> List[Tuple[int, float, str]]:
        # default: full exit at last_price
        if self.remaining <= 0:
            return []
        size = self.remaining
        self.remaining = 0
        return [(size, last_price, 'END_OF_DATA')]


# ------------------------
# Fixed SL / TP handler
# ------------------------
class FixedSLTPHandler(BaseExitHandler):
    def initialize(self, trade, df, entry_idx):
        super().initialize(trade, df, entry_idx)
        s = trade.signal
        # store absolute prices
        self.stop = s.stop_loss
        self.target = s.target_price
        # direction: 'BUY' or 'SELL'
        self.dir = s.signal_type

    def on_bar(self, i: int, row, df, market_regime):
        events = []
        if self.remaining <= 0:
            return events

        if self.dir == 'BUY':
            # check stop first (assume stop is price below entry)
            if row['Low'] <= self.stop:
                events.append((self.remaining, self.stop, 'STOP'))
                self.remaining = 0
                return events
            if row['High'] >= self.target:
                events.append((self.remaining, self.target, 'TARGET'))
                self.remaining = 0
                return events
        else:  # SELL
            if row['High'] >= self.stop:
                events.append((self.remaining, self.stop, 'STOP'))
                self.remaining = 0
                return events
            if row['Low'] <= self.target:
                events.append((self.remaining, self.target, 'TARGET'))
                self.remaining = 0
                return events
        return events


# ------------------------
# Trailing + Partial Exit handler
# ------------------------
class TrailingWithPartialHandler(BaseExitHandler):
    """
    Parameters:
      - primary_targets: list of pct targets, e.g. [0.02, 0.05] (relative to entry)
      - partials: list of fractions that exit at those targets, e.g. [0.5, 0.5] (sums to <=1)
      - trailing_pct: pct used to compute trailing stop (e.g. 0.015)
      - initial_stop_pct: initial hard stop if provided (abs price or pct)
      - time_exit_bars: int max holding bars (optional)
      - volatility_exit_pctile: if market_regime['volatility_percentile'] exceeds this -> force exit
    """
    def initialize(self, trade, df, entry_idx):
        super().initialize(trade, df, entry_idx)
        s = trade.signal
        self.dir = s.signal_type
        self.entry_price = s.entry_price
        # allowed partial targets and sizes
        pts = self.params.get('primary_targets', [])
        parts = self.params.get('partials', [])
        # normalize
        if len(parts) != len(pts):
            # default equal split among targets
            frac = 1.0 / len(pts) if pts else 1.0
            parts = [frac] * len(pts)
        # convert to absolute target prices depending on dir
        self.targets = []
        for p in pts:
            if self.dir == 'BUY':
                self.targets.append(self.entry_price * (1 + p))
            else:
                self.targets.append(self.entry_price * (1 - p))
        self.partials = parts[:]  # fractions of original position to exit at each target
        self.trail_pct = float(self.params.get('trailing_pct', 0.015))
        # trailing stop initial: set to entry - trailing buffer or entry + trailing for short
        if self.dir == 'BUY':
            self.highest = self.entry_price
            self.trail_stop = self.entry_price * (1 - self.trail_pct)
        else:
            self.lowest = self.entry_price
            self.trail_stop = self.entry_price * (1 + self.trail_pct)
        # hard stop fallback (absolute price)
        self.hard_stop = s.stop_loss
        self.time_exit_bars = int(self.params.get('time_exit_bars', s.signal_type and getattr(s, 'max_holding_period', None) or 0) or 0)
        self.entry_idx = entry_idx
        # volatility/regime threshold
        self.vol_exit_pctile = float(self.params.get('volatility_exit_pctile', 99.0))

    def on_bar(self, i: int, row, df, market_regime):
        events = []
        if self.remaining <= 0:
            return events

        # TIME exit
        if self.time_exit_bars and (i - self.entry_idx) >= self.time_exit_bars:
            events.append((self.remaining, float(row['Close']), 'TIME_EXIT'))
            self.remaining = 0
            return events

        # Volatility/regime-based immediate exit
        if market_regime and 'volatility_percentile' in market_regime and market_regime['volatility_percentile'] >= self.vol_exit_pctile:
            # exit all to avoid sudden spikes
            events.append((self.remaining, float(row['Close']), 'VOLATILITY_EXIT'))
            self.remaining = 0
            return events

        if self.dir == 'BUY':
            # update highest and trailing stop
            self.highest = max(self.highest, float(row['High']))
            new_trail = self.highest * (1 - self.trail_pct)
            if new_trail > self.trail_stop:
                self.trail_stop = new_trail

            # check partial targets (in order)
            for idx, tgt in enumerate(self.targets):
                if self.partials[idx] <= 0:
                    continue
                if float(row['High']) >= tgt:
                    # exit specified fraction of initial size
                    orig_size = self.trade.signal.position_size
                    size = int(round(self.partials[idx] * orig_size))
                    size = min(size, self.remaining)
                    if size > 0:
                        events.append((size, tgt, f'PARTIAL_TARGET_{int(idx+1)}'))
                        self.remaining -= size
                        self.partials[idx] = 0.0  # mark consumed

            # check trailing stop or hard stop
            if float(row['Low']) <= self.trail_stop:
                events.append((self.remaining, self.trail_stop, 'TRAIL_STOP'))
                self.remaining = 0
                return events
            if self.hard_stop and float(row['Low']) <= self.hard_stop:
                events.append((self.remaining, self.hard_stop, 'HARD_STOP'))
                self.remaining = 0
                return events

        else:  # SELL
            self.lowest = min(self.lowest, float(row['Low']))
            new_trail = self.lowest * (1 + self.trail_pct)
            if new_trail < self.trail_stop:
                self.trail_stop = new_trail

            for idx, tgt in enumerate(self.targets):
                if self.partials[idx] <= 0:
                    continue
                if float(row['Low']) <= tgt:
                    orig_size = self.trade.signal.position_size
                    size = int(round(self.partials[idx] * orig_size))
                    size = min(size, self.remaining)
                    if size > 0:
                        events.append((size, tgt, f'PARTIAL_TARGET_{int(idx+1)}'))
                        self.remaining -= size
                        self.partials[idx] = 0.0

            if float(row['High']) >= self.trail_stop:
                events.append((self.remaining, self.trail_stop, 'TRAIL_STOP'))
                self.remaining = 0
                return events
            if self.hard_stop and float(row['High']) >= self.hard_stop:
                events.append((self.remaining, self.hard_stop, 'HARD_STOP'))
                self.remaining = 0
                return events

        return events


# ------------------------
# CompositeExitHandler (convenience)
# ------------------------
class CompositeExitHandler(BaseExitHandler):
    """
    Factory-like handler that composes layered exit behavior.
    Expect params keys:
      - partial_targets: list of pct levels [0.02, 0.06]
      - partials: fractions [0.5, 0.5]
      - trailing_pct: 0.015
      - hard_stop_pct: e.g., 0.02 (if provided and stop on signal is not absolute)
      - time_exit_bars: int
      - volatility_exit_pctile: float
    """
    def initialize(self, trade, df, entry_idx):
        super().initialize(trade, df, entry_idx)
        # Build an internal TrailingWithPartialHandler using params
        tparams = {
            'primary_targets': self.params.get('partial_targets', []),
            'partials': self.params.get('partials', []),
            'trailing_pct': self.params.get('trailing_pct', 0.015),
            'time_exit_bars': self.params.get('time_exit_bars', 0),
            'volatility_exit_pctile': self.params.get('volatility_exit_pctile', 99.0)
        }
        self.inner = TrailingWithPartialHandler(tparams)
        # If trade.signal.stop_loss is None but hard_stop_pct provided, compute absolute stop
        stop = trade.signal.stop_loss
        if (stop is None or math.isnan(stop)) and ('hard_stop_pct' in self.params):
            pct = float(self.params['hard_stop_pct'])
            if trade.signal.signal_type == 'BUY':
                trade.signal.stop_loss = trade.signal.entry_price * (1 - pct)
            else:
                trade.signal.stop_loss = trade.signal.entry_price * (1 + pct)
        # pass through
        self.inner.initialize(trade, df, entry_idx)

    def on_bar(self, i, row, df, market_regime):
        return self.inner.on_bar(i, row, df, market_regime)

    def finalize_all(self, last_idx, last_price):
        return self.inner.finalize_all(last_idx, last_price)

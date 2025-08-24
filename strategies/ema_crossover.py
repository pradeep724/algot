# strategies/ema_crossover.py
from dataclasses import dataclass
import pandas as pd

@dataclass
class EMACrossParams:
    fast: int = 12
    slow: int = 26
    atr_mult: float = 2.0

class EMACross:
    def __init__(self, params: EMACrossParams):
        self.p = params

    def signal(self, df: pd.DataFrame) -> str:
        if len(df) < max(self.p.fast, self.p.slow) + 5:
            return "HOLD"
        ema_f = df["ema_fast"].iloc[-1]
        ema_s = df["ema_slow"].iloc[-1]
        if ema_f > ema_s:
            return "BUY"
        elif ema_f < ema_s:
            return "SELL"
        return "HOLD"

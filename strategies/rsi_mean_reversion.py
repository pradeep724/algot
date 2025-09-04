import numpy as np
import pandas as pd
from enhanced_backtesting import TradingSignal

class RSIMeanReversionStrategy:
    def __init__(self, config):
        self.name = "rsi_mean_reversion"
        self.rsi_period = config.get("rsi_period", 14)
        self.oversold_threshold = config.get("oversold_threshold", 25)
        self.overbought_threshold = config.get("overbought_threshold", 75)
        self.sma_period = config.get("sma_period", 20)
        self.stop_loss_mult = config.get("stop_loss_mult", 1.5)
        self.profit_target_pct = config.get("profit_target_pct", 0.035)
        self.max_holding_period = config.get("max_holding_days", 7)

    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(window=period).mean()
        avg_loss = pd.Series(loss).rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_atr(self, df, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift()).abs()
        low_close = (df["Low"] - df["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def calculate_indicators(self, df):
        df = df.copy()
        df["RSI"] = self.calculate_rsi(df["Close"], self.rsi_period)
        df["SMA"] = df["Close"].rolling(window=self.sma_period).mean()
        df["ATR"] = self.calculate_atr(df, 14)
        df["Volume_SMA"] = df["Volume"].rolling(window=20).mean()
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < max(self.rsi_period, self.sma_period) + 10:
            return None

        current = df.iloc[-1]
        prev = df.iloc[-2]

        oversold = (
            current["RSI"] < self.oversold_threshold
            and prev["RSI"] >= self.oversold_threshold
            and current["Close"] > current["SMA"]
        )
        overbought = (
            current["RSI"] > self.overbought_threshold
            and prev["RSI"] <= self.overbought_threshold
            and current["Close"] < current["SMA"]
        )
        volume_ok = current["Volume"] > current["Volume_SMA"]

        # --- BUY setup ---
        if oversold and volume_ok:
            entry = current["Close"]
            target = entry * (1 + self.profit_target_pct)
            stop = entry - (current["ATR"] * self.stop_loss_mult)
            return TradingSignal(
                timestamp=current.name,
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                strategy=self.name,
                signal_type="BUY",
                entry_price=entry,
                target_price=target,
                stop_loss=stop,
                position_size=1,
                reasons=f"RSI oversold mean reversion (RSI {current['RSI']:.1f})"
            )

        # --- SELL setup ---
        if overbought and volume_ok:
            entry = current["Close"]
            target = entry * (1 - self.profit_target_pct)
            stop = entry + (current["ATR"] * self.stop_loss_mult)
            return TradingSignal(
                timestamp=current.name,
                symbol=df.attrs.get("symbol", "UNKNOWN"),
                strategy=self.name,
                signal_type="SELL",
                entry_price=entry,
                target_price=target,
                stop_loss=stop,
                position_size=1,
                reasons=f"RSI overbought mean reversion (RSI {current['RSI']:.1f})"
            )

        return None

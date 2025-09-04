from backtesting import TradingSignal
import numpy as np

class VolatilityBreakoutStrategy:
    def __init__(self, config):
        self.name = "volatility_breakout"
        self.config = config.get('volatility_breakout', {})
        self.lookback_period = self.config.get('lookback_period', 20)
        self.vol_threshold = self.config.get('vol_threshold', 50)       # relaxed from 75
        self.volume_threshold = self.config.get('volume_threshold', 1.1)  # relaxed from 1.3
        self.target_pct = self.config.get('target_pct', 0.03)
        self.stop_loss_pct = self.config.get('stop_loss_pct', 0.02)
        self.max_holding_period = self.config.get('max_holding_period', 5)

    def calculate_indicators(self, df):
        df = df.copy()
        # Shift rolling highs/lows so current candle can actually break them
        df['Rolling_High'] = df['High'].rolling(window=self.lookback_period).max().shift(1)
        df['Rolling_Low'] = df['Low'].rolling(window=self.lookback_period).min().shift(1)

        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=self.lookback_period).std() * np.sqrt(252)

        symbol = df.attrs.get('symbol', 'UNKNOWN')

        if 'Volume' in df.columns and df['Volume'].notna().any() and df['Volume'].sum() > 0:
           # Use real volume filter for stocks
           df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
           df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']
        else:
           # Spot indices (NIFTY, BANKNIFTY, FINNIFTY) have no volume → bypass
           if symbol in ['NIFTY', 'BANKNIFTY', 'FINNIFTY']:
              df['Volume_Ratio'] = 1.0
           else:
              # Safety fallback if any other data source is missing volume
              df['Volume_Ratio'] = 1.0

        #df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        #df['Volume_Ratio'] = df['Volume'] / df['Volume_MA']

        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        df['BB_Std'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (df['BB_Std'] * 2)
        df['BB_Lower'] = df['BB_Middle'] - (df['BB_Std'] * 2)
        df = df.dropna().copy()
        return df

    def generate_signal(self, df, regime_info):
        if len(df) < self.lookback_period + 20:
            return None

        df_with_indicators = self.calculate_indicators(df)
        current = df_with_indicators.iloc[-1]
        prev_day = df_with_indicators.iloc[-2]

        # breakout conditions
        upside_breakout = (
            current['High'] > current['Rolling_High'] and
            current['Close'] > prev_day['Rolling_High']
        )
        downside_breakout = (
            current['Low'] < current['Rolling_Low'] and
            current['Close'] < prev_day['Rolling_Low']
        )

        # volume & volatility
        #volume_surge = current['Volume_Ratio'] >= self.volume_threshold
        symbol = df.attrs.get('symbol', 'UNKNOWN')
        volume_surge = (current['Volume_Ratio'] >= self.volume_threshold) or symbol in ['NIFTY','BANKNIFTY','FINNIFTY']
        vol_percentile = (df_with_indicators['Volatility'].tail(50).rank(pct=True).iloc[-1]) * 100
        volatility_expanding = vol_percentile >= self.vol_threshold

        # bollinger
        bb_upside_break = current['Close'] > current['BB_Upper']
        bb_downside_break = current['Close'] < current['BB_Lower']

        # 🔍 Debug print
        print(
            f"[{current.name}] {df.attrs.get('symbol', 'UNKNOWN')} | "
            f"Upside:{upside_breakout} Downside:{downside_breakout} | "
            f"VolRatio:{current['Volume_Ratio']:.2f} (thr {self.volume_threshold}) | "
            f"Vol%ile:{vol_percentile:.1f} (thr {self.vol_threshold}) | "
            f"BB_up:{bb_upside_break} BB_down:{bb_downside_break}"
        )

        print(f"[{current.name}] {symbol} | Breakout:{upside_breakout or downside_breakout} "
             f"| Vol OK:{volatility_expanding} | BB:{bb_upside_break or bb_downside_break} "
             f"| VolRatio:{current['Volume_Ratio']:.2f}")

        # BUY condition
        #if upside_breakout and volume_surge and volatility_expanding and bb_upside_break:
        if upside_breakout and volume_surge:
            entry = current['Close']
            target = entry * (1 + self.target_pct)
            stop = max(entry * (1 - self.stop_loss_pct), current['Rolling_High'] * 0.995)
            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0
            if rr >= 0.8:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='BUY',
                    strength=0.9,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.target_pct,
                    risk_reward_ratio=rr,
                    confidence=0.8,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Upside breakout | Vol%ile:{vol_percentile:.1f} VolRatio:{current['Volume_Ratio']:.2f}"
                )

        # SELL condition
        #elif downside_breakout and volume_surge and volatility_expanding and bb_downside_break:
        elif downside_breakout and volume_surge:
            entry = current['Close']
            target = entry * (1 - self.target_pct)
            stop = min(entry * (1 + self.stop_loss_pct), current['Rolling_Low'] * 1.005)
            risk = stop - entry
            reward = entry - target
            rr = reward / risk if risk > 0 else 0
            if rr >= 0.8:
                return TradingSignal(
                    timestamp=current.name,
                    symbol=df.attrs.get('symbol', 'UNKNOWN'),
                    strategy=self.name,
                    signal_type='SELL',
                    strength=0.9,
                    entry_price=entry,
                    target_price=target,
                    stop_loss=stop,
                    position_size=1,
                    expected_pnl=self.target_pct,
                    risk_reward_ratio=rr,
                    confidence=0.8,
                    market_regime=regime_info.get('regime', 'normal'),
                    reasons=f"Downside breakout | Vol%ile:{vol_percentile:.1f} VolRatio:{current['Volume_Ratio']:.2f}"
                )

        return None

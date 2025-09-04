from backtesting import TradingSignal
import datetime

class TestStrategy:
    name = "test_strategy"

    def __init__(self, config):
        self.config = config

    def generate_signal(self, df, market_regime):
        # Every 20th candle, generate a BUY
        if len(df) % 20 == 0:
            price = df['Close'].iloc[-1]
            return TradingSignal(
                timestamp=df.index[-1],
                symbol=df.attrs['symbol'],
                strategy=self.name,
                signal_type="BUY",
                strength=1.0,
                entry_price=price,
                target_price=price * 1.02,
                stop_loss=price * 0.98,
                position_size=10,
                expected_pnl=price * 0.02 * 10,
                risk_reward_ratio=2.0,
                confidence=0.9,
                market_regime=market_regime['regime'],
                reasons="Dummy BUY every 20 candles"
            )
        return None

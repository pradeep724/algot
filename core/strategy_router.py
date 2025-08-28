from strategies.debit_spreads import DebitSpreadStrategy
from strategies.long_options import LongOptionsStrategy
from strategies.iron_condor import IronCondorStrategy
from strategies.protective_straddle import ProtectiveStraddleStrategy
from utils.logger import log

class StrategyRouter:
    def __init__(self, cfg):
        self.cfg = cfg
        self.strategies = {
            'trending_high_vol': DebitSpreadStrategy(cfg),
            'trending_low_vol': LongOptionsStrategy(cfg),
            'range_low_vol': IronCondorStrategy(cfg),
            'event_risk_high': ProtectiveStraddleStrategy(cfg)
        }
    
    def generate_signal(self, regime, historical_data, live_data):
        strategy = self.strategies.get(regime)
        if not strategy:
            log.warning(f"No strategy mapped for regime '{regime}', defaulting to IronCondor")
            strategy = self.strategies['range_low_vol']
        return strategy.generate(historical_data, live_data)

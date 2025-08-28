from utils.logger import log

class RegimeDetector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.vix_high = cfg['data'].get('vix_high_threshold', 20)
        self.vix_low = cfg['data'].get('vix_low_threshold', 12)
    
    def detect_regime(self, hist_data, vix_data, market_breadth):
        vix = vix_data.get("value", 15) if vix_data else 15
        
        trending = self.is_trending(hist_data)
        if vix > self.vix_high:
            regime = "trending_high_vol" if trending else "event_risk_high"
        elif vix < self.vix_low:
            regime = "trending_low_vol" if trending else "range_low_vol"
        else:
            regime = "range_low_vol"
        
        log.info(f"Regime detected: {regime} (VIX: {vix})")
        return regime
    
    def is_trending(self, data):
        if len(data) < 20:
            return False
        recent = data[-20:]
        price = [d.get('Close') for d in recent]
        return price[-1] > sum(price)/len(price)

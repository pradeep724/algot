import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading
from utils.logger import log
from utils.greeks import GreeksCalculator
from utils.iv_analysis import IVAnalyzer

class EnhancedDataManager:
    def __init__(self, api_client, config):
        self.api = api_client
        self.config = config
        self.greeks_calc = GreeksCalculator()
        self.iv_analyzer = IVAnalyzer()
        
        # Real-time data cache
        self.live_data = {
            'option_chains': {},
            'index_data': {},
            'vix': None,
            'market_breadth': {},
            'last_update': {}
        }
        
        # Start background data update thread
        self.data_thread = threading.Thread(target=self._continuous_data_update)
        self.data_thread.daemon = True
        self.is_running = True

    def start_live_feeds(self):
        """Start continuous data updating."""
        log.info("Starting live data feeds...")
        self.data_thread.start()

    def stop_live_feeds(self):
        """Stop data feeds."""
        self.is_running = False

    def _continuous_data_update(self):
        """Background thread for continuous data updates."""
        while self.is_running:
            try:
                # Update all live data
                self._update_index_data()
                self._update_option_chains()
                self._update_vix()
                self._update_market_breadth()
                
                time.sleep(self.config['data']['update_frequency_seconds'])
            except Exception as e:
                log.error(f"Error in data update cycle: {e}")
                time.sleep(5)

    def _update_index_data(self):
        """Update live index OHLC data."""
        for instrument in self.config['universe'].keys():
            try:
                token = self.config['universe'][instrument]['token']
                # Get live quote
                quote_data = self.api.getMarketData("NSE", [token])
                
                if quote_data and quote_data.get('status'):
                    data = quote_data['data'][0]
                    self.live_data['index_data'][instrument] = {
                        'ltp': float(data['ltp']),
                        'open': float(data['open']),
                        'high': float(data['high']),
                        'low': float(data['low']),
                        'volume': int(data['volume']),
                        'timestamp': datetime.now()
                    }
                    
            except Exception as e:
                log.error(f"Error updating {instrument} data: {e}")

    def _update_option_chains(self):
        """Update live option chain data with Greeks."""
        for instrument in self.config['universe'].keys():
            try:
                if instrument not in self.live_data['index_data']:
                    continue
                    
                ltp = self.live_data['index_data'][instrument]['ltp']
                chain = self._fetch_option_chain(instrument, ltp)
                
                if chain:
                    # Calculate Greeks for each option
                    enhanced_chain = self._enhance_chain_with_greeks(chain, ltp)
                    self.live_data['option_chains'][instrument] = enhanced_chain
                    
            except Exception as e:
                log.error(f"Error updating option chain for {instrument}: {e}")

    def _fetch_option_chain(self, instrument, spot_price):
        """Fetch option chain from API."""
        try:
            # This is a placeholder - implement actual Angel One option chain API call
            # The API call would look something like:
            # chain_data = self.api.getOptionChain(instrument)
            
            # For now, simulate option chain structure
            chain = []
            depth = self.config['data']['option_chain_depth']
            
            # Generate strike prices around current spot
            atm_strike = round(spot_price / 50) * 50
            
            for i in range(-depth, depth + 1):
                strike = atm_strike + (i * 50)
                
                # Simulate call and put data
                for option_type in ['CE', 'PE']:
                    chain.append({
                        'strike': strike,
                        'type': option_type,
                        'symbol': f"{instrument}{strike}{option_type}",
                        'ltp': max(1, abs(strike - spot_price) * 0.5 + np.random.uniform(5, 50)),
                        'volume': np.random.randint(100, 10000),
                        'open_interest': np.random.randint(1000, 100000),
                        'implied_volatility': np.random.uniform(15, 35),
                        'bid': 0,
                        'ask': 0
                    })
            
            return chain
            
        except Exception as e:
            log.error(f"Error fetching option chain for {instrument}: {e}")
            return None

    def _enhance_chain_with_greeks(self, chain, spot_price):
        """Calculate Greeks for each option in the chain."""
        enhanced_chain = []
        
        for option in chain:
            try:
                # Calculate time to expiry (simplified - assume weekly expiry)
                dte = 7  # Days to expiry - should be calculated from actual expiry
                time_to_expiry = dte / 365.0
                
                greeks = self.greeks_calc.calculate_greeks(
                    spot_price=spot_price,
                    strike_price=option['strike'],
                    time_to_expiry=time_to_expiry,
                    risk_free_rate=0.06,  # 6% risk-free rate
                    implied_volatility=option['implied_volatility'] / 100,
                    option_type=option['type']
                )
                
                option.update(greeks)
                enhanced_chain.append(option)
                
            except Exception as e:
                log.error(f"Error calculating Greeks for {option['symbol']}: {e}")
                enhanced_chain.append(option)
                
        return enhanced_chain

    def _update_vix(self):
        """Update India VIX data."""
        try:
            # Placeholder for India VIX API call
            # In reality: vix_data = self.api.getMarketData("NSE", ["INDIA_VIX_TOKEN"])
            
            # Simulate VIX data
            self.live_data['vix'] = {
                'value': np.random.uniform(12, 25),  # Simulated VIX
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            log.error(f"Error updating VIX: {e}")

    def _update_market_breadth(self):
        """Update market breadth indicators."""
        try:
            # Placeholder for market breadth data
            # This would fetch advance/decline ratios, new highs/lows, etc.
            
            self.live_data['market_breadth'] = {
                'advance_decline_ratio': np.random.uniform(0.3, 2.0),
                'new_highs': np.random.randint(10, 100),
                'new_lows': np.random.randint(5, 50),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            log.error(f"Error updating market breadth: {e}")

    def get_live_option_chain(self, instrument):
        """Get current live option chain."""
        return self.live_data['option_chains'].get(instrument, [])

    def get_live_index_data(self, instrument):
        """Get current live index data."""
        return self.live_data['index_data'].get(instrument, {})

    def get_vix(self):
        """Get current VIX level."""
        return self.live_data['vix']

    def get_market_breadth(self):
        """Get current market breadth data."""
        return self.live_data['market_breadth']

    def is_data_fresh(self, max_age_seconds=30):
        """Check if data is fresh enough for trading decisions."""
        now = datetime.now()
        
        for instrument in self.config['universe'].keys():
            if instrument in self.live_data['index_data']:
                last_update = self.live_data['index_data'][instrument]['timestamp']
                age = (now - last_update).total_seconds()
                
                if age > max_age_seconds:
                    log.warning(f"Stale data detected for {instrument}: {age}s old")
                    return False
                    
        return True

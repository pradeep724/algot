import time
import signal
import sys
from datetime import datetime, timedelta
import yaml
from utils.logger import log
from utils.alerts import AlertManager
from core.data_manager import EnhancedDataManager
from core.regime_detector import RegimeDetector
from core.strategy_router import StrategyRouter
from core.risk_manager import PortfolioRiskManager
from core.execution_manager import SmartExecutionManager
from SmartApi import SmartConnect
import pyotp

class ProTraderBotV2:
    def __init__(self, config_path='config.yaml'):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
            
        # Initialize components
        self.api_client = None
        self.data_manager = None
        self.regime_detector = None
        self.strategy_router = None
        self.risk_manager = None
        self.execution_manager = None
        self.alert_manager = AlertManager(self.config)
        
        # System state
        self.is_running = False
        self.last_health_check = datetime.now()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def initialize(self):
        """Initialize all system components."""
        try:
            log.info("🚀 Initializing ProTraderBot v2.0...")
            
            # 1. Connect to broker API
            if not self._connect_to_broker():
                raise Exception("Failed to connect to broker")
                
            # 2. Initialize core components
            self.data_manager = EnhancedDataManager(self.api_client, self.config)
            self.regime_detector = RegimeDetector(self.config)
            self.strategy_router = StrategyRouter(self.config)
            self.risk_manager = PortfolioRiskManager(self.config)
            self.execution_manager = SmartExecutionManager(self.api_client, self.config)
            
            # 3. Start data feeds
            self.data_manager.start_live_feeds()
            
            # 4. Send initialization alert
            self.alert_manager.send_critical_alert(
                f"ProTraderBot v2.0 initialized successfully in {self.config['mode']} mode"
            )
            
            log.info("✅ System initialization complete")
            return True
            
        except Exception as e:
            log.critical(f"❌ System initialization failed: {e}")
            self.alert_manager.send_critical_alert(f"INITIALIZATION FAILED: {e}")
            return False

    def _connect_to_broker(self):
        """Connect to Angel One API."""
        try:
            api_config = self.config['api']['angel_one']
            self.api_client = SmartConnect(api_key=api_config['api_key'])
            
            # Generate TOTP and login
            totp = pyotp.TOTP(api_config['totp_secret']).now()
            data = self.api_client.generateSession(
                api_config['client_id'], 
                api_config['pin'], 
                totp
            )
            
            if data['status'] and data.get('data', {}).get('jwtToken'):
                log.info("✅ Connected to Angel One API")
                return True
            else:
                log.error(f"❌ Angel One login failed: {data.get('message')}")
                return False
                
        except Exception as e:
            log.error(f"❌ Broker connection error: {e}")
            return False

    def run(self):
        """Main trading loop."""
        if not self.initialize():
            return
            
        self.is_running = True
        log.info("🎯 Starting main trading loop...")
        
        try:
            while self.is_running:
                # Check if it's market hours
                if not self._is_market_hours():
                    log.info("📴 Market is closed. Sleeping...")
                    time.sleep(300)  # Sleep for 5 minutes
                    continue
                
                # System health check
                if not self._health_check():
                    log.critical("❌ Health check failed. Stopping system.")
                    break
                
                # Main trading cycle
                self._trading_cycle()
                
                # Sleep between cycles
                time.sleep(30)  # 30-second cycle
                
        except Exception as e:
            log.critical(f"💥 Critical error in main loop: {e}")
            self.alert_manager.send_critical_alert(f"SYSTEM ERROR: {e}")
        finally:
            self._shutdown()

    def _trading_cycle(self):
        """Execute one complete trading cycle."""
        try:
            log.debug("🔄 Starting trading cycle...")
            
            # 1. Check data freshness
            if not self.data_manager.is_data_fresh():
                log.warning("⚠️ Stale data detected, skipping cycle")
                return
            
            # 2. Scan each instrument in universe
            for instrument in self.config['universe'].keys():
                self._process_instrument(instrument)
                
            # 3. Portfolio maintenance
            self._portfolio_maintenance()
            
            # 4. Send periodic updates
            self._send_status_updates()
            
        except Exception as e:
            log.error(f"Error in trading cycle: {e}")

    def _process_instrument(self, instrument):
        """Process trading logic for one instrument."""
        try:
            # Get live data
            index_data = self.data_manager.get_live_index_data(instrument)
            option_chain = self.data_manager.get_live_option_chain(instrument)
            vix_data = self.data_manager.get_vix()
            market_breadth = self.data_manager.get_market_breadth()
            
            if not index_data:
                log.debug(f"No data available for {instrument}")
                return
            
            # Load historical data (you'd implement this)
            historical_data = self._load_historical_data(instrument)
            
            # Detect market regime
            regime = self.regime_detector.detect_regime(
                historical_data, vix_data, market_breadth
            )
            
            # Generate strategy signal
            live_data = {
                'instrument': instrument,
                'index_data': index_data,
                'option_chain': option_chain,
                'vix': vix_data,
                'market_breadth': market_breadth
            }
            
            signal = self.strategy_router.generate_signal(regime, historical_data, live_data)
            
            if signal:
                log.info(f"📊 Signal generated for {instrument}: {signal['direction']}")
                
                # Risk management check
                if self.risk_manager.check_pre_trade_risk(signal):
                    # Execute trade
                    trade_id = self.execution_manager.place_spread_trade(signal, option_chain)
                    
                    if trade_id:
                        log.info(f"✅ Trade executed: {trade_id}")
                        self.alert_manager.send_trade_alert({
                            'strategy': signal.get('strategy_type'),
                            'direction': signal.get('direction'),
                            'underlying': instrument,
                            'trade_id': trade_id
                        })
                    else:
                        log.warning("❌ Trade execution failed")
                else:
                    log.info("🚫 Trade blocked by risk management")
            
        except Exception as e:
            log.error(f"Error processing {instrument}: {e}")

    def _load_historical_data(self, instrument):
        """Load historical data for analysis."""
        try:
            import pandas as pd
            # Load from your data files
            file_path = f"data/{instrument}_historical.csv"
            df = pd.read_csv(file_path, index_col='Timestamp', parse_dates=True)
            return df.tail(200)  # Last 200 days
        except Exception as e:
            log.error(f"Error loading historical data for {instrument}: {e}")
            return pd.DataFrame()

    def _portfolio_maintenance(self):
        """Perform portfolio maintenance tasks."""
        try:
            # Update portfolio state
            positions = self.execution_manager.get_portfolio_summary()
            self.risk_manager.update_portfolio_state(positions)
            
            # Check for position management (exits, adjustments)
            self._check_position_exits()
            
            # Check risk limits
            self._check_portfolio_risk_limits()
            
        except Exception as e:
            log.error(f"Error in portfolio maintenance: {e}")

    def _check_position_exits(self):
        """Check if any positions need to be closed."""
        # This would implement your exit logic
        # For example: time-based exits, profit targets, stop losses
        pass

    def _check_portfolio_risk_limits(self):
        """Check if portfolio exceeds risk limits."""
        portfolio_summary = self.risk_manager.get_portfolio_summary()
        
        # Check daily loss limit
        daily_pnl = portfolio_summary.get('daily_pnl', 0)
        max_daily_loss = self.config['risk']['account_capital'] * self.config['risk']['max_daily_loss_pct']
        
        if daily_pnl < -max_daily_loss:
            log.critical("🚨 DAILY LOSS LIMIT BREACHED - EMERGENCY LIQUIDATION")
            self.risk_manager.emergency_liquidate(self.execution_manager)

    def _send_status_updates(self):
        """Send periodic status updates."""
        now = datetime.now()
        
        # Send hourly P&L updates during market hours
        if now.minute == 0:  # Top of the hour
            portfolio_summary = self.execution_manager.get_portfolio_summary()
            self.alert_manager.send_pnl_update({
                'daily_pnl': 0,  # Would calculate actual P&L
                'position_count': portfolio_summary['total_positions'],
                'portfolio_delta': 0,  # From risk manager
                'portfolio_theta': 0   # From risk manager  
            })

    def _health_check(self):
        """Perform system health check."""
        try:
            # Check API connectivity
            if not self._test_api_connection():
                return False
                
            # Check data freshness
            if not self.data_manager.is_data_fresh(max_age_seconds=60):
                return False
                
            # Check memory usage, etc.
            # (Add more health checks as needed)
            
            self.last_health_check = datetime.now()
            return True
            
        except Exception as e:
            log.error(f"Health check failed: {e}")
            return False

    def _test_api_connection(self):
        """Test API connectivity."""
        try:
            # Simple API test - get profile or similar
            # profile = self.api_client.getProfile()
            # return profile.get('status', False)
            return True  # Placeholder
        except:
            return False

    def _is_market_hours(self):
        """Check if market is currently open."""
        now = datetime.now()
        
        # Skip weekends
        if now.weekday() >= 5:
            return False
            
        # Market hours: 9:15 AM to 3:30 PM IST
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        log.info(f"📴 Received shutdown signal {signum}")
        self.is_running = False

    def _shutdown(self):
        """Graceful shutdown procedure."""
        log.info("📴 Initiating graceful shutdown...")
        
        try:
            # Stop data feeds
            if self.data_manager:
                self.data_manager.stop_live_feeds()
                
            # Close any open orders/positions if needed
            # (Implement emergency procedures)
            
            # Send shutdown alert
            self.alert_manager.send_critical_alert("ProTraderBot v2.0 has been shut down")
            
            log.info("✅ Shutdown complete")
            
        except Exception as e:
            log.error(f"Error during shutdown: {e}")

def main():
    """Entry point for ProTraderBot v2.0."""
    try:
        bot = ProTraderBotV2()
        bot.run()
    except KeyboardInterrupt:
        log.info("👋 Bot stopped by user")
    except Exception as e:
        log.critical(f"💥 Fatal error: {e}")

if __name__ == "__main__":
    main()

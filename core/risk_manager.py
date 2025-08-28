import pandas as pd
from utils.logger import log
from utils.alerts import AlertManager

class PortfolioRiskManager:
    def __init__(self, config):
        self.config = config
        self.risk_limits = config['risk']
        self.alert_manager = AlertManager(config)
        
        # Current portfolio state
        self.current_positions = {}
        self.daily_pnl = 0.0
        self.portfolio_greeks = {
            'delta': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'gamma': 0.0
        }

    def check_pre_trade_risk(self, proposed_trade):
        """Check if proposed trade passes all risk checks."""
        checks = [
            self._check_position_size_limit(proposed_trade),
            self._check_portfolio_delta_limit(proposed_trade),
            self._check_portfolio_theta_limit(proposed_trade),
            self._check_daily_loss_limit(),
            self._check_correlation_limit(proposed_trade)
        ]
        
        passed = all(checks)
        
        if not passed:
            log.warning(f"Trade rejected due to risk limits: {proposed_trade}")
            
        return passed

    def _check_position_size_limit(self, trade):
        """Check if trade size exceeds per-trade risk limit."""
        max_risk = self.config['risk']['account_capital'] * self.risk_limits['max_risk_per_trade_pct']
        trade_risk = trade.get('max_loss', 0)
        
        if trade_risk > max_risk:
            log.warning(f"Trade risk {trade_risk} exceeds limit {max_risk}")
            return False
        return True

    def _check_portfolio_delta_limit(self, trade):
        """Check if trade would exceed portfolio delta limit."""
        new_delta = self.portfolio_greeks['delta'] + trade.get('delta', 0)
        max_delta = self.risk_limits['max_portfolio_delta']
        
        if abs(new_delta) > max_delta:
            log.warning(f"Portfolio delta {new_delta} would exceed limit {max_delta}")
            return False
        return True

    def _check_portfolio_theta_limit(self, trade):
        """Check if trade would exceed portfolio theta limit."""
        new_theta = self.portfolio_greeks['theta'] + trade.get('theta', 0)
        min_theta = self.risk_limits['max_portfolio_theta']  # Negative number
        
        if new_theta < min_theta:
            log.warning(f"Portfolio theta {new_theta} would exceed limit {min_theta}")
            return False
        return True

    def _check_daily_loss_limit(self):
        """Check if daily loss limit has been hit."""
        max_daily_loss = self.config['risk']['account_capital'] * self.risk_limits['max_daily_loss_pct']
        
        if self.daily_pnl < -max_daily_loss:
            log.critical(f"Daily loss limit breached: {self.daily_pnl}")
            self.alert_manager.send_critical_alert("DAILY LOSS LIMIT BREACHED - TRADING HALTED")
            return False
        return True

    def _check_correlation_limit(self, trade):
        """Check for over-concentration in similar trades."""
        # Simple check: don't have more than 3 positions in same underlying
        underlying = trade.get('underlying', '')
        current_count = sum(1 for pos in self.current_positions.values() 
                          if pos.get('underlying') == underlying)
        
        if current_count >= 3:
            log.warning(f"Too many positions in {underlying}")
            return False
        return True

    def update_portfolio_state(self, positions):
        """Update current portfolio state and Greeks."""
        self.current_positions = positions
        
        # Recalculate portfolio Greeks
        total_delta = sum(pos.get('delta', 0) for pos in positions.values())
        total_theta = sum(pos.get('theta', 0) for pos in positions.values())
        total_vega = sum(pos.get('vega', 0) for pos in positions.values())
        
        self.portfolio_greeks = {
            'delta': total_delta,
            'theta': total_theta,
            'vega': total_vega,
            'gamma': sum(pos.get('gamma', 0) for pos in positions.values())
        }

    def emergency_liquidate(self, execution_manager):
        """Emergency kill switch - liquidate all positions."""
        log.critical("EMERGENCY LIQUIDATION TRIGGERED")
        self.alert_manager.send_critical_alert("EMERGENCY LIQUIDATION IN PROGRESS")
        
        try:
            for position_id, position in self.current_positions.items():
                execution_manager.close_position(position_id, emergency=True)
                
            log.critical("Emergency liquidation completed")
            
        except Exception as e:
            log.critical(f"Error during emergency liquidation: {e}")
            self.alert_manager.send_critical_alert(f"LIQUIDATION ERROR: {e}")

    def get_portfolio_summary(self):
        """Get current portfolio risk summary."""
        return {
            'positions_count': len(self.current_positions),
            'daily_pnl': self.daily_pnl,
            'portfolio_greeks': self.portfolio_greeks.copy(),
            'risk_utilization': {
                'delta': abs(self.portfolio_greeks['delta']) / self.risk_limits['max_portfolio_delta'],
                'theta': abs(self.portfolio_greeks['theta']) / abs(self.risk_limits['max_portfolio_theta'])
            }
        }

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class EnhancedRiskManager:
    def __init__(self, config):
        self.config = config.get('risk_management', {})
        self.account_capital = self.config.get('account_capital', 500000)
        self.max_risk_per_trade = self.config.get('max_risk_per_trade', 0.02)
        self.max_portfolio_risk = self.config.get('max_portfolio_risk', 0.06)
        self.max_daily_loss = self.config.get('max_daily_loss', 0.05)
        self.max_drawdown = self.config.get('max_drawdown', 0.20)
        self.kelly_fraction_cap = self.config.get('kelly_fraction_cap', 0.25)
        self.max_open_positions = self.config.get('max_open_positions', 5)
        self.max_correlation = self.config.get('max_correlation', 0.7)
        self.min_position_size = self.config.get('min_position_size', 1)
        self.max_position_size = self.config.get('max_position_size', 20)
        
        # Track current state
        self.current_positions = []
        self.daily_pnl = 0
        self.peak_capital = self.account_capital
        self.strategy_performance = {}
        
    def calculate_kelly_position_size(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Calculate Kelly Criterion position size"""
        if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
            return 0.1  # Conservative fallback
            
        # Kelly formula: f = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - win_rate
        
        kelly_fraction = (b * p - q) / b
        
        # Cap Kelly fraction to prevent excessive leverage
        kelly_fraction = max(0, min(kelly_fraction, self.kelly_fraction_cap))
        
        return kelly_fraction
    
    def get_strategy_performance(self, strategy_name: str) -> Dict:
        """Get historical performance for a strategy"""
        if strategy_name not in self.strategy_performance:
            # Default performance for new strategies
            return {
                'trades': 10,
                'wins': 6,
                'avg_win': 0.025,
                'avg_loss': 0.015,
                'win_rate': 0.6
            }
        return self.strategy_performance[strategy_name]
    
    def update_strategy_performance(self, strategy_name: str, trade_pnl: float, trade_result: str):
        """Update strategy performance tracking"""
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_pnls': [],
                'loss_pnls': []
            }
        
        perf = self.strategy_performance[strategy_name]
        perf['trades'] += 1
        perf['total_pnl'] += trade_pnl
        
        if trade_result == 'WIN':
            perf['wins'] += 1
            perf['win_pnls'].append(trade_pnl)
        else:
            perf['loss_pnls'].append(abs(trade_pnl))
        
        # Calculate running averages
        perf['win_rate'] = perf['wins'] / perf['trades']
        perf['avg_win'] = np.mean(perf['win_pnls']) if perf['win_pnls'] else 0.02
        perf['avg_loss'] = np.mean(perf['loss_pnls']) if perf['loss_pnls'] else 0.015
    
    def calculate_position_size(self, signal, current_portfolio_value: float, 
                              historical_performance: Optional[Dict] = None) -> int:
        """Calculate optimal position size using multiple factors"""
        
        # Get strategy historical performance
        if historical_performance:
            perf = historical_performance
        else:
            perf = self.get_strategy_performance(signal.strategy)
        
        # Calculate Kelly fraction
        kelly_fraction = self.calculate_kelly_position_size(
            perf['win_rate'], perf['avg_win'], perf['avg_loss']
        )
        
        # Risk-based position sizing
        risk_per_share = abs(signal.entry_price - signal.stop_loss)
        max_risk_amount = current_portfolio_value * self.max_risk_per_trade
        
        if risk_per_share <= 0:
            return self.min_position_size
            
        risk_based_size = int(max_risk_amount / risk_per_share)
        
        # Kelly-based position sizing
        kelly_amount = current_portfolio_value * kelly_fraction
        kelly_based_size = int(kelly_amount / signal.entry_price)
        
        # Take the minimum of risk-based and Kelly-based
        position_size = min(risk_based_size, kelly_based_size)
        
        # Apply min/max constraints
        position_size = max(self.min_position_size, min(position_size, self.max_position_size))
        
        # Adjust for confidence and signal strength
        confidence_multiplier = (signal.confidence * signal.strength)
        position_size = int(position_size * confidence_multiplier)
        
        return max(self.min_position_size, position_size)
    
    def check_risk_limits(self, signal, current_portfolio_value: float) -> Dict[str, bool]:
        """Comprehensive risk limit checks"""
        checks = {
            'position_limit': True,
            'portfolio_risk': True,
            'daily_loss': True,
            'drawdown': True,
            'correlation': True,
            'market_hours': True
        }
        
        # Check maximum open positions
        if len(self.current_positions) >= self.max_open_positions:
            checks['position_limit'] = False
        
        # Check portfolio risk
        current_risk = sum(pos.get('risk_amount', 0) for pos in self.current_positions)
        new_risk = abs(signal.entry_price - signal.stop_loss) * signal.position_size
        total_risk = current_risk + new_risk
        
        if total_risk > current_portfolio_value * self.max_portfolio_risk:
            checks['portfolio_risk'] = False
        
        # Check daily loss limit
        if abs(self.daily_pnl) > current_portfolio_value * self.max_daily_loss:
            checks['daily_loss'] = False
        
        # Check drawdown limit
        current_drawdown = (self.peak_capital - current_portfolio_value) / self.peak_capital
        if current_drawdown > self.max_drawdown:
            checks['drawdown'] = False
        
        # Check correlation (simplified - would need price correlation matrix in production)
        symbol_exposure = {}
        for pos in self.current_positions:
            symbol = pos.get('symbol')
            if symbol:
                symbol_exposure[symbol] = symbol_exposure.get(symbol, 0) + 1
        
        if signal.symbol in symbol_exposure and symbol_exposure[signal.symbol] >= 2:
            checks['correlation'] = False
        
        # Check market hours (simplified check)
        current_time = datetime.now()
        if current_time.weekday() >= 5:  # Weekend
            checks['market_hours'] = False
        
        return checks
    
    def should_accept_signal(self, signal, current_portfolio_value: float) -> tuple:
        """Determine if signal should be accepted based on all risk criteria"""
        
        # Perform all risk checks
        risk_checks = self.check_risk_limits(signal, current_portfolio_value)
        
        # Check if all risk limits pass
        failed_checks = [check for check, passed in risk_checks.items() if not passed]
        
        if failed_checks:
            return False, f"Risk limits failed: {', '.join(failed_checks)}"
        
        # Additional quality filters
        if signal.risk_reward_ratio < 1.0:
            return False, "Risk-reward ratio too low"
        
        if signal.confidence < 0.5:
            return False, "Signal confidence too low"
        
        return True, "All risk checks passed"
    
    def add_position(self, signal, position_size: int, current_portfolio_value: float):
        """Add new position to tracking"""
        risk_amount = abs(signal.entry_price - signal.stop_loss) * position_size
        
        position = {
            'symbol': signal.symbol,
            'strategy': signal.strategy,
            'entry_time': signal.timestamp,
            'entry_price': signal.entry_price,
            'position_size': position_size,
            'risk_amount': risk_amount,
            'target_price': signal.target_price,
            'stop_loss': signal.stop_loss
        }
        
        self.current_positions.append(position)
    
    def remove_position(self, symbol: str, strategy: str):
        """Remove position from tracking"""
        self.current_positions = [
            pos for pos in self.current_positions 
            if not (pos['symbol'] == symbol and pos['strategy'] == strategy)
        ]
    
    def update_daily_pnl(self, pnl_change: float):
        """Update daily P&L tracking"""
        self.daily_pnl += pnl_change
        
        # Update peak capital if we're at new highs
        current_value = self.account_capital + self.daily_pnl
        if current_value > self.peak_capital:
            self.peak_capital = current_value
    
    def reset_daily_tracking(self):
        """Reset daily tracking for new trading day"""
        self.daily_pnl = 0
    
    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio risk summary"""
        total_positions = len(self.current_positions)
        total_risk = sum(pos.get('risk_amount', 0) for pos in self.current_positions)
        current_drawdown = (self.peak_capital - self.account_capital) / self.peak_capital
        
        return {
            'total_positions': total_positions,
            'total_risk_amount': total_risk,
            'total_risk_pct': total_risk / self.account_capital * 100,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl / self.account_capital * 100,
            'current_drawdown_pct': current_drawdown * 100,
            'available_capital': self.account_capital - total_risk,
            'max_new_positions': max(0, self.max_open_positions - total_positions)
        }

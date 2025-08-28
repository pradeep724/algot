import time
import uuid
from datetime import datetime, timedelta
from utils.logger import log
from utils.alerts import AlertManager

class SmartExecutionManager:
    def __init__(self, api_client, config):
        self.api = api_client
        self.config = config
        self.alert_manager = AlertManager(config)
        self.active_orders = {}
        self.positions = {}
        
        # Execution settings
        self.max_slippage = config['execution']['max_slippage_pct']
        self.retry_attempts = config['execution']['order_retry_attempts']
        self.partial_fill_threshold = config['execution']['partial_fill_threshold']

    def place_spread_trade(self, strategy_signal, option_chain):
        """Place a defined-risk spread trade with smart execution."""
        try:
            # Generate unique trade ID
            trade_id = str(uuid.uuid4())[:8]
            
            # Select optimal strikes from option chain
            legs = self._select_spread_legs(strategy_signal, option_chain)
            
            if not legs:
                log.error("Could not select appropriate spread legs")
                return None
                
            # Calculate spread parameters
            spread_details = self._calculate_spread_parameters(legs)
            
            # Risk check
            if not self._pre_execution_risk_check(spread_details):
                return None
                
            # Place orders with slippage protection
            order_results = self._place_spread_orders(trade_id, legs)
            
            if order_results:
                # Start monitoring the orders
                self._start_order_monitoring(trade_id, order_results)
                return trade_id
            else:
                return None
                
        except Exception as e:
            log.error(f"Error placing spread trade: {e}")
            return None

    def _select_spread_legs(self, signal, option_chain):
        """Select optimal strikes for spread trade."""
        try:
            # Find ATM strike
            spot_price = signal['spot_price']
            atm_strike = self._find_atm_strike(option_chain, spot_price)
            
            if signal['strategy_type'] == 'DebitSpreads':
                if signal['direction'] == 'bullish':
                    # Bull Call Spread
                    buy_leg = self._find_option_by_strike(option_chain, atm_strike, 'CE')
                    sell_leg = self._find_option_by_strike(option_chain, atm_strike + 100, 'CE')
                else:
                    # Bear Put Spread  
                    buy_leg = self._find_option_by_strike(option_chain, atm_strike, 'PE')
                    sell_leg = self._find_option_by_strike(option_chain, atm_strike - 100, 'PE')
                    
                return [
                    {'action': 'BUY', 'option': buy_leg},
                    {'action': 'SELL', 'option': sell_leg}
                ]
                
            elif signal['strategy_type'] == 'IronCondor':
                # Iron Condor - 4 legs
                wing_width = 100
                return [
                    {'action': 'SELL', 'option': self._find_option_by_strike(option_chain, atm_strike - 50, 'PE')},
                    {'action': 'BUY', 'option': self._find_option_by_strike(option_chain, atm_strike - 150, 'PE')},
                    {'action': 'SELL', 'option': self._find_option_by_strike(option_chain, atm_strike + 50, 'CE')},
                    {'action': 'BUY', 'option': self._find_option_by_strike(option_chain, atm_strike + 150, 'CE')}
                ]
                
        except Exception as e:
            log.error(f"Error selecting spread legs: {e}")
            return None

    def _find_atm_strike(self, option_chain, spot_price):
        """Find At-The-Money strike price."""
        strikes = [opt['strike'] for opt in option_chain]
        return min(strikes, key=lambda x: abs(x - spot_price))

    def _find_option_by_strike(self, option_chain, strike, option_type):
        """Find option by strike and type."""
        for option in option_chain:
            if option['strike'] == strike and option['type'] == option_type:
                return option
        return None

    def _calculate_spread_parameters(self, legs):
        """Calculate spread risk/reward parameters."""
        net_premium = 0
        max_loss = 0
        max_profit = 0
        
        for leg in legs:
            premium = leg['option']['ltp']
            if leg['action'] == 'BUY':
                net_premium -= premium  # Debit
            else:
                net_premium += premium  # Credit
                
        # For spreads, max loss is usually the net debit paid
        max_loss = abs(net_premium) if net_premium < 0 else 0
        
        # Max profit depends on spread type and width
        if len(legs) == 2:  # Simple spread
            strike_diff = abs(legs[0]['option']['strike'] - legs[1]['option']['strike'])
            max_profit = strike_diff - max_loss
            
        return {
            'net_premium': net_premium,
            'max_loss': max_loss,
            'max_profit': max_profit,
            'risk_reward_ratio': max_profit / max_loss if max_loss > 0 else 0
        }

    def _pre_execution_risk_check(self, spread_details):
        """Final risk check before execution."""
        # Check if risk-reward ratio is acceptable
        min_rr_ratio = 1.5  # Minimum 1.5:1 risk-reward
        
        if spread_details['risk_reward_ratio'] < min_rr_ratio:
            log.warning(f"Poor risk-reward ratio: {spread_details['risk_reward_ratio']:.2f}")
            return False
            
        # Check maximum loss limit
        max_trade_risk = self.config['risk']['account_capital'] * self.config['risk']['max_risk_per_trade_pct']
        
        if spread_details['max_loss'] > max_trade_risk:
            log.warning(f"Trade risk exceeds limit: {spread_details['max_loss']} > {max_trade_risk}")
            return False
            
        return True

    def _place_spread_orders(self, trade_id, legs):
        """Place all legs of spread order."""
        order_results = []
        
        for i, leg in enumerate(legs):
            try:
                # Prepare order parameters
                order_params = {
                    "variety": "NORMAL",
                    "tradingsymbol": leg['option']['symbol'],
                    "symboltoken": leg['option'].get('token', ''),
                    "transactiontype": leg['action'],
                    "exchange": "NFO",
                    "ordertype": "LIMIT",  # Use limit orders for better control
                    "producttype": "INTRADAY",
                    "duration": "DAY",
                    "quantity": str(self._calculate_quantity(leg)),
                    "price": str(self._calculate_limit_price(leg))
                }
                
                # Place order
                if self.config['mode'] == 'live':
                    result = self.api.placeOrder(order_params)
                    order_id = result.get('data', {}).get('orderid') if result.get('status') else None
                else:
                    # Paper trading
                    order_id = f"PAPER_{trade_id}_{i}"
                    log.info(f"PAPER TRADE: {order_params}")
                
                if order_id:
                    order_results.append({
                        'leg_index': i,
                        'order_id': order_id,
                        'leg': leg,
                        'order_params': order_params,
                        'status': 'PENDING'
                    })
                    
            except Exception as e:
                log.error(f"Error placing order for leg {i}: {e}")
                # Cancel any already placed orders
                self._cancel_partial_spread(order_results)
                return None
                
        return order_results

    def _calculate_quantity(self, leg):
        """Calculate quantity based on lot size."""
        # This would use the underlying instrument's lot size
        return 50  # Simplified - should be based on config

    def _calculate_limit_price(self, leg):
        """Calculate limit price with slippage buffer."""
        ltp = leg['option']['ltp']
        slippage_buffer = ltp * self.max_slippage
        
        if leg['action'] == 'BUY':
            return ltp + slippage_buffer
        else:
            return ltp - slippage_buffer

    def _start_order_monitoring(self, trade_id, order_results):
        """Start monitoring orders for fills."""
        self.active_orders[trade_id] = {
            'orders': order_results,
            'status': 'PENDING',
            'timestamp': datetime.now()
        }
        
        # In a real system, this would start a background thread to monitor
        log.info(f"Started monitoring trade {trade_id} with {len(order_results)} orders")

    def close_position(self, position_id, emergency=False):
        """Close an existing position."""
        try:
            if position_id not in self.positions:
                log.error(f"Position {position_id} not found")
                return False
                
            position = self.positions[position_id]
            
            # Create closing orders (opposite of opening)
            closing_orders = []
            for leg in position['legs']:
                opposite_action = 'SELL' if leg['action'] == 'BUY' else 'BUY'
                
                order_params = {
                    "variety": "NORMAL",
                    "tradingsymbol": leg['option']['symbol'],
                    "transactiontype": opposite_action,
                    "exchange": "NFO",
                    "ordertype": "MARKET" if emergency else "LIMIT",
                    "producttype": "INTRADAY",
                    "duration": "DAY",
                    "quantity": str(leg['quantity'])
                }
                
                if not emergency and self.config['mode'] != 'paper':
                    order_params["price"] = str(leg['option']['ltp'])
                
                # Place closing order
                if self.config['mode'] == 'live':
                    result = self.api.placeOrder(order_params)
                else:
                    result = {'status': True, 'data': {'orderid': f"CLOSE_{position_id}_{len(closing_orders)}"}}
                    log.info(f"PAPER CLOSE: {order_params}")
                
                if result.get('status'):
                    closing_orders.append(result['data']['orderid'])
                    
            # Update position status
            position['status'] = 'CLOSING'
            position['closing_orders'] = closing_orders
            
            log.info(f"Initiated closing of position {position_id}")
            return True
            
        except Exception as e:
            log.error(f"Error closing position {position_id}: {e}")
            return False

    def get_portfolio_summary(self):
        """Get current portfolio positions summary."""
        summary = {
            'total_positions': len(self.positions),
            'active_orders': len(self.active_orders),
            'positions': []
        }
        
        for pos_id, position in self.positions.items():
            pos_summary = {
                'position_id': pos_id,
                'strategy': position.get('strategy', 'Unknown'),
                'pnl': self._calculate_position_pnl(position),
                'status': position.get('status', 'OPEN')
            }
            summary['positions'].append(pos_summary)
            
        return summary

    def _calculate_position_pnl(self, position):
        """Calculate current P&L for a position."""
        # Simplified P&L calculation
        # In reality, would use current option prices vs entry prices
        return 0.0  # Placeholder

# engine/risk.py
import math

def position_size(total_capital: float, price: float, risk_per_trade: float, stop_dist: float, reserved_ratio: float = 0.20) -> int:
    """
    Computes quantity sized so that loss per trade <= (risk_per_trade * total_capital),
    but uses only the active capital (total_capital * (1 - reserved_ratio)) for exposure calculation.
    Returns integer quantity (rounded down).
    """
    if stop_dist <= 0:
        stop_dist = max(0.5, price * 0.01)

    active_capital = total_capital * (1.0 - reserved_ratio)
    risk_amt = total_capital * risk_per_trade          # risk defined on total capital (per config)
    # saner cap: don't allow position value > active_capital
    qty_by_risk = int(risk_amt / stop_dist) if stop_dist > 0 else 0

    # also cap by available capital / price to avoid using more than active capital
    max_qty_by_cap = int(active_capital / price) if price > 0 else 0

    qty = max(0, min(qty_by_risk, max_qty_by_cap))
    return qty

def default_sl_target(price: float, atr: float, atr_mult: float = 2.0, rr: float = 2.0, min_stop_abs: float = 0.5):
    """
    Returns (stop_price, target_price, stop_dist)
    For a LONG: stop_price = price - stop_dist; target_price = price + stop_dist*rr
    For a SHORT: analogous (caller should adapt sign).
    """
    stop_dist = max(atr * atr_mult, min_stop_abs)
    stop_price = price - stop_dist
    target_price = price + stop_dist * rr
    return stop_price, target_price, stop_dist

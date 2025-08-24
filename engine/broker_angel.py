# engine/broker_angel.py
from typing import Dict, List, Optional
import time
import os
from pydantic import BaseModel
import requests

# Angel One SmartAPI imports
try:
    from smartapi import SmartConnect  # type: ignore
except Exception:
    SmartConnect = None  # to avoid errors if not installed yet


class Order(BaseModel):
    symbol: str
    qty: int
    side: str                # "BUY" or "SELL"
    order_type: str = "MARKET"  # MARKET/LIMIT
    limit_price: Optional[float] = None
    variety: str = "NORMAL"     # NORMAL, AMO, STOPLOSS, etc.
    product: str = "INTRADAY"   # INTRADAY or DELIVERY
    exchange: str = "NSE"


class AngelBroker:
    """Thin wrapper over Angel One SmartAPI.

    You must supply api_key, client_code, password, and TOTP secret.

    Read: https://smartapi.angelbroking.com/

    """
    def __init__(self, api_key: str, client_code: str, password: str, totp_secret: str):
        assert SmartConnect is not None, "Install smartapi-python first."
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        self.sc = SmartConnect(api_key=self.api_key)
        self._login()

    def _login(self):
        # Angel requires TOTP for session; implement using pyotp if needed.
        try:
            import pyotp
        except Exception:
            raise RuntimeError("Please install pyotp for TOTP: pip install pyotp")
        totp = pyotp.TOTP(self.totp_secret).now()
        data = self.sc.generateSession(self.client_code, self.password, totp)
        self.feed_token = self.sc.getfeedToken()
        self.refresh_token = data.get("data", {}).get("refreshToken")

    def get_profile(self) -> Dict:
        return self.sc.getProfile()

    def quote_ltp(self, exchange: str, tradingsymbol: str) -> float:
        q = self.sc.ltpData(exchange=exchange, tradingsymbol=tradingsymbol, symboltoken=self._symbol_token(tradingsymbol))
        return float(q["data"]["ltp"])

    def historical_candles(self, exchange: str, symbol: str, interval: str, from_dt: str, to_dt: str) -> List[List]:
        """Returns list of [time, open, high, low, close, volume].
        interval: Angel names e.g., 'ONE_DAY','FIVE_MINUTE','ONE_MINUTE'
        Dates as 'YYYY-MM-DD HH:MM' in exchange timezone.
        """
        token = self._symbol_token(symbol)
        data = self.sc.getCandleData({
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_dt,
            "todate": to_dt
        })
        return data.get("data", [])

    def place_order(self, order: Order) -> str:
        params = dict(
            variety=order.variety,
            tradingsymbol=order.symbol,
            symboltoken=self._symbol_token(order.symbol),
            transactiontype="BUY" if order.side.upper().startswith("B") else "SELL",
            exchange=order.exchange,
            ordertype=order.order_type,
            producttype=order.product,
            duration="DAY",
            quantity=int(order.qty),
        )
        if order.order_type == "LIMIT" and order.limit_price:
            params["price"] = float(order.limit_price)
        resp = self.sc.placeOrder(params)
        if resp.get("status") and resp.get("data"):
            return str(resp["data"]["orderid"])
        raise RuntimeError(f"Order failed: {resp}")

    def positions(self):
        return self.sc.position()

    def _symbol_token(self, tradingsymbol: str) -> str:
        """Lookup token from Angel instruments dump. You must keep a local

        cache (CSV/JSON) of instrument tokens mapped to tradingsymbol.

        Implement your own lookup below.

        """
        # TODO: Replace with a real lookup. Placeholder token '0' will fail.
        return "0"

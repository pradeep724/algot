from typing import Dict, List, Optional
import random
import os
import pandas as pd
from pydantic import BaseModel
import time

# Angel One SmartAPI imports
try:
    from SmartApi import SmartConnect  # pip install smartapi-python
except Exception:
    SmartConnect = None  # fallback if not installed


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
    - Handles login with retry
    - Singleton instance
    - Auto-relogin on API failure
    - Loads instruments.csv for symboltoken lookup
    """

    _singleton = None  # singleton instance

    def __init__(self, api_key: str, client_code: str, password: str, totp_secret: str):
        assert SmartConnect is not None, "Install smartapi-python first."
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        self.instruments_path = "data/instruments.csv"
        self._instrument_df: Optional[pd.DataFrame] = None
        self._logged_in = False

        self.sc = SmartConnect(api_key=self.api_key)
        self._login()

    @classmethod
    def get_instance(cls, api_key: str, client_code: str, password: str, totp_secret: str):
        """Return singleton instance (reuse login session)."""
        if cls._singleton is None:
            cls._singleton = AngelBroker(api_key, client_code, password, totp_secret)
        return cls._singleton

    # ---------------- Login Handling ---------------- #
    def _login(self, max_retries: int = 5):
        """Login with TOTP, retries and exponential backoff."""
        try:
            import pyotp
        except Exception:
            raise RuntimeError("Please install pyotp for TOTP: pip install pyotp")

        # If already logged in and feed_token exists, reuse
        if getattr(self, "_logged_in", False) and getattr(self, "feed_token", None):
            return

        attempt = 0
        while attempt < max_retries:
            try:
                totp = pyotp.TOTP(self.totp_secret).now()
                data = self.sc.generateSession(self.client_code, self.password, totp)
                self.feed_token = self.sc.getfeedToken()
                self.refresh_token = data.get("data", {}).get("refreshToken")
                self._logged_in = True
                print(f"Login successful for {self.client_code}")
                return
            except Exception as e:
                wait_time = (2 ** attempt) * 5 + random.uniform(0, 1)
                print(f"Login attempt {attempt+1} failed: {e}. Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
                attempt += 1

        raise RuntimeError(f"Failed to login after {max_retries} attempts. Check credentials or rate limits.")

    def _ensure_login(self):
        """Ensure session is valid, relogin if necessary"""
        if not getattr(self, "_logged_in", False):
            print("Session expired or not logged in, relogging...")
            self._login()

    # ---------------- Symbol / Instrument Handling ---------------- #
    def _load_instruments(self) -> pd.DataFrame:
        """Lazy load instruments CSV into memory"""
        if self._instrument_df is None:
            if not os.path.exists(self.instruments_path):
                raise FileNotFoundError(
                    f"Instrument file not found: {self.instruments_path}. "
                    "Run tools/fetch_instruments.py first."
                )
            df = pd.read_csv(self.instruments_path)
            df["tradingsymbol"] = df["tradingsymbol"].astype(str).str.strip().str.upper()
            self._instrument_df = df
        return self._instrument_df

    def _normalize(self, symbol: str) -> str:
        """Remove common AngelOne suffixes (-EQ, -BE, etc.)"""
        s = symbol.strip().upper()
        for suffix in ["-EQ", "-BE", "-BZ", "-SM"]:
            if s.endswith(suffix):
                return s.replace(suffix, "")
        return s

    def _symbol_token(self, tradingsymbol: str) -> str:
        """Lookup token for a trading symbol (exact + fuzzy match)."""
        df = self._load_instruments()
        sym = tradingsymbol.strip().upper()

        # 1. Exact match
        match = df.loc[df["tradingsymbol"] == sym, "symboltoken"]
        if not match.empty:
            return str(match.iloc[0])

        # 2. Normalized suffix match
        sym_norm = self._normalize(sym)
        df_norm = df.copy()
        df_norm["norm"] = df_norm["tradingsymbol"].apply(self._normalize)
        match = df_norm.loc[df_norm["norm"] == sym_norm, "symboltoken"]

        if not match.empty:
            return str(match.iloc[0])

        raise KeyError(
            f"Symbol {tradingsymbol} not found in instruments.csv. "
            "Run tools/fetch_instruments.py to refresh."
        )

    # ---------------- API Methods ---------------- #
    def get_profile(self) -> Dict:
        self._ensure_login()
        return self.sc.getProfile()

    def quote_ltp(self, exchange: str, tradingsymbol: str) -> float:
        self._ensure_login()
        q = self.sc.ltpData(
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            symboltoken=self._symbol_token(tradingsymbol),
        )
        return float(q["data"]["ltp"])

    def historical_candles(
        self, exchange: str, symbol: str, interval: str, from_dt: str, to_dt: str, max_retries: int = 5
    ) -> List[List]:
        """Fetch OHLCV candles with automatic relogin and retry"""
        attempt = 0
        while attempt < max_retries:
            try:
                self._ensure_login()
                token = self._symbol_token(symbol)
                data = self.sc.getCandleData({
                    "exchange": exchange,
                    "symboltoken": token,
                    "interval": interval,
                    "fromdate": from_dt,
                    "todate": to_dt
                })
                if not data.get("status", True):
                    raise RuntimeError(data.get("message"))
                return data.get("data", [])
            except Exception as e:
                self._logged_in = False  # force relogin
                wait_time = (2 ** attempt) * 5 + random.uniform(0, 1)
                print(f"[{symbol} {interval}] API error: {e}. Retrying in {wait_time:.1f}s...")
                time.sleep(wait_time)
                attempt += 1
        raise RuntimeError(f"Failed to fetch {symbol} {interval} after {max_retries} retries.")

    def place_order(self, order: Order) -> str:
        self._ensure_login()
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
        self._ensure_login()
        return self.sc.position()

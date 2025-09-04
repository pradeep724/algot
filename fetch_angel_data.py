#!/usr/bin/env python3
"""
Angel One API Data Fetcher with Smart Data Management - Updated 2025
Production-grade script for fetching Indian market data with persistent storage
Fixed for latest Angel One API endpoints and requirements
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import time
import os
import logging
from dataclasses import dataclass
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    symbol: str

class AngelOneDataFetcher:
    """Professional Angel One API client with smart data management - Updated 2025"""
    
    def __init__(self, client_id: str, password: str, totp_secret: Optional[str] = None, api_key: Optional[str] = None):
        self.client_id = client_id
        self.password = password
        self.totp_secret = totp_secret
        self.api_key = api_key
        self.access_token = None
        self.refresh_token = None
        self.session = requests.Session()
        
        # Updated API endpoints (2025)
        self.base_url = "https://apiconnect.angelone.in"  # ✅ Updated URL
        self.auth_url = f"{self.base_url}/rest/auth/angelbroking/user/v1/loginByPassword"
        self.historical_url = f"{self.base_url}/rest/secure/angelbroking/historical/v1/getCandleData"
        self.ltp_url = f"{self.base_url}/rest/secure/angelbroking/order/v1/getLTP"
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1
        
        # Data management
        self.data_directory = Path("historical_data")
        self.data_directory.mkdir(exist_ok=True)
        
        # Updated symbol mapping for Indian indices (2025)
        self.index_symbols = {
            'NIFTY': '99926000',        # NSE:NIFTY 50
            'BANKNIFTY': '99926009',    # NSE:NIFTY BANK  
            'FINNIFTY': '99926037',     # NSE:NIFTY FIN SERVICE
            'MIDCPNIFTY': '99926074',   # NSE:NIFTY MID SELECT
            'SENSEX': '99919000'        # BSE:SENSEX
        }
        
    def rate_limit(self):
        """Enforce rate limiting between API calls"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def generate_totp(self) -> Optional[str]:
        """Generate TOTP code for 2FA authentication"""
        if not self.totp_secret:
            return None
        
        try:
            import pyotp
            totp = pyotp.TOTP(self.totp_secret)
            return totp.now()
        except ImportError:
            logger.warning("pyotp not installed. Install with: pip install pyotp")
            return None
        except Exception as e:
            logger.error(f"TOTP generation failed: {e}")
            return None
    
    def authenticate(self) -> bool:
        """Authenticate with Angel One API using updated endpoint"""
        try:
            totp_code = self.generate_totp()
            
            payload = {
                "clientcode": self.client_id,
                "password": self.password
            }
            
            if totp_code:
                payload["totp"] = totp_code
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00"
            }
            
            if self.api_key:
                headers["X-PrivateKey"] = self.api_key
            
            self.rate_limit()
            response = self.session.post(self.auth_url, json=payload, headers=headers)
            
            logger.debug(f"Auth response status: {response.status_code}")
            logger.debug(f"Auth response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("status"):
                    auth_data = data.get("data", {})
                    self.access_token = auth_data.get("jwtToken")
                    self.refresh_token = auth_data.get("refreshToken")
                    
                    # Update session headers with authentication
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-UserType": "USER",
                        "X-SourceID": "WEB",
                        "X-ClientLocalIP": "127.0.0.1",
                        "X-ClientPublicIP": "127.0.0.1",
                        "X-MACAddress": "00:00:00:00:00:00"
                    })
                    
                    if self.api_key:
                        self.session.headers["X-PrivateKey"] = self.api_key
                    
                    logger.info("✅ Authentication successful")
                    return True
                else:
                    logger.error(f"❌ Authentication failed: {data.get('message')}")
                    return False
            else:
                logger.error(f"❌ HTTP error during authentication: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Authentication exception: {e}")
            return False
    
    def get_latest_symbol_tokens(self):
        """Fetch and display latest symbol tokens from Angel One master file"""
        try:
            url = 'https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json'
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                instruments = response.json()
                
                logger.info("📊 Latest Symbol Tokens from Angel One:")
                for instrument in instruments:
                    name = instrument.get('name', '').upper()
                    symbol = instrument.get('symbol', '')
                    token = instrument.get('token', '')
                    exch_seg = instrument.get('exch_seg', '')
                    
                    if name in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY'] and exch_seg == 'NSE':
                        logger.info(f"  {name}: {token} (Symbol: {symbol})")
                    elif name == 'SENSEX' and exch_seg == 'BSE':
                        logger.info(f"  {name}: {token} (Symbol: {symbol})")
                        
        except Exception as e:
            logger.error(f"❌ Failed to fetch latest tokens: {e}")
    
    def get_symbol_token(self, symbol: str, exchange: str = "NSE") -> Optional[str]:
        """Get symbol token for API calls"""
        if symbol.upper() in self.index_symbols:
            return self.index_symbols[symbol.upper()]
        
        logger.warning(f"⚠️ Symbol token not found for {symbol}")
        logger.info("💡 Run get_latest_symbol_tokens() to see current tokens")
        return None
    
    def get_persistent_filename(self, symbol: str) -> Path:
        """Get persistent filename for a symbol"""
        return self.data_directory / f"{symbol}_historical.csv"
    
    def load_existing_data(self, symbol: str) -> pd.DataFrame:
        """Load existing historical data for a symbol"""
        filename = self.get_persistent_filename(symbol)
        
        if filename.exists():
            try:
                df = pd.read_csv(filename, index_col='Timestamp', parse_dates=True)
                logger.info(f"📊 Loaded existing  {len(df)} records for {symbol}")
                return df
            except Exception as e:
                logger.warning(f"⚠️ Failed to load existing data for {symbol}: {e}")
                return pd.DataFrame()
        else:
            logger.info(f"📝 No existing data file for {symbol}")
            return pd.DataFrame()
    
    def find_missing_date_ranges(self, symbol: str, requested_start: str, requested_end: str) -> List[tuple]:
        """Find which date ranges are missing from existing data"""
        existing_df = self.load_existing_data(symbol)
        
        if existing_df.empty:
            logger.info(f"📥 Will fetch entire date range for {symbol}")
            return [(requested_start, requested_end)]
        
        req_start = pd.to_datetime(requested_start).date()
        req_end = pd.to_datetime(requested_end).date()
        
        existing_dates = set(existing_df.index.date)
        existing_start = min(existing_dates)
        existing_end = max(existing_dates)
        
        missing_ranges = []
        
        # Check if we need data before existing range
        if req_start < existing_start:
            missing_ranges.append((
                req_start.strftime('%Y-%m-%d'), 
                (existing_start - timedelta(days=1)).strftime('%Y-%m-%d')
            ))
            logger.info(f"📅 Missing data before: {req_start} to {existing_start - timedelta(days=1)}")
        
        # Check if we need data after existing range  
        if req_end > existing_end:
            missing_ranges.append((
                (existing_end + timedelta(days=1)).strftime('%Y-%m-%d'),
                req_end.strftime('%Y-%m-%d')
            ))
            logger.info(f"📅 Missing data after: {existing_end + timedelta(days=1)} to {req_end}")
        
        if not missing_ranges:
            logger.info(f"✅ All requested data already exists for {symbol}")
        
        return missing_ranges
    
    def update_historical_data(self, symbol: str, new_df) -> pd.DataFrame:
        """Update historical data file with new data"""
        if not new_df:
            return pd.DataFrame()
        
        filename = self.get_persistent_filename(symbol)
        existing_df = self.load_existing_data(symbol)
        
        # Convert new data to DataFrame
        new_df_data = []
        for data in new_df:
            new_df_data.append({
                'Timestamp': data.timestamp,
                'Open': data.open,
                'High': data.high,
                'Low': data.low,
                'Close': data.close,
                'Volume': data.volume
            })
        
        new_df = pd.DataFrame(new_df_data)
        new_df.set_index('Timestamp', inplace=True)
        
        # Remove duplicates from new data
        new_df = new_df[~new_df.index.duplicated(keep='first')]
        
        if not existing_df.empty:
            # Find truly new timestamps
            missing_timestamps = new_df.index.difference(existing_df.index)
            
            if len(missing_timestamps) > 0:
                new_rows = new_df.loc[missing_timestamps]
                combined_df = pd.concat([existing_df, new_rows]).sort_index()
                logger.info(f"📈 Added {len(new_rows)} new records for {symbol}")
            else:
                combined_df = existing_df
                logger.info(f"ℹ️ No new data to add for {symbol}")
        else:
            combined_df = new_df
            logger.info(f"📝 Creating new historical file for {symbol}")
        
        # Save updated data
        combined_df.to_csv(filename)
        
        # Set attributes for compatibility
        combined_df.attrs['symbol'] = symbol
        combined_df.attrs['source'] = 'AngelOne'
        combined_df.attrs['last_updated'] = datetime.now()
        
        logger.info(f"✅ Updated {symbol}: total {len(combined_df)} records saved to {filename}")
        return combined_df
    
    def fetch_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = "1h", exchange: str = "NSE") -> List[MarketData]:
        """Fetch historical OHLCV data with updated 2025 API implementation"""
        
        if not self.access_token:
            raise RuntimeError("Not authenticated. Call authenticate() first.")
        
        symbol_token = self.get_symbol_token(symbol, exchange)
        if not symbol_token:
            logger.error(f"❌ Could not find symbol token for {symbol}")
            return []
        
        try:
            payload = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": f"{start_date} 09:15",
                "todate": f"{end_date} 15:30"
            }
            
            # Complete headers required by Angel One API 2025
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "X-PrivateKey": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-UserType": "USER",
                "X-SourceID": "WEB",
                "X-ClientLocalIP": "127.0.0.1",
                "X-ClientPublicIP": "127.0.0.1",
                "X-MACAddress": "00:00:00:00:00:00"
            }
            
            logger.debug(f"🔍 API Request for {symbol}:")
            logger.debug(f"   URL: {self.historical_url}")
            logger.debug(f"   Payload: {payload}")
            
            self.rate_limit()
            response = requests.post(self.historical_url, json=payload, headers=headers)
            
            logger.debug(f"📡 Response Status: {response.status_code}")
            logger.debug(f"📡 Response Text: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code} error for {symbol}")
                logger.error(f"Response: {response.text}")
                logger.error(f"Payload sent: {payload}")
                return []
            
            data = response.json()
            
            if not data.get("status", False):
                logger.error(f"❌ API error for {symbol}: {data.get('message', 'Unknown error')}")
                logger.error(f"Full API response: {data}")
                return []
            
            candles = data.get("data", [])
            if not candles:
                logger.warning(f"⚠️ No candle data returned for {symbol}")
                return []
            
            market_data = []
            for candle in candles:
                try:
                    # Handle different timestamp formats from Angel One
                    timestamp_str = candle[0]
                    if 'T' in timestamp_str:
                        # ISO format: 2025-09-01T09:15:00+05:30
                        timestamp = pd.to_datetime(timestamp_str)
                    else:
                        # Simple format: 2025-09-01 09:15:00
                        timestamp = pd.to_datetime(timestamp_str)
                    
                    market_data.append(MarketData(
                        timestamp=timestamp,
                        open=float(candle[1]),
                        high=float(candle[2]), 
                        low=float(candle[3]),
                        close=float(candle[4]),
                        volume=int(candle[5]),
                        symbol=symbol
                    ))
                except (ValueError, IndexError, TypeError) as e:
                    logger.warning(f"⚠️ Skipping malformed candle for {symbol}: {e}")
                    logger.debug(f"Problematic candle  {candle}")
                    continue
            
            logger.info(f"✅ Successfully fetched {len(market_data)} records for {symbol}")
            return market_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error fetching {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching {symbol}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []
    
    def fetch_and_update_historical_data(self, symbol: str, start_date: str, end_date: str, interval: str = "ONE_DAY") -> pd.DataFrame:
        """Smart fetch - only gets missing data and updates persistent file"""
        
        logger.info(f"🔍 Processing {symbol} for date range {start_date} to {end_date}")
        
        missing_ranges = self.find_missing_date_ranges(symbol, start_date, end_date)
        
        if not missing_ranges:
            logger.info(f"✅ {symbol}: All data already exists, loading from file")
            return self.load_existing_data(symbol)
        
        all_new_data = []
        for range_start, range_end in missing_ranges:
            logger.info(f"📥 Fetching missing data for {symbol}: {range_start} to {range_end}")
            
            range_data = self.fetch_historical_data(symbol, range_start, range_end, interval)
            if range_data:
                all_new_data.extend(range_data)
                logger.info(f"📈 Fetched {len(range_data)} records for {symbol} ({range_start} to {range_end})")
            else:
                logger.warning(f"⚠️ No data returned for {symbol} ({range_start} to {range_end})")
        
        if all_new_data:
            return self.update_historical_data(symbol, all_new_data)
        else:
            logger.warning(f"⚠️ No new data fetched for {symbol}")
            return self.load_existing_data(symbol)
    
    def get_live_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
      """Get current live price with improved error handling for Angel One API issues"""
    
      if not self.access_token:
        logger.error("Not authenticated")
        return None
    
      symbol_token = self.get_symbol_token(symbol, exchange)
      if not symbol_token:
        logger.warning(f"Symbol token not found for {symbol}")
        return None
    
      try:
        payload = {
            "exchange": exchange,
            "tradingsymbol": symbol,
            "symboltoken": symbol_token
        }
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00"
        }
        
        if self.api_key:
            headers["X-PrivateKey"] = self.api_key
        
        self.rate_limit()
        response = requests.post(self.ltp_url, json=payload, headers=headers, timeout=10)
        
        # ✅ Enhanced response validation
        if response.status_code != 200:
            logger.warning(f"HTTP {response.status_code} for {symbol} live price")
            return None
        
        # ✅ Check for empty response before JSON parsing
        if not response.text or not response.text.strip():
            logger.warning(f"Empty response received for {symbol} live price")
            return None
        
        # ✅ Safe JSON parsing with fallback
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response for {symbol}: {e}")
            logger.debug(f"Response text: '{response.text}'")
            return None
        
        # ✅ Validate API response structure
        if not isinstance(data, dict):
            logger.warning(f"Unexpected response format for {symbol}")
            return None
        
        if not data.get("status", False):
            error_msg = data.get("message", "Unknown API error")
            logger.warning(f"API error for {symbol}: {error_msg}")
            return None
        
        # ✅ Extract LTP with fallback options
        ltp_data = data.get("data", {})
        if not ltp_data:
            logger.warning(f"No data field in response for {symbol}")
            return None
        
        # Try multiple LTP fields (Angel One API inconsistency)
        ltp = ltp_data.get("ltp") or ltp_data.get("LTP") or ltp_data.get("lastPrice")
        
        if ltp is not None and ltp > 0:
            return float(ltp)
        else:
            logger.warning(f"Invalid LTP value ({ltp}) for {symbol}")
            return None
            
      except requests.exceptions.Timeout:
        logger.warning(f"Timeout getting live price for {symbol}")
        return None
      except requests.exceptions.RequestException as e:
        logger.error(f"Network error getting live price for {symbol}: {e}")
        return None
      except Exception as e:
        logger.error(f"Unexpected error getting live price for {symbol}: {e}")
        return None

    #def get_live_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
    #    """Get current live price for a symbol"""
    #    
    #    if not self.access_token:
    #        raise RuntimeError("Not authenticated")
    #    
    #    symbol_token = self.get_symbol_token(symbol, exchange)
    #    if not symbol_token:
    #        return None
    #    
    #    try:
    #        payload = {
    #            "exchange": exchange,
    #            "tradingsymbol": symbol,
    #            "symboltoken": symbol_token
    #        }
    #        
    #        headers = {
    #            "Authorization": f"Bearer {self.access_token}",
    #            "Content-Type": "application/json"
    #        }
    #        
    #        if self.api_key:
    #            headers["X-PrivateKey"] = self.api_key
    #        
    #        self.rate_limit()
    #        response = requests.post(self.ltp_url, json=payload, headers=headers)
    #        
    #        if response.status_code == 200:
    #            data = response.json()
    #            if data.get("status") and data.get("data"):
    #                return float(data["data"]["ltp"])
    #        
    #        logger.error(f"❌ Failed to get live price for {symbol}")
    #        return None
    #        
    #    except Exception as e:
    #        logger.error(f"❌ Exception getting live price for {symbol}: {e}")
    #        return None
    
    def save_to_csv(self, market_data, filename: str):
        """Save market data to CSV file"""
        
        if not market_data:
            logger.warning("⚠️ No data to save")
            return
        
        try:
            df_data = []
            for data in market_data:
                df_data.append({
                    'Timestamp': data.timestamp,
                    'Open': data.open,
                    'High': data.high,
                    'Low': data.low,
                    'Close': data.close,
                    'Volume': data.volume,
                    'Symbol': data.symbol
                })
            
            df = pd.DataFrame(df_data)
            df.to_csv(filename, index=False)
            logger.info(f"✅ Data saved to {filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save data to CSV: {e}")
    
    def save_to_algo_format(self, market_data, filename: str):
        """Save in format compatible with algo trading system"""
        
        if not market_data:
            logger.warning("⚠️ No data to save")
            return
        
        try:
            df_data = []
            for data in market_data:
                df_data.append({
                    'Timestamp': data.timestamp,
                    'Open': data.open,
                    'High': data.high,
                    'Low': data.low,
                    'Close': data.close,
                    'Volume': data.volume
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('Timestamp', inplace=True)
            df.attrs['symbol'] = market_data[0].symbol if market_data else 'UNKNOWN'
            df.attrs['source'] = 'AngelOne'
            df.attrs['fetch_time'] = datetime.now()
            
            # Save both pickle and CSV formats
            pickle_filename = filename.replace('.csv', '.pkl')
            df.to_pickle(pickle_filename)
            df.to_csv(filename)
            
            logger.info(f"✅ Algo-compatible data saved to {filename} and {pickle_filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save algo format  {e}")

def create_data_summary_report(data_dict: Dict[str, pd.DataFrame]):
    """Create a summary report of all updated data"""
    report_lines = []
    report_lines.append("# 📊 Historical Data Summary Report")
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    total_records = 0
    for symbol, df in data_dict.items():
        if not df.empty:
            total_records += len(df)
            report_lines.append(f"## {symbol}")
            report_lines.append(f"- **Records**: {len(df):,}")
            report_lines.append(f"- **Date Range**: {df.index.min().date()} to {df.index.max().date()}")
            report_lines.append(f"- **Latest Close**: ₹{df['Close'].iloc[-1]:,.2f}")
            report_lines.append(f"- **Average Volume**: {df['Volume'].mean():,.0f}")
            report_lines.append(f"- **File Size**: {os.path.getsize(f'historical_data/{symbol}_historical.csv')/1024:.1f} KB")
            report_lines.append("")
    
    report_lines.append(f"## Summary")
    report_lines.append(f"- **Total Indices**: {len(data_dict)}")
    report_lines.append(f"- **Total Records**: {total_records:,}")
    report_lines.append(f"- **Data Directory**: `historical_data/`")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("*Report generated by Angel One Data Fetcher v2025*")
    
    # Save report
    os.makedirs('historical_data', exist_ok=True)
    with open('historical_data/data_summary.md', 'w') as f:
        f.write('\n'.join(report_lines))
    
    logger.info("📋 Data summary report saved to historical_data/data_summary.md")

def main():
    """Main function with comprehensive data management"""
    
    logger.info("🚀 Angel One Data Fetcher v2025 - Starting...")
    
    # Load credentials from environment variables
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("📁 Loaded environment variables from .env file")
    except ImportError:
        logger.warning("⚠️ python-dotenv not found. Using system environment variables.")
    
    # Get credentials
    CLIENT_ID = os.getenv('ANGEL_CLIENT_ID')
    PASSWORD = os.getenv('ANGEL_PASSWORD') 
    TOTP_SECRET = os.getenv('ANGEL_TOTP_SECRET')
    API_KEY = os.getenv('ANGEL_API_KEY')
    
    # Validate credentials
    if not CLIENT_ID or not PASSWORD:
        logger.error("❌ Missing Angel One credentials!")
        logger.info("📝 Create a .env file with:")
        logger.info("   ANGEL_CLIENT_ID=your_client_id")
        logger.info("   ANGEL_PASSWORD=your_password")
        logger.info("   ANGEL_TOTP_SECRET=your_totp_secret")
        logger.info("   ANGEL_API_KEY=your_api_key")
        return
    
    if not API_KEY:
        logger.warning("⚠️ ANGEL_API_KEY not set - this may cause API errors")
    
    # Initialize fetcher
    fetcher = AngelOneDataFetcher(CLIENT_ID, PASSWORD, TOTP_SECRET, API_KEY)
    
    # Optional: Show latest symbol tokens
    logger.info("🔍 Checking latest symbol tokens...")
    fetcher.get_latest_symbol_tokens()
    
    # Authenticate
    logger.info("🔐 Authenticating with Angel One...")
    if not fetcher.authenticate():
        logger.error("❌ Authentication failed. Please check your credentials.")
        return
    
    # Define data requirements
    indices = ['NIFTY', 'BANKNIFTY', 'FINNIFTY']
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=600)).strftime('%Y-%m-%d')  # 3 months
    
    logger.info(f"📊 Updating historical data from {start_date} to {end_date}")
    logger.info(f"📈 Processing indices: {', '.join(indices)}")
    
    updated_data = {}
    
    for symbol in indices:
        logger.info(f"🎯 Processing {symbol}...")
        
        try:
            # Smart fetch - only gets missing data
            df = fetcher.fetch_and_update_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df.empty:
                updated_data[symbol] = df
                
                # Display summary
                logger.info(f"📊 {symbol} Summary:")
                logger.info(f"   📅 Date range: {df.index.min().date()} to {df.index.max().date()}")
                logger.info(f"   📈 Total records: {len(df):,}")
                logger.info(f"   💰 Latest close: ₹{df['Close'].iloc[-1]:,.2f}")
                logger.info(f"   📊 Avg volume: {df['Volume'].mean():,.0f}")
                
                # Optional: Get current live price for comparison
                try:
                    live_price = fetcher.get_live_price(symbol)
                    if live_price:
                        change = ((live_price - df['Close'].iloc[-1]) / df['Close'].iloc[-1]) * 100
                        logger.info(f"   💹 Live price: ₹{live_price:,.2f} ({change:+.2f}%)")
                except Exception:
                    pass  # Live price is optional
            else:
                logger.warning(f"⚠️ No data available for {symbol}")
            
            # Small delay between symbols to respect rate limits
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ Failed to update {symbol}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    # Final summary
    if updated_data:
        logger.info(f"✅ Data update completed successfully!")
        logger.info(f"📈 Updated {len(updated_data)} indices with total {sum(len(df) for df in updated_data.values()):,} records")
        
        # Create comprehensive summary report
        create_data_summary_report(updated_data)
        
        logger.info("📁 Files saved in 'historical_data/' directory:")
        for symbol in updated_data.keys():
            filename = f"historical_data/{symbol}_historical.csv"
            if os.path.exists(filename):
                size_kb = os.path.getsize(filename) / 1024
                logger.info(f"   📄 {filename} ({size_kb:.1f} KB)")
    else:
        logger.warning("⚠️ No data was updated. Check API credentials and network connection.")
    
    logger.info("🎉 Angel One Data Fetcher completed!")

if __name__ == "__main__":
    main()

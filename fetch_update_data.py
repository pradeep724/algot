import os
import time
import yaml
import pandas as pd
from datetime import datetime, timedelta
from SmartApi import SmartConnect
import pyotp
from logging import getLogger, StreamHandler, FileHandler, Formatter

# Setup logger
logger = getLogger("DataFetcher")
logger.setLevel("DEBUG")
ch = StreamHandler()
fh = FileHandler("data_fetcher.log")
fmt = Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(fmt)
fh.setFormatter(fmt)
logger.addHandler(ch)
logger.addHandler(fh)

def load_config(config_path='config.yaml'):
    with open(config_path) as f:
        return yaml.safe_load(f)

def connect_to_broker(cfg):
    api_key = cfg['api_key']
    client_id = cfg['client_id']
    pin = cfg['pin']
    totp_secret = cfg['totp_secret']

    api = SmartConnect(api_key=api_key)
    totp = pyotp.TOTP(totp_secret).now()
    data = api.generateSession(client_id, pin, totp)
    if data['status'] and 'jwtToken' in data['data']:
        logger.info("Successfully logged in to Angel One API")
        return api
    else:
        logger.error(f"Login failed: {data.get('message')}")
        return None

def fetch_and_update_data(api, instrument, token, data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    filename = os.path.join(data_dir, f"{instrument}_historical.csv")

    start_date = "2020-01-01 09:15"
    if os.path.isfile(filename):
        try:
            df_existing = pd.read_csv(filename, index_col='Timestamp', parse_dates=True)
            if not df_existing.empty:
                last_date = df_existing.index[-1].to_pydatetime()
                next_date = last_date + timedelta(days=1)
                # Only fetch from next_date if before today
                today = datetime.now()
                if next_date.date() >= today.date():
                    logger.info(f"{instrument} data is up to date")
                    return
                start_date = next_date.strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            logger.warning(f"Could not read existing CSV for {instrument}: {e}")
            # Proceed to full download

    end_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    logger.info(f"Fetching {instrument} data from {start_date} to {end_date}")

    params = {
        "variety": "NORMAL",
        "exchange": "NSE",
        "tradingsymbol": instrument,
        "fromdate": start_date,
        "todate": end_date,
        "interval": "1day"
    }

    try:
        # Adjust API call based on actual SmartAPI method signature
        # Using getCandleData similar to earlier example
        data = api.getCandleData({
            "exchange": "NSE",
            "symboltoken": token,
            "fromdate": start_date,
            "todate": end_date,
            "interval": "ONE_DAY"
        })
        if data['status']:
            df_new = pd.DataFrame(data['data'])
            df_new.columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
            df_new['Timestamp'] = pd.to_datetime(df_new['Timestamp'])
            df_new.set_index('Timestamp', inplace=True)

            if os.path.isfile(filename):
                df = pd.read_csv(filename, index_col='Timestamp', parse_dates=True)
                df = pd.concat([df, df_new])
                df = df[~df.index.duplicated(keep='last')]
                df.sort_index(inplace=True)
            else:
                df = df_new

            df.to_csv(filename)
            logger.info(f"Saved data for {instrument} with {len(df_new)} new rows")
        else:
            logger.error(f"Failed to fetch data for {instrument}: {data.get('message')}")
    except Exception as e:
        logger.error(f"Exception fetching data for {instrument}: {e}")

def main():
    cfg = load_config()
    api = connect_to_broker(cfg['api']['angel_one'])
    if not api:
        logger.error("Failed to connect to broker, exiting")
        return

    for instrument, info in cfg['universe'].items():
        fetch_and_update_data(api, instrument, info['token'])

if __name__ == '__main__':
    main()


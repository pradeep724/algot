# tools/fetch_instruments.py
import pandas as pd
import os
import requests

ANGEL_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

# List of index symbols you want to mark as indices
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYIT", "NIFTY50"]

def fetch_and_export(out_path: str = "data/instruments.csv"):
    """
    Fetch Angel One instrument dump (JSON), extract tradingsymbol and symboltoken,
    mark indices, and save to CSV for algo use.
    """
    print("📥 Fetching instrument dump from Angel One...")
    resp = requests.get(ANGEL_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Convert JSON list → DataFrame
    df = pd.DataFrame(data)

    # Ensure required fields exist
    if not {"symbol", "token"}.issubset(df.columns):
        raise ValueError(f"Unexpected columns in Angel dump: {df.columns}")

    # Keep only tradingsymbol + token
    df_out = df[["symbol", "token"]].rename(
        columns={"symbol": "tradingsymbol", "token": "symboltoken"}
    )

    # Add is_index column
    df_out["is_index"] = df_out["tradingsymbol"].isin(INDEX_SYMBOLS)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_out.to_csv(out_path, index=False)
    print(f"✅ Exported {len(df_out)} symbols to {out_path} with is_index flag")

if __name__ == "__main__":
    fetch_and_export()

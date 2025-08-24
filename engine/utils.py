#import toml

#def load_config(cfg_path="config/secrets.toml"):
#    try:
#        return toml.load(cfg_path)
#    except Exception as e:
#        print(f"❌ Error parsing {cfg_path}: {e}")
#        with open(cfg_path) as f:
#            lines = f.readlines()
#            for i, line in enumerate(lines, 1):
#                print(f"{i:03d}: {line.strip()}")
#        raise

# engine/utils.py
import toml, os, pandas as pd

def load_config():
    cfg_path = os.path.join("config", "secrets.toml")
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join("config", "settings.toml")
    print(cfg_path)
    return toml.load(cfg_path)

#def load_universe(path: str):
#    return list(pd.read_csv(path)["SYMBOL"].dropna().astype(str).unique())

def load_universe(path:str):
    df = pd.read_csv(path)

    # Ensure required columns exist
    if not {"tradingsymbol", "symboltoken"}.issubset(df.columns):
        raise ValueError("instruments.csv must have 'tradingsymbol' and 'symboltoken' columns")

    # Convert to list of dicts: [{symbol, token}, ...]
    universe = df[["tradingsymbol", "symboltoken"]].to_dict("records")
    return universe

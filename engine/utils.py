# engine/utils.py
import toml, os, pandas as pd

def load_config():
    cfg_path = os.path.join("config", "secrets.toml")
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join("config", "settings.toml")
    return toml.load(cfg_path)

def load_universe(path: str):
    return list(pd.read_csv(path)["SYMBOL"].dropna().astype(str).unique())

# Angel One Algo Starter (Python)

A practical starter to:
- Auto-select **intraday vs swing** based on market hours (IST).
- **Rank symbols** from your universe for each mode using robust technical scores.
- Optionally **re-rank with an LLM** (OpenAI/HF) if you provide an API key.
- Wire up to **Angel One SmartAPI** for quotes, candles, and order placement.

## 1) Setup
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2) Configure
- Copy `config/settings.toml` to `config/secrets.toml` and fill your credentials.
- Put your universe in `data/symbols.csv` (column: SYMBOL).

> **Angel Instrument Tokens:** Angel requires `symboltoken` for quotes/orders.
> Export their instrument dump once and keep a local CSV mapping `tradingsymbol -> token`.
> Replace the `_symbol_token()` method in `engine/broker_angel.py` to read from that CSV.

## 3) Scanning
```bash
python run_scan.py
```
This will choose **intraday** (09:15–15:30 IST) or **swing** (outside hours) and print top symbols.
Implement `fetch_history()` using `AngelBroker.getCandleData` to make it live.

## 4) Live Trading (PAPER FIRST)
- Flesh out `run_live.py` to call your scans and strategies, create orders with risk-based sizing, and send them to the broker.
- Add hard **kill-switches** and **logging**.

## 5) LLM Re‑ranking (Optional)
- Set `[llm].enabled=true` in `config/secrets.toml`.
- Export your key: `export OPENAI_API_KEY=...` (or `HF_API_TOKEN`).
- Implement your actual API call in `selector/auto_selector.llm_rerank` (kept minimal here).

## 6) Notes
- Always **paper trade** several weeks.
- Add costs: brokerage, STT, stamp duty, GST, SEBI fees, slippage.
- Ensure **compliance** with your broker’s API policy and SEBI rules.

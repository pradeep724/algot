import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os

ANALYSIS_DIR = "data/analysis"
os.makedirs(ANALYSIS_DIR, exist_ok=True)

def analyze_backtest(df: pd.DataFrame):
    """Compute metrics + generate PnL curve for backtest"""

    if df.empty:
        print("⚠️ No data for analysis")
        return

    # --- Basic Metrics ---
    total_trades = len(df)
    winners = df[df["pnl"] > 0]
    losers = df[df["pnl"] < 0]

    win_rate = len(winners) / total_trades * 100 if total_trades else 0
    avg_pnl = df["pnl"].mean()
    total_pnl = df["pnl"].sum()

    # --- Risk/Reward Metrics ---
    pnl_series = df["pnl"].cumsum()
    sharpe_ratio = (df["pnl"].mean() / df["pnl"].std()) * np.sqrt(252) if df["pnl"].std() != 0 else 0
    max_drawdown = (pnl_series.cummax() - pnl_series).max()

    # Print summary
    print("\n📊 Backtest Performance Summary")
    print(f"Total Trades   : {total_trades}")
    print(f"Win Rate       : {win_rate:.2f}%")
    print(f"Avg PnL        : {avg_pnl:.2f}")
    print(f"Total PnL      : {total_pnl:.2f}")
    print(f"Sharpe Ratio   : {sharpe_ratio:.2f}")
    print(f"Max Drawdown   : {max_drawdown:.2f}\n")

    # --- Plot Equity Curve ---
    plt.figure(figsize=(10, 5))
    pnl_series.plot(title="Equity Curve (PnL over Time)")
    plt.xlabel("Trades")
    plt.ylabel("Cumulative PnL")
    plt.grid()
    curve_file = os.path.join(ANALYSIS_DIR, "equity_curve.png")
    plt.savefig(curve_file)
    plt.close()

    print(f"📈 Equity curve saved → {curve_file}")

#!/usr/bin/env python3
"""Simple backtester for trading strategies on B3 data.

Tests realistic profitability with transaction costs and position sizing.

Usage:
  python backtest_strategies.py
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import json

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
ANALYSIS_DIR = DATA_DIR / "analysis"

# Backtesting parameters
COMMISSION_PCT = 0.05  # 0.05% per trade (realistic for B3)
SLIPPAGE_PCT = 0.02   # 0.02% entry/exit slippage
INITIAL_CAPITAL = 100_000  # R$ 100k
MAX_POSITION_SIZE = 0.05   # Max 5% of capital per position


def load_analysis_data() -> pd.DataFrame:
    """Load the pre-computed metrics dataset."""
    return pd.read_parquet(ANALYSIS_DIR / "liquidity_filtered_with_metrics.parquet")


def backtest_overnight_gap_reversal(df: pd.DataFrame) -> dict:
    """Strategy: Gap reversals (short large gaps, long gap-downs).

    Logic: Large overnight gaps tend to reverse intraday.
    """
    df = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)

    # Define trades: large gaps (>1% magnitude)
    df["signal"] = 0
    df.loc[df["gap_pct"] > 1.0, "signal"] = -1  # Short gap-ups (expect reversal down)
    df.loc[df["gap_pct"] < -1.0, "signal"] = 1  # Long gap-downs (expect reversal up)

    # Position sizing
    position_size = (INITIAL_CAPITAL * MAX_POSITION_SIZE) / (df["preabe"].mean())

    # Entry at open, exit at close
    df["entry_price"] = df["preabe"] * (1 + SLIPPAGE_PCT / 100)
    df["exit_price"] = df["preuln"] * (1 - SLIPPAGE_PCT / 100)

    # Trade returns (before commission)
    df["gross_ret"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"] * 100
    df["gross_ret"] *= df["signal"]  # Flip for shorts

    # Subtract commission
    df["net_ret"] = df["gross_ret"] - (2 * COMMISSION_PCT)  # Round trip

    # Equity curve
    df["equity"] = INITIAL_CAPITAL * (1 + (df[df["signal"] != 0]["net_ret"] / 100).cumsum())

    trades = df[df["signal"] != 0]

    return {
        "strategy": "gap_reversal",
        "description": "Short gap-ups, long gap-downs (expect intraday reversal)",
        "trades": len(trades),
        "win_rate": float((trades["net_ret"] > 0).sum() / len(trades) * 100),
        "avg_return_per_trade": float(trades["net_ret"].mean()),
        "total_return_pct": float((df["equity"].iloc[-1] / INITIAL_CAPITAL - 1) * 100),
        "sharpe_ratio": float(trades["net_ret"].std() / trades["net_ret"].mean() * np.sqrt(252)) if trades["net_ret"].mean() != 0 else np.nan,
    }


def backtest_high_volume_breakout(df: pd.DataFrame) -> dict:
    """Strategy: Trade in direction of high-volume days.

    Logic: Abnormally high volume often signals directional conviction.
    """
    df = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)

    # Signal: high volume → go long if price is up, short if down
    df["signal"] = 0
    high_vol = df["volume_ratio"] > df["volume_ratio"].quantile(0.75)
    df.loc[high_vol & (df["daily_ret_pct"] > 0), "signal"] = 1   # Long
    df.loc[high_vol & (df["daily_ret_pct"] < 0), "signal"] = -1  # Short

    # Trade next day (since signal comes from today's data)
    df["signal"] = df.groupby("codneg")["signal"].shift(1)

    # Entry next day open, exit at close
    df["entry_price"] = df.groupby("codneg")["preabe"].shift(-1) * (1 + SLIPPAGE_PCT / 100)
    df["exit_price"] = df.groupby("codneg")["preuln"].shift(-1) * (1 - SLIPPAGE_PCT / 100)

    # Calculate returns
    df["gross_ret"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"] * 100
    df["gross_ret"] *= df["signal"]
    df["net_ret"] = df["gross_ret"] - (2 * COMMISSION_PCT)

    trades = df[df["signal"] != 0].dropna()

    if len(trades) == 0:
        return {
            "strategy": "high_volume_breakout",
            "trades": 0,
            "error": "No signals generated"
        }

    return {
        "strategy": "high_volume_breakout",
        "description": "Trade direction of high-volume days (next day)",
        "trades": len(trades),
        "win_rate": float((trades["net_ret"] > 0).sum() / len(trades) * 100),
        "avg_return_per_trade": float(trades["net_ret"].mean()),
        "total_return_pct": float((trades["net_ret"].sum() / INITIAL_CAPITAL) * 100),
        "sharpe_ratio": float(trades["net_ret"].std() / trades["net_ret"].mean() * np.sqrt(252)) if trades["net_ret"].mean() != 0 else np.nan,
    }


def backtest_mean_reversion(df: pd.DataFrame) -> dict:
    """Strategy: Bet against extreme moves (mean reversion).

    Logic: Stocks that move >2% in a day tend to revert next day.
    """
    df = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)

    # Signal: extreme moves
    df["signal"] = 0
    extreme_threshold = df["daily_ret_pct"].std() * 2
    df.loc[df["daily_ret_pct"] > extreme_threshold, "signal"] = -1  # Short (expect down)
    df.loc[df["daily_ret_pct"] < -extreme_threshold, "signal"] = 1   # Long (expect up)

    # Trade next day
    df["signal"] = df.groupby("codneg")["signal"].shift(1)
    df["entry_price"] = df.groupby("codneg")["preabe"].shift(-1) * (1 + SLIPPAGE_PCT / 100)
    df["exit_price"] = df.groupby("codneg")["preuln"].shift(-1) * (1 - SLIPPAGE_PCT / 100)

    df["gross_ret"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"] * 100
    df["gross_ret"] *= df["signal"]
    df["net_ret"] = df["gross_ret"] - (2 * COMMISSION_PCT)

    trades = df[df["signal"] != 0].dropna()

    if len(trades) == 0:
        return {
            "strategy": "mean_reversion",
            "trades": 0,
            "error": "No signals generated"
        }

    return {
        "strategy": "mean_reversion",
        "description": "Fade extreme moves (short 2σ up, long 2σ down)",
        "trades": len(trades),
        "win_rate": float((trades["net_ret"] > 0).sum() / len(trades) * 100),
        "avg_return_per_trade": float(trades["net_ret"].mean()),
        "total_return_pct": float((trades["net_ret"].sum() / INITIAL_CAPITAL) * 100),
        "sharpe_ratio": float(trades["net_ret"].std() / trades["net_ret"].mean() * np.sqrt(252)) if trades["net_ret"].mean() != 0 else np.nan,
    }


def backtest_friday_monday_bias(df: pd.DataFrame) -> dict:
    """Strategy: Exploit day-of-week effects.

    Logic: Friday/Wednesday show slight positive bias; Monday is weaker.
    """
    df = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    df["dow"] = df["date"].dt.day_name()

    # Signal based on day of week
    df["signal"] = 0
    df.loc[df["dow"].isin(["Friday", "Wednesday"]), "signal"] = 1   # Long on strong days
    df.loc[df["dow"].isin(["Monday"]), "signal"] = -1              # Short on weak days

    df["entry_price"] = df["preabe"] * (1 + SLIPPAGE_PCT / 100)
    df["exit_price"] = df["preuln"] * (1 - SLIPPAGE_PCT / 100)

    df["gross_ret"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"] * 100
    df["gross_ret"] *= df["signal"]
    df["net_ret"] = df["gross_ret"] - (2 * COMMISSION_PCT)

    trades = df[df["signal"] != 0]

    return {
        "strategy": "day_of_week_bias",
        "description": "Long Fri/Wed, short Mon (calendar effect)",
        "trades": len(trades),
        "win_rate": float((trades["net_ret"] > 0).sum() / len(trades) * 100),
        "avg_return_per_trade": float(trades["net_ret"].mean()),
        "total_return_pct": float((trades["net_ret"].sum() / INITIAL_CAPITAL) * 100),
        "sharpe_ratio": float(trades["net_ret"].std() / trades["net_ret"].mean() * np.sqrt(252)) if trades["net_ret"].mean() != 0 else np.nan,
    }


def backtest_buy_and_hold(df: pd.DataFrame) -> dict:
    """Benchmark: simple buy-and-hold.

    Strategy: Buy all liquid stocks equally weighted, hold forever.
    """
    # Equal-weighted buy all
    df = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)

    # Returns (no timing, just daily returns)
    df["ret"] = df["daily_ret_pct"] - COMMISSION_PCT

    total_ret = df["ret"].sum() / len(df.groupby("codneg"))
    trades = len(df)

    return {
        "strategy": "buy_and_hold_benchmark",
        "description": "Equal-weighted long, hold forever",
        "trades": trades,
        "win_rate": float((df["ret"] > 0).sum() / len(df) * 100),
        "avg_return_per_trade": float(df["ret"].mean()),
        "total_return_pct": float(total_ret),
        "sharpe_ratio": float(df["ret"].std() / df["ret"].mean() * np.sqrt(252)) if df["ret"].mean() != 0 else np.nan,
    }


def main():
    print("="*80)
    print("B3 STRATEGY BACKTESTER")
    print("="*80)
    print(f"\nLoading analysis data...", flush=True)

    try:
        df = load_analysis_data()
    except FileNotFoundError:
        print("ERROR: Run analysis_overnight_anomaly.py first to generate data.")
        return 1

    print(f"  Records: {len(df):,}")
    print(f"  Date range: {df['date'].min().date()} → {df['date'].max().date()}")

    print(f"\nBacktesting parameters:")
    print(f"  Initial capital: R$ {INITIAL_CAPITAL:,}")
    print(f"  Commission: {COMMISSION_PCT}% per trade (round-trip: {2*COMMISSION_PCT}%)")
    print(f"  Slippage: {SLIPPAGE_PCT}%")
    print(f"  Max position size: {MAX_POSITION_SIZE*100:.1f}% of capital")

    print("\n" + "="*80)
    print("BACKTEST RESULTS")
    print("="*80)

    results = []

    print("\n1. GAP REVERSAL (short gap-ups, long gap-downs)")
    result = backtest_overnight_gap_reversal(df)
    if "error" not in result:
        print(f"   Trades: {result['trades']:,}  |  Win rate: {result['win_rate']:.1f}%")
        print(f"   Avg return/trade: {result['avg_return_per_trade']:+.3f}%")
        print(f"   Total return: {result['total_return_pct']:+.2f}%")
        if not np.isnan(result['sharpe_ratio']):
            print(f"   Sharpe ratio: {result['sharpe_ratio']:.2f}")
    results.append(result)

    print("\n2. HIGH VOLUME BREAKOUT (trade in direction of abnormal volume)")
    result = backtest_high_volume_breakout(df)
    if "error" not in result:
        print(f"   Trades: {result['trades']:,}  |  Win rate: {result['win_rate']:.1f}%")
        print(f"   Avg return/trade: {result['avg_return_per_trade']:+.3f}%")
        print(f"   Total return: {result['total_return_pct']:+.2f}%")
        if not np.isnan(result['sharpe_ratio']):
            print(f"   Sharpe ratio: {result['sharpe_ratio']:.2f}")
    results.append(result)

    print("\n3. MEAN REVERSION (fade extreme 2σ moves)")
    result = backtest_mean_reversion(df)
    if "error" not in result:
        print(f"   Trades: {result['trades']:,}  |  Win rate: {result['win_rate']:.1f}%")
        print(f"   Avg return/trade: {result['avg_return_per_trade']:+.3f}%")
        print(f"   Total return: {result['total_return_pct']:+.2f}%")
        if not np.isnan(result['sharpe_ratio']):
            print(f"   Sharpe ratio: {result['sharpe_ratio']:.2f}")
    results.append(result)

    print("\n4. DAY-OF-WEEK BIAS (long Fri/Wed, short Mon)")
    result = backtest_friday_monday_bias(df)
    if "error" not in result:
        print(f"   Trades: {result['trades']:,}  |  Win rate: {result['win_rate']:.1f}%")
        print(f"   Avg return/trade: {result['avg_return_per_trade']:+.3f}%")
        print(f"   Total return: {result['total_return_pct']:+.2f}%")
        if not np.isnan(result['sharpe_ratio']):
            print(f"   Sharpe ratio: {result['sharpe_ratio']:.2f}")
    results.append(result)

    print("\n5. BUY & HOLD BENCHMARK (equal-weighted long)")
    result = backtest_buy_and_hold(df)
    if "error" not in result:
        print(f"   Trades: {result['trades']:,}  |  Win rate: {result['win_rate']:.1f}%")
        print(f"   Avg return/trade: {result['avg_return_per_trade']:+.3f}%")
        print(f"   Total return: {result['total_return_pct']:+.2f}%")
        if not np.isnan(result['sharpe_ratio']):
            print(f"   Sharpe ratio: {result['sharpe_ratio']:.2f}")
    results.append(result)

    # Save results
    output_file = ANALYSIS_DIR / "backtest_results.json"
    with output_file.open("w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "parameters": {
                "initial_capital": INITIAL_CAPITAL,
                "commission_pct": COMMISSION_PCT,
                "slippage_pct": SLIPPAGE_PCT,
                "max_position_size": MAX_POSITION_SIZE,
            },
            "results": results,
        }, f, indent=2)

    print("\n" + "="*80)
    print(f"✓ Results saved to {output_file}")
    print("="*80)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Multi-strategy trading research framework for B3 data.

This is a general toolkit for testing various trading theories and patterns:
- Overnight gaps and weekend effects
- Mean reversion vs momentum
- Volume anomalies
- Seasonality and calendar patterns
- Any other article-based strategies

Run with: python analysis_overnight_anomaly.py
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
PARQUET_DIR = DATA_DIR / "parquet" / "cotahist"

# Filter thresholds
MIN_AVG_VOLUME_REAIS = 100_000  # Only liquid stocks
MIN_TRADING_DAYS = 252  # At least 1 year of data


def load_all_data() -> pd.DataFrame:
    """Load all COTAHIST years into one DataFrame."""
    files = sorted(PARQUET_DIR.glob("*.parquet"))
    dfs = [pd.read_parquet(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df = df.sort_values(["codneg", "date"]).reset_index(drop=True)
    return df


def filter_liquid_equities(df: pd.DataFrame, min_volume: float = MIN_AVG_VOLUME_REAIS) -> pd.DataFrame:
    """Keep only highly liquid spot equities to avoid delisted/tiny stock effects."""
    # Spot equities only
    df = df[(df["codbdi"] == "02") & (df["tpmerc"] == "010")].copy()

    # Filter by average daily volume in reais
    ticker_volumes = df.groupby("codneg")["voltot"].mean()
    liquid_tickers = ticker_volumes[ticker_volumes >= min_volume].index

    df = df[df["codneg"].isin(liquid_tickers)].copy()

    # Only tickers with enough history
    ticker_counts = df.groupby("codneg").size()
    established = ticker_counts[ticker_counts >= MIN_TRADING_DAYS].index
    df = df[df["codneg"].isin(established)]

    return df


def compute_returns_and_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily returns, gaps, and volatility metrics."""
    df = df.sort_values(["codneg", "date"]).reset_index(drop=True)

    # Gap and returns
    df["prev_close"] = df.groupby("codneg")["preuln"].shift(1)
    df["gap_pct"] = np.where(
        df["prev_close"] > 0,
        (df["preabe"] - df["prev_close"]) / df["prev_close"] * 100,
        np.nan
    )
    df["daily_ret_pct"] = np.where(
        df["preabe"] > 0,
        (df["preuln"] - df["preabe"]) / df["preabe"] * 100,
        np.nan
    )
    df["close_to_close_ret"] = np.where(
        df["prev_close"] > 0,
        (df["preuln"] - df["prev_close"]) / df["prev_close"] * 100,
        np.nan
    )

    # Volatility and range
    df["intraday_range_pct"] = np.where(
        df["premin"] > 0,
        (df["premax"] - df["premin"]) / df["premin"] * 100,
        np.nan
    )

    # Volume metrics
    df["volume_ma20"] = df.groupby("codneg")["quatot"].transform(
        lambda x: x.rolling(20, min_periods=1).mean()
    )
    df["volume_ratio"] = np.where(
        df["volume_ma20"] > 0,
        df["quatot"] / df["volume_ma20"],
        np.nan
    )

    # Remove rows without valid gap data
    return df[df["prev_close"].notna()].copy()


def test_overnight_anomaly(df: pd.DataFrame) -> dict:
    """Test: Do overnight gaps persist or mean-revert?"""
    # Filter valid data
    valid = df[["gap_pct", "daily_ret_pct"]].dropna()

    return {
        "strategy": "overnight_gap_anomaly",
        "description": "Test if overnight gaps predict same-day reversal",
        "sample_size": len(valid),
        "gap_mean": float(valid["gap_pct"].mean()),
        "gap_median": float(valid["gap_pct"].median()),
        "gap_up_pct": float((valid["gap_pct"] > 0).sum() / len(valid) * 100),
        "gap_corr_daily_ret": float(valid["gap_pct"].corr(valid["daily_ret_pct"])),
    }


def test_volume_anomaly(df: pd.DataFrame) -> dict:
    """Test: Do high-volume days predict direction changes?"""
    valid = df[["volume_ratio", "daily_ret_pct"]].dropna()

    high_vol = valid[valid["volume_ratio"] > valid["volume_ratio"].quantile(0.75)]
    low_vol = valid[valid["volume_ratio"] < valid["volume_ratio"].quantile(0.25)]

    return {
        "strategy": "volume_anomaly",
        "description": "Test if abnormal volume predicts returns",
        "high_vol_avg_return": float(high_vol["daily_ret_pct"].mean()),
        "low_vol_avg_return": float(low_vol["daily_ret_pct"].mean()),
        "high_vol_positive_pct": float((high_vol["daily_ret_pct"] > 0).sum() / len(high_vol) * 100),
        "low_vol_positive_pct": float((low_vol["daily_ret_pct"] > 0).sum() / len(low_vol) * 100),
    }


def test_mean_reversion(df: pd.DataFrame) -> dict:
    """Test: After extreme moves, do prices revert?"""
    valid = df[["codneg", "daily_ret_pct", "close_to_close_ret"]].dropna().copy()
    valid["next_close_to_close_ret"] = valid.groupby("codneg")["close_to_close_ret"].shift(-1)

    # Extreme down days
    extreme_down = valid[valid["daily_ret_pct"] < valid["daily_ret_pct"].quantile(0.10)]
    next_ret_after_down = extreme_down["next_close_to_close_ret"].dropna()

    # Extreme up days
    extreme_up = valid[valid["daily_ret_pct"] > valid["daily_ret_pct"].quantile(0.90)]
    next_ret_after_up = extreme_up["next_close_to_close_ret"].dropna()

    return {
        "strategy": "mean_reversion",
        "description": "Test if extreme moves are followed by reversals",
        "after_extreme_down_avg_ret": float(next_ret_after_down.mean()),
        "after_extreme_up_avg_ret": float(next_ret_after_up.mean()),
        "reversion_win_rate": float(
            ((next_ret_after_down < 0).sum() + (next_ret_after_up < 0).sum()) /
            (len(next_ret_after_down) + len(next_ret_after_up)) * 100
            if (len(next_ret_after_down) + len(next_ret_after_up)) > 0 else np.nan
        ),
    }


def test_day_of_week_effect(df: pd.DataFrame) -> dict:
    """Test: Are certain weekdays more profitable?"""
    df["dow"] = df["date"].dt.day_name()
    daily_stats = df.groupby("dow")["daily_ret_pct"].agg(["mean", "std", "count"])

    return {
        "strategy": "day_of_week_effect",
        "description": "Test if returns vary by day of week",
        "by_day": daily_stats.to_dict("index"),
    }


def test_volatility_anomaly(df: pd.DataFrame) -> dict:
    """Test: Does high intraday volatility predict next-day moves?"""
    df["volatility_ma20"] = df.groupby("codneg")["intraday_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=1).mean()
    )

    valid = df[["volatility_ma20", "daily_ret_pct"]].dropna()
    high_vol = valid[valid["volatility_ma20"] > valid["volatility_ma20"].quantile(0.75)]
    low_vol = valid[valid["volatility_ma20"] < valid["volatility_ma20"].quantile(0.25)]

    return {
        "strategy": "volatility_anomaly",
        "description": "Test if high volatility predicts larger moves",
        "high_vol_avg_intraday_range": float(high_vol["volatility_ma20"].mean()),
        "low_vol_avg_intraday_range": float(low_vol["volatility_ma20"].mean()),
        "high_vol_return_std": float(high_vol["daily_ret_pct"].std()),
        "low_vol_return_std": float(low_vol["daily_ret_pct"].std()),
    }


def main():
    print("="*80)
    print("B3 MULTI-STRATEGY TRADING RESEARCH")
    print("="*80)

    print("\nLoading COTAHIST data...", flush=True)
    df = load_all_data()
    print(f"  Total records: {len(df):,}")
    print(f"  Unique tickers: {df['codneg'].nunique()}")

    print(f"\nFiltering for liquid equities (volume ≥ R$ {MIN_AVG_VOLUME_REAIS:,})...", flush=True)
    df = filter_liquid_equities(df)
    print(f"  Liquid spot equities: {len(df):,} records")
    print(f"  Unique tickers: {df['codneg'].nunique()}")
    print(f"  Date range: {df['date'].min().date()} → {df['date'].max().date()}")

    print(f"\nComputing returns and metrics...", flush=True)
    df = compute_returns_and_gaps(df)
    print(f"  Valid analysis records: {len(df):,}")

    # Run all strategy tests
    print("\n" + "="*80)
    print("STRATEGY TEST RESULTS")
    print("="*80)

    strategies = []

    print("\n1. OVERNIGHT GAP ANOMALY")
    result = test_overnight_anomaly(df)
    print(f"   Gap mean: {result['gap_mean']:+.3f}%")
    print(f"   Gap up frequency: {result['gap_up_pct']:.1f}%")
    print(f"   Gap ↔ same-day return correlation: {result['gap_corr_daily_ret']:.4f}")
    strategies.append(result)

    print("\n2. VOLUME ANOMALY")
    result = test_volume_anomaly(df)
    print(f"   High volume days avg return: {result['high_vol_avg_return']:+.3f}%")
    print(f"   Low volume days avg return: {result['low_vol_avg_return']:+.3f}%")
    print(f"   High volume positive days: {result['high_vol_positive_pct']:.1f}%")
    strategies.append(result)

    print("\n3. MEAN REVERSION")
    result = test_mean_reversion(df)
    print(f"   After extreme down: next day avg return {result['after_extreme_down_avg_ret']:+.3f}%")
    print(f"   After extreme up: next day avg return {result['after_extreme_up_avg_ret']:+.3f}%")
    print(f"   Reversion win rate: {result['reversion_win_rate']:.1f}%")
    strategies.append(result)

    print("\n4. DAY-OF-WEEK EFFECT")
    result = test_day_of_week_effect(df)
    for day, stats in sorted(result["by_day"].items()):
        print(f"   {day:9s}: avg return {stats['mean']:+.3f}% (n={int(stats['count']):,})")
    strategies.append(result)

    print("\n5. VOLATILITY ANOMALY")
    result = test_volatility_anomaly(df)
    print(f"   High vol days return std: {result['high_vol_return_std']:.3f}%")
    print(f"   Low vol days return std: {result['low_vol_return_std']:.3f}%")
    strategies.append(result)

    # Save analysis dataset first; backtests run from the same data and also persist
    # detailed trades/equity curves.
    output_dir = DATA_DIR / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = output_dir / "liquidity_filtered_with_metrics.parquet"
    df.to_parquet(metrics_file)

    backtest_summary = None
    backtest_error = None
    try:
        from backtest_strategies import run_backtests

        backtest_summary = run_backtests(df=df, verbose=True)
        analysis_strategy_names = {strategy["strategy"] for strategy in strategies}
        backtested_names = set(backtest_summary.get("strategies_backtested", []))
        missing_backtests = sorted(analysis_strategy_names - backtested_names)
        failed_backtests = [
            result.get("strategy")
            for result in backtest_summary.get("results", [])
            if result.get("strategy") in analysis_strategy_names
            and (result.get("error") or result.get("trades", 0) <= 0)
        ]
        if missing_backtests:
            raise RuntimeError(f"Missing backtests for strategies: {missing_backtests}")
        if failed_backtests:
            raise RuntimeError(f"Backtests produced no trades or errored: {failed_backtests}")
    except Exception as exc:  # noqa: BLE001
        backtest_error = repr(exc)

    results_summary = {
        "timestamp": datetime.now().isoformat(),
        "data_scope": {
            "total_records": len(df),
            "unique_tickers": int(df["codneg"].nunique()),
            "date_range": [str(df["date"].min().date()), str(df["date"].max().date())],
            "filters": {
                "min_avg_volume_reais": MIN_AVG_VOLUME_REAIS,
                "min_trading_days": MIN_TRADING_DAYS,
            }
        },
        "strategies": strategies,
        "backtest": {
            "status": "ok" if backtest_error is None else "error",
            "error": backtest_error,
            "results_file": str(output_dir / "backtest_results.json"),
            "trades_file": str(output_dir / "backtest_trades.parquet"),
            "equity_curves_file": str(output_dir / "backtest_equity_curves.parquet"),
            "strategies_backtested": backtest_summary.get("strategies_backtested", []) if backtest_summary else [],
            "total_trade_rows": backtest_summary.get("total_trade_rows", 0) if backtest_summary else 0,
        },
    }

    with (output_dir / "strategy_results.json").open("w") as f:
        json.dump(results_summary, f, indent=2)

    print("\n" + "="*80)
    print(f"✓ Results saved to {output_dir / 'strategy_results.json'}")
    print(f"✓ Full data saved to {metrics_file}")
    if backtest_error is None:
        print(f"✓ Backtest results saved to {output_dir / 'backtest_results.json'}")
        print(f"✓ Backtest trades saved to {output_dir / 'backtest_trades.parquet'}")
    else:
        print(f"✗ Backtest failed: {backtest_error}")
    print("="*80)

    if backtest_error is not None:
        raise RuntimeError(f"Backtest failed: {backtest_error}")


if __name__ == "__main__":
    main()

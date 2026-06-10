#!/usr/bin/env python3
"""Systematic experimentation framework for trading hypotheses.

Approach: test many variations of each idea, find conditions where they work/fail.

Usage:
  python experiment_framework.py
"""

from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
import json
from dataclasses import dataclass, asdict

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
ANALYSIS_DIR = DATA_DIR / "analysis"
EXPERIMENTS_DIR = DATA_DIR / "experiments"
EXPERIMENTS_DIR.mkdir(exist_ok=True)

COMMISSION_PCT = 0.05
SLIPPAGE_PCT = 0.02


@dataclass
class Experiment:
    """Records one hypothesis test."""
    name: str
    hypothesis: str
    preconditions: dict  # what we're testing
    trades: int
    win_rate: float
    avg_return: float
    sharpe: float
    profitable: bool
    notes: str


def load_data() -> pd.DataFrame:
    """Load pre-computed metrics."""
    return pd.read_parquet(ANALYSIS_DIR / "liquidity_filtered_with_metrics.parquet")


def test_gap_reversal_by_magnitude(df: pd.DataFrame) -> list[Experiment]:
    """Test: does reversal strength depend on gap magnitude?"""
    results = []

    for gap_threshold in [0.5, 1.0, 1.5, 2.0, 3.0]:
        subset = df[df["gap_pct"].abs() > gap_threshold].copy()
        if len(subset) < 100:
            continue

        # Short gaps up, long gaps down
        subset["signal"] = np.where(subset["gap_pct"] > 0, -1, 1)
        subset["entry"] = subset["preabe"] * (1 + SLIPPAGE_PCT / 100)
        subset["exit"] = subset["preuln"] * (1 - SLIPPAGE_PCT / 100)

        subset["gross_ret"] = (subset["exit"] - subset["entry"]) / subset["entry"] * 100
        subset["gross_ret"] *= subset["signal"]
        subset["net_ret"] = subset["gross_ret"] - (2 * COMMISSION_PCT)

        wr = (subset["net_ret"] > 0).sum() / len(subset) * 100
        avg = subset["net_ret"].mean()
        sharpe = avg / subset["net_ret"].std() * np.sqrt(252) if subset["net_ret"].std() > 0 else 0

        results.append(Experiment(
            name="gap_reversal_by_magnitude",
            hypothesis=f"Gap reversals work better with larger gaps (>{gap_threshold}%)",
            preconditions={"gap_threshold": gap_threshold},
            trades=len(subset),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(subset):,} trades with gap >{gap_threshold}%"
        ))

    return results


def test_gap_reversal_by_volatility_regime(df: pd.DataFrame) -> list[Experiment]:
    """Test: does gap reversal work better in high/low volatility?"""
    results = []
    df = df.copy()

    # Define vol regimes
    df["vol_percentile"] = df.groupby("codneg")["intraday_range_pct"].transform(
        lambda x: x.rolling(20).apply(lambda y: y.std()).rank(pct=True)
    )

    for regime_name, condition in [
        ("high_vol", df["vol_percentile"] > 0.75),
        ("normal_vol", (df["vol_percentile"] >= 0.25) & (df["vol_percentile"] <= 0.75)),
        ("low_vol", df["vol_percentile"] < 0.25),
    ]:
        subset = df[condition & (df["gap_pct"].abs() > 0.5)].copy()
        if len(subset) < 100:
            continue

        subset["signal"] = np.where(subset["gap_pct"] > 0, -1, 1)
        subset["entry"] = subset["preabe"] * (1 + SLIPPAGE_PCT / 100)
        subset["exit"] = subset["preuln"] * (1 - SLIPPAGE_PCT / 100)

        subset["gross_ret"] = (subset["exit"] - subset["entry"]) / subset["entry"] * 100
        subset["gross_ret"] *= subset["signal"]
        subset["net_ret"] = subset["gross_ret"] - (2 * COMMISSION_PCT)

        wr = (subset["net_ret"] > 0).sum() / len(subset) * 100
        avg = subset["net_ret"].mean()
        sharpe = avg / subset["net_ret"].std() * np.sqrt(252) if subset["net_ret"].std() > 0 else 0

        results.append(Experiment(
            name="gap_reversal_by_vol_regime",
            hypothesis=f"Gap reversals work better in {regime_name}",
            preconditions={"volatility_regime": regime_name},
            trades=len(subset),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(subset):,} trades in {regime_name}"
        ))

    return results


def test_volume_breakout_by_holding_period(df: pd.DataFrame) -> list[Experiment]:
    """Test: volume signal work better with different holding periods?"""
    results = []

    for hold_days in [1, 2, 3, 5]:
        subset = df[df["volume_ratio"] > df["volume_ratio"].quantile(0.75)].copy()
        if len(subset) < 100:
            continue

        # Signal: buy if volume is high and price up, sell N days later
        subset["signal"] = np.where(subset["daily_ret_pct"] > 0, 1, -1)

        # Better: calculate forward returns properly
        subset = subset.sort_values(["codneg", "date"]).reset_index(drop=True)
        subset["future_close"] = subset.groupby("codneg")["preuln"].shift(-hold_days)

        # Can only trade if we have future data
        valid = subset[subset["future_close"].notna()].copy()
        if len(valid) < 100:
            continue

        # Entry at today's open, exit at future_close
        valid["entry"] = valid["preabe"] * (1 + SLIPPAGE_PCT / 100)
        valid["exit"] = valid["future_close"] * (1 - SLIPPAGE_PCT / 100)

        valid["gross_ret"] = (valid["exit"] - valid["entry"]) / valid["entry"] * 100
        valid["gross_ret"] *= valid["signal"]
        valid["net_ret"] = valid["gross_ret"] - (2 * COMMISSION_PCT)  # Same commission regardless of days

        wr = (valid["net_ret"] > 0).sum() / len(valid) * 100
        avg = valid["net_ret"].mean()
        sharpe = avg / valid["net_ret"].std() * np.sqrt(252) if valid["net_ret"].std() > 0 else 0

        results.append(Experiment(
            name="volume_breakout_by_holding",
            hypothesis=f"Volume signals work better holding {hold_days} days",
            preconditions={"holding_days": hold_days},
            trades=len(valid),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(valid):,} trades, {hold_days}-day hold"
        ))

    return results


def test_mean_reversion_by_extreme_level(df: pd.DataFrame) -> list[Experiment]:
    """Test: mean reversion only works on VERY extreme moves?"""
    results = []
    df = df.copy()

    for std_threshold in [1.0, 1.5, 2.0, 2.5, 3.0]:
        daily_std = df["daily_ret_pct"].std()
        extreme = df["daily_ret_pct"].abs() > (daily_std * std_threshold)

        subset = df[extreme].copy()
        if len(subset) < 100:
            continue

        # Next day trade
        subset["signal"] = np.where(subset["daily_ret_pct"] > 0, -1, 1)
        subset["entry"] = subset.groupby("codneg")["preabe"].shift(-1) * (1 + SLIPPAGE_PCT / 100)
        subset["exit"] = subset.groupby("codneg")["preuln"].shift(-1) * (1 - SLIPPAGE_PCT / 100)

        subset["gross_ret"] = (subset["exit"] - subset["entry"]) / subset["entry"] * 100
        subset["gross_ret"] *= subset["signal"]
        subset["net_ret"] = subset["gross_ret"] - (2 * COMMISSION_PCT)

        valid = subset[subset["entry"].notna()]
        if len(valid) < 50:
            continue

        wr = (valid["net_ret"] > 0).sum() / len(valid) * 100
        avg = valid["net_ret"].mean()
        sharpe = avg / valid["net_ret"].std() * np.sqrt(252) if valid["net_ret"].std() > 0 else 0

        results.append(Experiment(
            name="mean_reversion_by_extreme_level",
            hypothesis=f"Mean reversion only works on >{std_threshold}σ moves",
            preconditions={"std_threshold": std_threshold},
            trades=len(valid),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(valid):,} trades on >{std_threshold}σ moves"
        ))

    return results


def test_calendar_by_month(df: pd.DataFrame) -> list[Experiment]:
    """Test: calendar effects vary by month?"""
    results = []
    df = df.copy()
    df["month"] = df["date"].dt.month
    df["month_name"] = df["date"].dt.month_name()

    for month in range(1, 13):
        subset = df[df["month"] == month].copy()
        subset["signal"] = np.where(subset["daily_ret_pct"] > 0, 1, 0)
        subset["net_ret"] = subset["daily_ret_pct"] - COMMISSION_PCT

        wr = (subset["net_ret"] > 0).sum() / len(subset) * 100
        avg = subset["net_ret"].mean()
        sharpe = avg / subset["net_ret"].std() * np.sqrt(252) if subset["net_ret"].std() > 0 else 0

        month_name = subset["month_name"].iloc[0]

        results.append(Experiment(
            name="calendar_by_month",
            hypothesis=f"Returns vary by month (testing {month_name})",
            preconditions={"month": month},
            trades=len(subset),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(subset):,} trades in {month_name}"
        ))

    return results


def test_liquidity_effect(df: pd.DataFrame) -> list[Experiment]:
    """Test: does strategy work better on more liquid stocks?"""
    results = []
    df = df.copy()

    # Define liquidity tiers
    df["liquidity"] = df.groupby("codneg")["voltot"].transform(lambda x: x.rolling(20).mean())

    for tier_name, condition in [
        ("most_liquid", df["liquidity"] > df["liquidity"].quantile(0.75)),
        ("high_liquid", df["liquidity"] > df["liquidity"].quantile(0.5)),
        ("mid_liquid", df["liquidity"] > df["liquidity"].quantile(0.25)),
        ("least_liquid", df["liquidity"] <= df["liquidity"].quantile(0.25)),
    ]:
        subset = df[condition & (df["gap_pct"].abs() > 0.5)].copy()
        if len(subset) < 100:
            continue

        subset["signal"] = np.where(subset["gap_pct"] > 0, -1, 1)
        subset["net_ret"] = subset["daily_ret_pct"] * subset["signal"] - (2 * COMMISSION_PCT)

        wr = (subset["net_ret"] > 0).sum() / len(subset) * 100
        avg = subset["net_ret"].mean()
        sharpe = avg / subset["net_ret"].std() * np.sqrt(252) if subset["net_ret"].std() > 0 else 0

        results.append(Experiment(
            name="gap_reversal_by_liquidity",
            hypothesis=f"Gap reversal works better with {tier_name} stocks",
            preconditions={"liquidity_tier": tier_name},
            trades=len(subset),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(subset):,} trades on {tier_name} stocks"
        ))

    return results


def test_gap_reversal_out_of_sample(df: pd.DataFrame) -> dict:
    """CRITICAL: Does gap reversal work on recent data (2024-2026)?"""
    recent = df[df["date"] >= "2024-01-01"].copy()
    train = df[df["date"] < "2024-01-01"].copy()

    if len(recent) < 100:
        return {"strategy": "oos_test", "error": "Not enough recent data"}

    # Use 2% threshold found to be profitable
    recent["signal"] = 0
    recent.loc[recent["gap_pct"] > 2.0, "signal"] = -1
    recent.loc[recent["gap_pct"] < -2.0, "signal"] = 1

    recent["entry"] = recent["preabe"] * (1 + SLIPPAGE_PCT / 100)
    recent["exit"] = recent["preuln"] * (1 - SLIPPAGE_PCT / 100)
    recent["gross_ret"] = (recent["exit"] - recent["entry"]) / recent["entry"] * 100
    recent["gross_ret"] *= recent["signal"]
    recent["net_ret"] = recent["gross_ret"] - (2 * COMMISSION_PCT)

    trades = recent[recent["signal"] != 0]

    if len(trades) < 50:
        return {"strategy": "oos_test", "error": "Too few trades"}

    wr = (trades["net_ret"] > 0).sum() / len(trades) * 100
    avg = trades["net_ret"].mean()

    # Also show what we found on training data
    train["signal"] = 0
    train.loc[train["gap_pct"] > 2.0, "signal"] = -1
    train.loc[train["gap_pct"] < -2.0, "signal"] = 1
    train["net_ret"] = (train["gap_pct"] * -train["signal"]) - (2 * COMMISSION_PCT)
    train_trades = train[train["signal"] != 0]
    train_wr = (train_trades["net_ret"] > 0).sum() / len(train_trades) * 100
    train_avg = train_trades["net_ret"].mean()

    return {
        "strategy": "gap_reversal_out_of_sample",
        "description": "Gap reversal on recent (2024-2026) vs historical (1986-2023) data",
        "train_period": f"1986-2023",
        "test_period": f"2024-2026",
        "train_avg_return": float(train_avg),
        "train_win_rate": float(train_wr),
        "train_trades": int(len(train_trades)),
        "test_avg_return": float(avg),
        "test_win_rate": float(wr),
        "test_trades": int(len(trades)),
        "edge_survived": avg > 0,
        "conclusion": "VALIDATED" if abs(avg - train_avg) < 0.3 and avg > 0 else "FAILED or DEGRADED"
    }


def test_gap_reversal_by_market_regime(df: pd.DataFrame) -> list[Experiment]:
    """Does gap reversal work in bull vs bear markets?"""
    results = []
    df = df.copy()

    # Define bull/bear by 252-day return trend
    df["annual_ret"] = df.groupby("codneg")["close_to_close_ret"].transform(
        lambda x: x.rolling(252).sum()
    )

    for regime_name, condition in [
        ("bull_market", df["annual_ret"] > 0),
        ("bear_market", df["annual_ret"] < 0),
    ]:
        subset = df[condition & (df["gap_pct"].abs() > 2.0)].copy()
        if len(subset) < 100:
            continue

        subset["signal"] = np.where(subset["gap_pct"] > 0, -1, 1)
        subset["entry"] = subset["preabe"] * (1 + SLIPPAGE_PCT / 100)
        subset["exit"] = subset["preuln"] * (1 - SLIPPAGE_PCT / 100)
        subset["gross_ret"] = (subset["exit"] - subset["entry"]) / subset["entry"] * 100
        subset["gross_ret"] *= subset["signal"]
        subset["net_ret"] = subset["gross_ret"] - (2 * COMMISSION_PCT)

        wr = (subset["net_ret"] > 0).sum() / len(subset) * 100
        avg = subset["net_ret"].mean()
        sharpe = avg / subset["net_ret"].std() * np.sqrt(252) if subset["net_ret"].std() > 0 else 0

        results.append(Experiment(
            name="gap_reversal_by_market_regime",
            hypothesis=f"Gap reversal works in {regime_name}",
            preconditions={"market_regime": regime_name},
            trades=len(subset),
            win_rate=wr,
            avg_return=avg,
            sharpe=sharpe,
            profitable=avg > 0,
            notes=f"{len(subset):,} trades in {regime_name}"
        ))

    return results


def main():
    print("="*80)
    print("TRADING HYPOTHESIS EXPERIMENTATION FRAMEWORK")
    print("="*80)
    print("\nLoading data...", flush=True)
    df = load_data()

    all_experiments = []

    # CRITICAL: Out-of-sample test
    print("\n🔬 CRITICAL: Out-of-Sample Validation (2024-2026)...", flush=True)
    oos_result = test_gap_reversal_out_of_sample(df)
    print(f"   Training edge (1986-2023): {oos_result['train_avg_return']:+.3f}%")
    print(f"   Test edge (2024-2026): {oos_result['test_avg_return']:+.3f}%")
    print(f"   Conclusion: {oos_result['conclusion']}")

    print("\n1. Testing gap reversal by gap magnitude...")
    all_experiments.extend(test_gap_reversal_by_magnitude(df))

    print("2. Testing gap reversal by market regime (bull vs bear)...")
    all_experiments.extend(test_gap_reversal_by_market_regime(df))

    print("3. Testing gap reversal by volatility regime...")
    all_experiments.extend(test_gap_reversal_by_volatility_regime(df))

    print("3. Testing volume breakout by holding period...")
    all_experiments.extend(test_volume_breakout_by_holding_period(df))

    print("4. Testing mean reversion by extreme level...")
    all_experiments.extend(test_mean_reversion_by_extreme_level(df))

    print("5. Testing calendar effects by month...")
    all_experiments.extend(test_calendar_by_month(df))

    print("6. Testing liquidity effects...")
    all_experiments.extend(test_liquidity_effect(df))

    # Summary
    print("\n" + "="*80)
    print("EXPERIMENT RESULTS SUMMARY")
    print("="*80)

    profitable = [e for e in all_experiments if e.profitable]
    unprofitable = [e for e in all_experiments if not e.profitable]

    print(f"\n✅ PROFITABLE CONDITIONS ({len(profitable)}/{len(all_experiments)}):")
    for exp in sorted(profitable, key=lambda x: x.avg_return, reverse=True)[:10]:
        print(f"  • {exp.name}: {exp.preconditions}")
        print(f"    Avg return: {exp.avg_return:+.3f}% | Win rate: {exp.win_rate:.1f}% | {exp.notes}")

    print(f"\n❌ UNPROFITABLE/LOSING ({len(unprofitable)}):")
    for exp in sorted(unprofitable, key=lambda x: x.avg_return)[:5]:
        print(f"  • {exp.name}: {exp.preconditions}")
        print(f"    Avg return: {exp.avg_return:+.3f}% | Win rate: {exp.win_rate:.1f}% | {exp.notes}")

    # Key insights
    print(f"\n" + "="*80)
    print("KEY INSIGHTS (conditions that matter):")
    print("="*80)

    # Group by name to find patterns
    by_strategy = {}
    for exp in all_experiments:
        if exp.name not in by_strategy:
            by_strategy[exp.name] = []
        by_strategy[exp.name].append(exp)

    for strategy_name, experiments in by_strategy.items():
        profitable_variants = [e for e in experiments if e.profitable]
        if profitable_variants:
            variance = max(e.avg_return for e in experiments) - min(e.avg_return for e in experiments)
            print(f"\n{strategy_name}:")
            print(f"  Profitable in {len(profitable_variants)}/{len(experiments)} conditions")
            print(f"  Return variance: {variance:.3f}% (suggests strong pre-conditions)")
            print(f"  Best condition: {profitable_variants[0].preconditions} ({profitable_variants[0].avg_return:+.3f}%)")

    # Save
    output_file = EXPERIMENTS_DIR / "experiments.json"
    with output_file.open("w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_experiments": len(all_experiments),
            "profitable": len(profitable),
            "experiments": [asdict(e) for e in all_experiments],
        }, f, indent=2, default=str)

    print(f"\n✓ All experiments saved to {output_file}")


if __name__ == "__main__":
    main()

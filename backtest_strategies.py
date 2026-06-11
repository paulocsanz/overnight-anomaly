#!/usr/bin/env python3
"""Backtest all registered B3 strategies with trade/equity output.

Tests realistic profitability with transaction costs, slippage, and fixed
position sizing. Writes both aggregate summaries and detailed backtest data.

Usage:
  python backtest_strategies.py
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
ANALYSIS_DIR = DATA_DIR / "analysis"

# Backtesting parameters
COMMISSION_PCT = 0.05  # 0.05% per side (realistic for B3)
SLIPPAGE_PCT = 0.02    # 0.02% entry/exit slippage
INITIAL_CAPITAL = 100_000  # R$ 100k
MAX_POSITION_SIZE = 0.05   # Max 5% of capital per position

# Production-oriented extreme gap fade filters.
EXTREME_GAP_PCT = 5.0
EXTREME_GAP_MIN_ADV20_REAIS = 10_000_000
EXTREME_GAP_VOL_MULT = 1.5
EXTREME_GAP_SLIPPAGE_PCT = 0.10  # Wider spreads/impact on B3 gap opens.

SHOCK_GAP_PCT = 12.0
SHOCK_GAP_MIN_ADV20_REAIS = 1_000_000
SHOCK_GAP_VOL_MULT = 3.0
SHOCK_GAP_MIN_PREV_CLOSE = 2.0

TRADE_COLUMNS = [
    "strategy",
    "date",
    "codneg",
    "signal",
    "side",
    "entry_price",
    "exit_price",
    "gross_ret_pct",
    "net_ret_pct",
    "position_value",
    "pnl",
    "equity",
    "reason",
]
EQUITY_COLUMNS = ["strategy", "date", "daily_pnl", "equity", "cum_return_pct"]


BacktestFn = Callable[[pd.DataFrame], tuple[dict, pd.DataFrame, pd.DataFrame]]


def load_analysis_data() -> pd.DataFrame:
    """Load the pre-computed metrics dataset."""
    return pd.read_parquet(ANALYSIS_DIR / "liquidity_filtered_with_metrics.parquet")


def safe_float(value) -> float | None:
    """Convert numpy/pandas scalars to JSON-safe floats."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def sanitize_for_json(obj):
    """Recursively make objects strict-JSON serializable."""
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [sanitize_for_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return safe_float(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    if isinstance(obj, float):
        return safe_float(obj)
    return obj


def _empty_trades() -> pd.DataFrame:
    return pd.DataFrame(columns=TRADE_COLUMNS)


def _empty_equity_curve(strategy: str) -> pd.DataFrame:
    return pd.DataFrame(columns=EQUITY_COLUMNS).assign(strategy=strategy)


def _empty_result(strategy: str, description: str, error: str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    return {
        "strategy": strategy,
        "description": description,
        "trades": 0,
        "win_rate": None,
        "avg_return_per_trade": None,
        "total_pnl": 0.0,
        "total_return_pct": 0.0,
        "sharpe_ratio": None,
        "error": error,
    }, _empty_trades(), _empty_equity_curve(strategy)


def _apply_entry_exit_prices(df: pd.DataFrame, slippage_pct: float = SLIPPAGE_PCT) -> pd.DataFrame:
    """Apply signal-aware slippage and compute trade returns.

    Long: buy at open + slippage, sell at close - slippage.
    Short: sell at open - slippage, buy to cover at close + slippage.
    """
    out = df.copy()
    s = slippage_pct / 100
    long_mask = out["signal"] > 0
    short_mask = out["signal"] < 0

    out["entry_price"] = np.nan
    out["exit_price"] = np.nan
    out.loc[long_mask, "entry_price"] = out.loc[long_mask, "preabe"] * (1 + s)
    out.loc[long_mask, "exit_price"] = out.loc[long_mask, "preuln"] * (1 - s)
    out.loc[short_mask, "entry_price"] = out.loc[short_mask, "preabe"] * (1 - s)
    out.loc[short_mask, "exit_price"] = out.loc[short_mask, "preuln"] * (1 + s)

    out["gross_ret_pct"] = np.where(
        out["signal"] > 0,
        (out["exit_price"] - out["entry_price"]) / out["entry_price"] * 100,
        (out["entry_price"] - out["exit_price"]) / out["entry_price"] * 100,
    )
    out["net_ret_pct"] = out["gross_ret_pct"] - (2 * COMMISSION_PCT)
    return out


def _finalize_trades(strategy: str, description: str, df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    trades = df[df["signal"].fillna(0) != 0].copy()
    trades = trades.replace([np.inf, -np.inf], np.nan)
    trades = trades.dropna(subset=["date", "codneg", "signal", "entry_price", "exit_price", "net_ret_pct"])

    if trades.empty:
        return _empty_result(strategy, description, "No signals generated")

    trades = trades.sort_values(["date", "codneg"]).reset_index(drop=True)
    trades["strategy"] = strategy
    trades["side"] = np.where(trades["signal"] > 0, "long", "short")
    if "reason" not in trades.columns:
        trades["reason"] = "signal"
    trades["position_value"] = INITIAL_CAPITAL * MAX_POSITION_SIZE
    trades["pnl"] = trades["position_value"] * trades["net_ret_pct"] / 100
    trades["equity"] = INITIAL_CAPITAL + trades["pnl"].cumsum()

    daily = trades.groupby("date", as_index=False)["pnl"].sum().rename(columns={"pnl": "daily_pnl"})
    daily["strategy"] = strategy
    daily["equity"] = INITIAL_CAPITAL + daily["daily_pnl"].cumsum()
    daily["cum_return_pct"] = (daily["equity"] / INITIAL_CAPITAL - 1) * 100
    equity_curve = daily[EQUITY_COLUMNS]

    returns = trades["net_ret_pct"]
    mean_ret = returns.mean()
    std_ret = returns.std()
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret and std_ret > 0 else np.nan
    total_pnl = trades["pnl"].sum()

    result = {
        "strategy": strategy,
        "description": description,
        "trades": int(len(trades)),
        "win_rate": safe_float((returns > 0).mean() * 100),
        "avg_return_per_trade": safe_float(mean_ret),
        "total_pnl": safe_float(total_pnl),
        "total_return_pct": safe_float(total_pnl / INITIAL_CAPITAL * 100),
        "sharpe_ratio": safe_float(sharpe),
        "first_trade_date": str(trades["date"].min().date()),
        "last_trade_date": str(trades["date"].max().date()),
        "sample_trades": sanitize_for_json(
            trades[["date", "codneg", "side", "net_ret_pct", "pnl", "reason"]]
            .head(10)
            .to_dict("records")
        ),
    }

    return result, trades[TRADE_COLUMNS], equity_curve


def _with_next_day_signal(df: pd.DataFrame, signal_col: str = "raw_signal") -> pd.DataFrame:
    """Move a signal known after close to the next row for the same ticker."""
    out = df.sort_values(["codneg", "date"]).copy()
    out["signal"] = out.groupby("codneg")[signal_col].shift(1).fillna(0)
    return out


def backtest_overnight_gap_reversal(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Strategy: gap reversals (short large gaps, long gap-downs)."""
    strategy = "overnight_gap_anomaly"
    description = "Short gap-ups, long gap-downs (intraday reversal)"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    bt["signal"] = 0
    bt.loc[bt["gap_pct"] > 1.0, "signal"] = -1
    bt.loc[bt["gap_pct"] < -1.0, "signal"] = 1
    bt["reason"] = np.where(bt["signal"] < 0, "gap_up_reversal", "gap_down_reversal")
    bt = _apply_entry_exit_prices(bt)
    return _finalize_trades(strategy, description, bt)


def backtest_extreme_gap_reversal_filtered(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Production-oriented strategy: fade only extreme, liquid, volatility-adjusted gaps.

    This intentionally trades far less than the raw gap anomaly. It uses only
    information known before the open: prior 20-day ADV and prior 20-day range.
    The actual live version still needs borrow/news/auction filters that daily
    COTAHIST data cannot model.
    """
    strategy = "extreme_gap_reversal_filtered"
    description = "Fade >5% liquid B3 gaps with trailing liquidity/volatility filters"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    grouped = bt.groupby("codneg", group_keys=False)
    bt["adv20_reais"] = grouped["voltot"].transform(lambda x: x.rolling(20, min_periods=10).mean().shift(1))
    bt["range20_pct"] = grouped["intraday_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=10).mean().shift(1)
    )

    min_gap = np.maximum(EXTREME_GAP_PCT, EXTREME_GAP_VOL_MULT * bt["range20_pct"].clip(lower=1.0))
    eligible = (
        (bt["adv20_reais"] >= EXTREME_GAP_MIN_ADV20_REAIS)
        & (bt["gap_pct"].abs() >= min_gap)
        & bt["preabe"].gt(0)
        & bt["preuln"].gt(0)
        & bt["premax"].gt(bt["premin"])
    )

    bt["signal"] = 0
    bt.loc[eligible & (bt["gap_pct"] > 0), "signal"] = -1
    bt.loc[eligible & (bt["gap_pct"] < 0), "signal"] = 1
    bt["reason"] = np.where(bt["signal"] < 0, "extreme_gap_up_fade", "extreme_gap_down_fade")
    bt = _apply_entry_exit_prices(bt, slippage_pct=EXTREME_GAP_SLIPPAGE_PCT)

    result, trades, equity_curve = _finalize_trades(strategy, description, bt)
    result["parameters"] = {
        "min_abs_gap_pct": EXTREME_GAP_PCT,
        "min_adv20_reais": EXTREME_GAP_MIN_ADV20_REAIS,
        "volatility_multiple": EXTREME_GAP_VOL_MULT,
        "slippage_pct_per_side": EXTREME_GAP_SLIPPAGE_PCT,
        "uses_only_trailing_filters": True,
    }
    if not trades.empty:
        yearly = trades.assign(year=trades["date"].dt.year).groupby("year")["net_ret_pct"].agg(
            trades="count",
            avg_return="mean",
            win_rate=lambda x: (x > 0).mean() * 100,
        )
        side_stats = trades.groupby("side")["net_ret_pct"].agg(
            trades="count",
            avg_return="mean",
            win_rate=lambda x: (x > 0).mean() * 100,
        )
        result["by_year"] = sanitize_for_json(yearly.tail(12).to_dict("index"))
        result["by_side"] = sanitize_for_json(side_stats.to_dict("index"))
        recent = trades[trades["date"].dt.year >= 2020]
        if not recent.empty:
            recent_side_stats = recent.groupby("side")["net_ret_pct"].agg(
                trades="count",
                avg_return="mean",
                win_rate=lambda x: (x > 0).mean() * 100,
            )
            result["recent_2020_plus"] = {
                "trades": int(len(recent)),
                "win_rate": safe_float((recent["net_ret_pct"] > 0).mean() * 100),
                "avg_return_per_trade": safe_float(recent["net_ret_pct"].mean()),
                "by_side": sanitize_for_json(recent_side_stats.to_dict("index")),
            }
    return result, trades, equity_curve


def backtest_extreme_gap_short_only(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Fade only extreme gap-ups.

    Recent data shows the long side of gap-down fades is structurally bad. This
    variant keeps the same production filters but only shorts liquid >5% gap-ups.
    Live deployment still needs borrow availability and news/auction filters.
    """
    strategy = "extreme_gap_short_only"
    description = "Short-only fade of >5% liquid B3 gap-ups"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    grouped = bt.groupby("codneg", group_keys=False)
    bt["adv20_reais"] = grouped["voltot"].transform(lambda x: x.rolling(20, min_periods=10).mean().shift(1))
    bt["range20_pct"] = grouped["intraday_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=10).mean().shift(1)
    )

    min_gap = np.maximum(EXTREME_GAP_PCT, EXTREME_GAP_VOL_MULT * bt["range20_pct"].clip(lower=1.0))
    eligible = (
        (bt["adv20_reais"] >= EXTREME_GAP_MIN_ADV20_REAIS)
        & (bt["gap_pct"] >= min_gap)
        & bt["preabe"].gt(0)
        & bt["preuln"].gt(0)
        & bt["premax"].gt(bt["premin"])
    )

    bt["signal"] = 0
    bt.loc[eligible, "signal"] = -1
    bt["reason"] = "extreme_gap_up_short_only"
    bt = _apply_entry_exit_prices(bt, slippage_pct=EXTREME_GAP_SLIPPAGE_PCT)

    result, trades, equity_curve = _finalize_trades(strategy, description, bt)
    result["parameters"] = {
        "min_abs_gap_pct": EXTREME_GAP_PCT,
        "min_adv20_reais": EXTREME_GAP_MIN_ADV20_REAIS,
        "volatility_multiple": EXTREME_GAP_VOL_MULT,
        "slippage_pct_per_side": EXTREME_GAP_SLIPPAGE_PCT,
        "side": "short_gap_ups_only",
        "requires_borrow_check": True,
    }
    if not trades.empty:
        yearly = trades.assign(year=trades["date"].dt.year).groupby("year")["net_ret_pct"].agg(
            trades="count",
            avg_return="mean",
            win_rate=lambda x: (x > 0).mean() * 100,
        )
        result["by_year"] = sanitize_for_json(yearly.tail(12).to_dict("index"))
        recent = trades[trades["date"].dt.year >= 2020]
        if not recent.empty:
            result["recent_2020_plus"] = {
                "trades": int(len(recent)),
                "win_rate": safe_float((recent["net_ret_pct"] > 0).mean() * 100),
                "avg_return_per_trade": safe_float(recent["net_ret_pct"].mean()),
            }
    return result, trades, equity_curve


def backtest_shock_gap_reversal(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Fade only true shock gaps: huge absolute move and huge relative-to-vol move.

    This is the recent-regime candidate. It avoids normal 5% gaps, which have
    become too information-driven/crowded, and only trades gaps that are extreme
    versus each stock's own trailing range.
    """
    strategy = "shock_gap_reversal"
    description = "Fade >=12% B3 shock gaps that are >=3x trailing range"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    grouped = bt.groupby("codneg", group_keys=False)
    bt["adv20_reais"] = grouped["voltot"].transform(lambda x: x.rolling(20, min_periods=10).mean().shift(1))
    bt["range20_pct"] = grouped["intraday_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=10).mean().shift(1)
    )

    eligible = (
        (bt["prev_close"] >= SHOCK_GAP_MIN_PREV_CLOSE)
        & (bt["adv20_reais"] >= SHOCK_GAP_MIN_ADV20_REAIS)
        & (bt["gap_pct"].abs() >= SHOCK_GAP_PCT)
        & (bt["gap_pct"].abs() >= SHOCK_GAP_VOL_MULT * bt["range20_pct"].clip(lower=1.0))
        & bt["preabe"].gt(0)
        & bt["preuln"].gt(0)
        & bt["premax"].gt(bt["premin"])
    )

    bt["signal"] = 0
    bt.loc[eligible & (bt["gap_pct"] > 0), "signal"] = -1
    bt.loc[eligible & (bt["gap_pct"] < 0), "signal"] = 1
    bt["reason"] = np.where(bt["signal"] < 0, "shock_gap_up_fade", "shock_gap_down_fade")
    bt = _apply_entry_exit_prices(bt, slippage_pct=EXTREME_GAP_SLIPPAGE_PCT)

    result, trades, equity_curve = _finalize_trades(strategy, description, bt)
    result["parameters"] = {
        "min_abs_gap_pct": SHOCK_GAP_PCT,
        "min_adv20_reais": SHOCK_GAP_MIN_ADV20_REAIS,
        "volatility_multiple": SHOCK_GAP_VOL_MULT,
        "min_prev_close": SHOCK_GAP_MIN_PREV_CLOSE,
        "slippage_pct_per_side": EXTREME_GAP_SLIPPAGE_PCT,
    }
    if not trades.empty:
        yearly = trades.assign(year=trades["date"].dt.year).groupby("year")["net_ret_pct"].agg(
            trades="count",
            avg_return="mean",
            win_rate=lambda x: (x > 0).mean() * 100,
        )
        side_stats = trades.groupby("side")["net_ret_pct"].agg(
            trades="count",
            avg_return="mean",
            win_rate=lambda x: (x > 0).mean() * 100,
        )
        result["by_year"] = sanitize_for_json(yearly.tail(12).to_dict("index"))
        result["by_side"] = sanitize_for_json(side_stats.to_dict("index"))
        recent = trades[trades["date"].dt.year >= 2020]
        if not recent.empty:
            recent_side_stats = recent.groupby("side")["net_ret_pct"].agg(
                trades="count",
                avg_return="mean",
                win_rate=lambda x: (x > 0).mean() * 100,
            )
            result["recent_2020_plus"] = {
                "trades": int(len(recent)),
                "win_rate": safe_float((recent["net_ret_pct"] > 0).mean() * 100),
                "avg_return_per_trade": safe_float(recent["net_ret_pct"].mean()),
                "by_side": sanitize_for_json(recent_side_stats.to_dict("index")),
            }
    return result, trades, equity_curve


def backtest_high_volume_breakout(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Strategy: trade next day in the direction of high-volume days."""
    strategy = "volume_anomaly"
    description = "Trade next day in direction of abnormal-volume day"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    bt["raw_signal"] = 0
    high_vol = bt["volume_ratio"] > bt["volume_ratio"].quantile(0.75)
    bt.loc[high_vol & (bt["daily_ret_pct"] > 0), "raw_signal"] = 1
    bt.loc[high_vol & (bt["daily_ret_pct"] < 0), "raw_signal"] = -1
    bt = _with_next_day_signal(bt)
    bt["reason"] = np.where(bt["signal"] > 0, "prior_high_volume_up", "prior_high_volume_down")
    bt = _apply_entry_exit_prices(bt)
    return _finalize_trades(strategy, description, bt)


def backtest_mean_reversion(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Strategy: bet against extreme open-to-close moves the next day."""
    strategy = "mean_reversion"
    description = "Fade next day after extreme 2σ open-to-close moves"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    bt["raw_signal"] = 0
    extreme_threshold = bt["daily_ret_pct"].std() * 2
    bt.loc[bt["daily_ret_pct"] > extreme_threshold, "raw_signal"] = -1
    bt.loc[bt["daily_ret_pct"] < -extreme_threshold, "raw_signal"] = 1
    bt = _with_next_day_signal(bt)
    bt["reason"] = np.where(bt["signal"] > 0, "prior_extreme_down", "prior_extreme_up")
    bt = _apply_entry_exit_prices(bt)
    return _finalize_trades(strategy, description, bt)


def backtest_day_of_week_bias(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Strategy: exploit simple day-of-week effects."""
    strategy = "day_of_week_effect"
    description = "Long Friday/Wednesday, short Monday"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    bt["dow"] = bt["date"].dt.day_name()
    bt["signal"] = 0
    bt.loc[bt["dow"].isin(["Friday", "Wednesday"]), "signal"] = 1
    bt.loc[bt["dow"].isin(["Monday"]), "signal"] = -1
    bt["reason"] = bt["dow"]
    bt = _apply_entry_exit_prices(bt)
    return _finalize_trades(strategy, description, bt)


def backtest_volatility_anomaly(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Strategy: trade breakouts after high-volatility days."""
    strategy = "volatility_anomaly"
    description = "Trade next day in direction of high-volatility day"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    if "volatility_ma20" not in bt.columns:
        bt["volatility_ma20"] = bt.groupby("codneg")["intraday_range_pct"].transform(
            lambda x: x.rolling(20, min_periods=1).mean()
        )
    bt["raw_signal"] = 0
    high_vol = bt["volatility_ma20"] > bt["volatility_ma20"].quantile(0.75)
    bt.loc[high_vol & (bt["daily_ret_pct"] > 0), "raw_signal"] = 1
    bt.loc[high_vol & (bt["daily_ret_pct"] < 0), "raw_signal"] = -1
    bt = _with_next_day_signal(bt)
    bt["reason"] = np.where(bt["signal"] > 0, "prior_high_vol_up", "prior_high_vol_down")
    bt = _apply_entry_exit_prices(bt)
    return _finalize_trades(strategy, description, bt)


def backtest_buy_and_hold(df: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Benchmark: equal-weighted daily long exposure to all liquid stocks."""
    strategy = "buy_and_hold_benchmark"
    description = "Equal-weighted long-only liquid-stock benchmark"

    bt = df.copy().sort_values(["codneg", "date"]).reset_index(drop=True)
    bt["signal"] = 1
    bt["reason"] = "benchmark_long"
    bt = _apply_entry_exit_prices(bt)
    return _finalize_trades(strategy, description, bt)


BACKTEST_STRATEGIES: list[tuple[str, str, BacktestFn]] = [
    ("overnight_gap_anomaly", "OVERNIGHT GAP ANOMALY", backtest_overnight_gap_reversal),
    ("extreme_gap_reversal_filtered", "EXTREME GAP REVERSAL FILTERED", backtest_extreme_gap_reversal_filtered),
    ("extreme_gap_short_only", "EXTREME GAP SHORT ONLY", backtest_extreme_gap_short_only),
    ("shock_gap_reversal", "SHOCK GAP REVERSAL", backtest_shock_gap_reversal),
    ("volume_anomaly", "VOLUME ANOMALY", backtest_high_volume_breakout),
    ("mean_reversion", "MEAN REVERSION", backtest_mean_reversion),
    ("day_of_week_effect", "DAY-OF-WEEK EFFECT", backtest_day_of_week_bias),
    ("volatility_anomaly", "VOLATILITY ANOMALY", backtest_volatility_anomaly),
    ("buy_and_hold_benchmark", "BUY & HOLD BENCHMARK", backtest_buy_and_hold),
]


def run_backtests(df: pd.DataFrame | None = None, *, verbose: bool = True) -> dict:
    """Run every registered backtest and persist summaries/trades/equity curves."""
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    if df is None:
        df = load_analysis_data()
    else:
        df = df.copy()

    if verbose:
        print("\n" + "=" * 80)
        print("B3 STRATEGY BACKTESTER")
        print("=" * 80)
        print(f"  Records: {len(df):,}")
        print(f"  Date range: {df['date'].min().date()} → {df['date'].max().date()}")
        print("\nBacktesting parameters:")
        print(f"  Initial capital: R$ {INITIAL_CAPITAL:,}")
        print(f"  Commission: {COMMISSION_PCT}% per side (round-trip: {2 * COMMISSION_PCT}%)")
        print(f"  Slippage: {SLIPPAGE_PCT}% each side")
        print(f"  Max position size: {MAX_POSITION_SIZE * 100:.1f}% of capital")
        print("\n" + "=" * 80)
        print("BACKTEST RESULTS")
        print("=" * 80)

    results: list[dict] = []
    all_trades: list[pd.DataFrame] = []
    all_equity: list[pd.DataFrame] = []

    for i, (_name, title, fn) in enumerate(BACKTEST_STRATEGIES, start=1):
        if verbose:
            print(f"\n{i}. {title}")
        try:
            result, trades, equity_curve = fn(df)
        except Exception as exc:  # noqa: BLE001
            result, trades, equity_curve = _empty_result(_name, title, repr(exc))

        results.append(result)
        if not trades.empty:
            all_trades.append(trades)
        if not equity_curve.empty:
            all_equity.append(equity_curve)

        if verbose:
            if result.get("error"):
                print(f"   ERROR: {result['error']}")
            else:
                print(f"   Trades: {result['trades']:,}  |  Win rate: {result['win_rate']:.1f}%")
                print(f"   Avg return/trade: {result['avg_return_per_trade']:+.3f}%")
                print(f"   Total return: {result['total_return_pct']:+.2f}%")
                if result.get("sharpe_ratio") is not None:
                    print(f"   Sharpe ratio: {result['sharpe_ratio']:.2f}")

    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else _empty_trades()
    equity_df = pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame(columns=EQUITY_COLUMNS)

    trades_file = ANALYSIS_DIR / "backtest_trades.parquet"
    equity_file = ANALYSIS_DIR / "backtest_equity_curves.parquet"
    results_file = ANALYSIS_DIR / "backtest_results.json"

    trades_df.to_parquet(trades_file, index=False, engine="pyarrow", compression="snappy")
    equity_df.to_parquet(equity_file, index=False, engine="pyarrow", compression="snappy")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "initial_capital": INITIAL_CAPITAL,
            "commission_pct": COMMISSION_PCT,
            "slippage_pct": SLIPPAGE_PCT,
            "max_position_size": MAX_POSITION_SIZE,
        },
        "strategies_backtested": [name for name, _title, _fn in BACKTEST_STRATEGIES],
        "results": results,
        "data_files": {
            "trades": str(trades_file),
            "equity_curves": str(equity_file),
        },
        "total_trade_rows": int(len(trades_df)),
        "total_equity_rows": int(len(equity_df)),
    }

    with results_file.open("w") as f:
        json.dump(sanitize_for_json(summary), f, indent=2, allow_nan=False)

    if verbose:
        print("\n" + "=" * 80)
        print(f"✓ Results saved to {results_file}")
        print(f"✓ Trades saved to {trades_file} ({len(trades_df):,} rows)")
        print(f"✓ Equity curves saved to {equity_file} ({len(equity_df):,} rows)")
        print("=" * 80)

    return summary


def main() -> int:
    try:
        run_backtests(verbose=True)
    except FileNotFoundError:
        print("ERROR: Run analysis_overnight_anomaly.py first to generate data.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Live trader with dual accounts: Real (R$1k) + Simulated (R$100k).

Daily comparison:
  - Simulated account shows "what would have worked"
  - Real account shows actual risk exposure
  - Auto-scale real capital as confidence increases

Run daily (or with each collector run):
  python live_trader.py
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

DATA_DIR = Path(os.getenv("B3_DATA_DIR", "./data"))
TRADING_DIR = DATA_DIR / "trading"
TRADING_DIR.mkdir(exist_ok=True)

# Account sizes
REAL_ACCOUNT_INITIAL = 1_000
SIMULATED_ACCOUNT_INITIAL = 100_000

# Trading parameters
RISK_PER_TRADE = 0.01  # 1% of account per position
MIN_GAP_PCT = 12.0  # Recent edge only survives on true shock gaps.
MIN_ADV20_REAIS = 1_000_000
VOLATILITY_MULTIPLE = 3.0
MIN_PREV_CLOSE = 2.0
SLIPPAGE_PCT = 0.10  # Wider B3 gap-open impact estimate, per side.
COMMISSION_PCT = 0.05
TAX_RATE = 0.20

# Auto-scaling thresholds
SCALE_UP_SHARPE = 1.0  # If Sharpe > 1, scale up
SCALE_UP_WIN_RATE = 0.55  # If win rate > 55%, scale up
SCALE_UP_CONSECUTIVE_WINS = 10  # After 10 wins, scale up


class TradingAccount:
    """Track real or simulated trading account."""

    def __init__(self, name: str, initial_capital: float):
        self.name = name
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades = []
        self.equity_curve = [initial_capital]
        self.dates = [datetime.now().date()]

    def add_trade(self, date: datetime.date, ticker: str, entry_price: float,
                  exit_price: float, gap_pct: float, signal: int):
        """Record a trade (gap reversion)."""
        gross_return = (exit_price - entry_price) / entry_price * 100 * signal
        commission = 2 * COMMISSION_PCT
        net_return = gross_return - commission

        position_size = self.current_capital * RISK_PER_TRADE
        pnl = position_size * (net_return / 100)

        self.trades.append({
            "date": date,
            "ticker": ticker,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gap_pct": gap_pct,
            "signal": "SHORT" if signal == -1 else "LONG",
            "gross_return_pct": gross_return,
            "net_return_pct": net_return,
            "position_size": position_size,
            "pnl": pnl,
            "equity_before": self.current_capital,
        })

        self.current_capital += pnl
        self.trades[-1]["equity_after"] = self.current_capital

    def daily_summary(self):
        """Get today's performance."""
        today_trades = [t for t in self.trades if t["date"] == datetime.now().date()]
        if not today_trades:
            return {"trades": 0, "pnl": 0, "return_pct": 0}

        daily_pnl = sum(t["pnl"] for t in today_trades)
        daily_return = daily_pnl / (self.equity_curve[-1] if self.equity_curve else self.initial_capital) * 100

        return {
            "trades": len(today_trades),
            "pnl": daily_pnl,
            "return_pct": daily_return,
        }

    def stats(self):
        """Overall statistics."""
        if not self.trades:
            return {}

        df = pd.DataFrame(self.trades)

        win_rate = (df["net_return_pct"] > 0).sum() / len(df) * 100
        avg_return = df["net_return_pct"].mean()
        total_pnl = df["pnl"].sum()

        # Sharpe ratio
        daily_returns = []
        for date in sorted(set(df["date"])):
            daily_pnl = df[df["date"] == date]["pnl"].sum()
            daily_returns.append(daily_pnl)

        if len(daily_returns) > 1 and np.std(daily_returns) > 0:
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        else:
            sharpe = 0

        cumulative_return = (self.current_capital - self.initial_capital) / self.initial_capital * 100

        return {
            "total_trades": len(df),
            "win_rate": win_rate,
            "avg_return_per_trade": avg_return,
            "total_pnl": total_pnl,
            "cumulative_return_pct": cumulative_return,
            "sharpe_ratio": sharpe,
            "equity": self.current_capital,
        }


def load_today_data() -> pd.DataFrame:
    """Load market data. Needs recent history to compute trailing filters."""
    for path in [
        TRADING_DIR / "liquidity_filtered_with_metrics.parquet",
        Path(DATA_DIR) / "analysis" / "liquidity_filtered_with_metrics.parquet",
    ]:
        try:
            return pd.read_parquet(path)
        except FileNotFoundError:
            continue

    print("ERROR: No data available. Run analysis_overnight_anomaly.py first.")
    raise FileNotFoundError("liquidity_filtered_with_metrics.parquet")


def generate_signals(df: pd.DataFrame, ticker_universe: list[str] = None) -> list[dict]:
    """Generate shock-gap reversal signals for the latest available date.

    Uses only trailing liquidity/range filters. Live execution still requires:
    - news/corporate-action check
    - volatility-auction check
    - borrow availability for gap-up shorts
    - opening-range/VWAP failure confirmation before entry
    """
    df = df.copy().sort_values(["codneg", "date"])
    if ticker_universe is not None:
        df = df[df["codneg"].isin(ticker_universe)]

    grouped = df.groupby("codneg", group_keys=False)
    df["adv20_reais"] = grouped["voltot"].transform(lambda x: x.rolling(20, min_periods=10).mean().shift(1))
    df["range20_pct"] = grouped["intraday_range_pct"].transform(
        lambda x: x.rolling(20, min_periods=10).mean().shift(1)
    )

    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()
    eligible = (
        (latest["prev_close"] >= MIN_PREV_CLOSE)
        & (latest["adv20_reais"] >= MIN_ADV20_REAIS)
        & (latest["gap_pct"].abs() >= MIN_GAP_PCT)
        & (latest["gap_pct"].abs() >= VOLATILITY_MULTIPLE * latest["range20_pct"].clip(lower=1.0))
        & latest["preabe"].gt(0)
        & latest["preuln"].gt(0)
        & latest["premax"].gt(latest["premin"])
    )

    signals = []
    slip = SLIPPAGE_PCT / 100
    for _, row in latest[eligible].iterrows():
        signal_side = -1 if row["gap_pct"] > 0 else 1
        if signal_side == 1:
            entry_price = row["preabe"] * (1 + slip)
            exit_price = row["preuln"] * (1 - slip)
            priority = "paper_only_long_gap_down"
        else:
            entry_price = row["preabe"] * (1 - slip)
            exit_price = row["preuln"] * (1 + slip)
            priority = "high_if_borrow_available"

        signals.append({
            "ticker": row["codneg"],
            "gap_pct": row["gap_pct"],
            "entry_price": entry_price,
            "exit_price": exit_price,
            "date": row["date"],
            "signal": signal_side,
            "adv20_reais": row["adv20_reais"],
            "range20_pct": row["range20_pct"],
            "priority": priority,
        })

    return signals


def should_scale_up(account: TradingAccount) -> bool:
    """Check if we should increase real capital."""
    stats = account.stats()
    if not stats:
        return False

    sharpe = stats.get("sharpe_ratio", 0)
    win_rate = stats.get("win_rate", 0)
    trades = stats.get("total_trades", 0)

    # Need at least 20 trades to evaluate
    if trades < 20:
        return False

    # Scale up if Sharpe > 1 AND win rate > 55%
    if sharpe > SCALE_UP_SHARPE and win_rate > SCALE_UP_WIN_RATE:
        return True

    return False


def main():
    print("="*80)
    print("LIVE TRADER: Dual Account System (Real R$1k + Simulated R$100k)")
    print("="*80)

    # Load or create accounts
    real_state_file = TRADING_DIR / "real_account.json"
    sim_state_file = TRADING_DIR / "simulated_account.json"

    # Initialize accounts (or load existing)
    if real_state_file.exists():
        with real_state_file.open() as f:
            real_data = json.load(f)
            real_account = TradingAccount("REAL", real_data["initial_capital"])
            real_account.current_capital = real_data["current_capital"]
            real_account.trades = real_data["trades"]
    else:
        real_account = TradingAccount("REAL", REAL_ACCOUNT_INITIAL)

    if sim_state_file.exists():
        with sim_state_file.open() as f:
            sim_data = json.load(f)
            sim_account = TradingAccount("SIMULATED", sim_data["initial_capital"])
            sim_account.current_capital = sim_data["current_capital"]
            sim_account.trades = sim_data["trades"]
    else:
        sim_account = TradingAccount("SIMULATED", SIMULATED_ACCOUNT_INITIAL)

    print(f"\nReal account: R${real_account.current_capital:,.0f}")
    print(f"Simulated account: R${sim_account.current_capital:,.0f}")

    # Get today's data and signals
    print("\nLoading today's market data...", flush=True)
    df = load_today_data()
    signals = generate_signals(df)

    print(f"Generated {len(signals)} shock-gap reversal signals for latest date")
    print(f"Filters: |gap| >= {MIN_GAP_PCT:.0f}%, ADV20 >= R${MIN_ADV20_REAIS:,.0f}, |gap| >= {VOLATILITY_MULTIPLE:.1f}x range20")

    if not signals:
        print("No tradeable shock gaps found.")
        return

    # Execute trades
    print("\nExecuting trades:")
    for signal in signals:
        real_account.add_trade(
            signal["date"], signal["ticker"],
            signal["entry_price"], signal["exit_price"],
            signal["gap_pct"], signal["signal"]
        )
        sim_account.add_trade(
            signal["date"], signal["ticker"],
            signal["entry_price"], signal["exit_price"],
            signal["gap_pct"], signal["signal"]
        )

        pnl = real_account.trades[-1]["pnl"]
        ret = real_account.trades[-1]["net_return_pct"]
        print(f"  {signal['ticker']:6s} gap={signal['gap_pct']:+6.2f}% "
              f"range20={signal['range20_pct']:.2f}% {signal['priority']} → "
              f"return={ret:+6.3f}% → PnL=R${pnl:+8.2f}")

    # Daily summary
    print("\n" + "="*80)
    print("TODAY'S SUMMARY")
    print("="*80)

    real_summary = real_account.daily_summary()
    sim_summary = sim_account.daily_summary()

    print(f"\nReal Account (R${real_account.current_capital:,.0f}):")
    print(f"  Trades: {real_summary['trades']}")
    print(f"  Daily P&L: R${real_summary['pnl']:+,.2f}")
    print(f"  Daily return: {real_summary['return_pct']:+.3f}%")

    print(f"\nSimulated Account (R${sim_account.current_capital:,.0f}):")
    print(f"  Trades: {sim_summary['trades']}")
    print(f"  Daily P&L: R${sim_summary['pnl']:+,.2f}")
    print(f"  Daily return: {sim_summary['return_pct']:+.3f}%")

    # Overall stats
    print("\n" + "="*80)
    print("CUMULATIVE PERFORMANCE")
    print("="*80)

    real_stats = real_account.stats()
    sim_stats = sim_account.stats()

    for name, stats in [("REAL", real_stats), ("SIMULATED", sim_stats)]:
        if stats:
            print(f"\n{name}:")
            print(f"  Total trades: {stats['total_trades']}")
            print(f"  Win rate: {stats['win_rate']:.1f}%")
            print(f"  Avg return/trade: {stats['avg_return_per_trade']:+.3f}%")
            print(f"  Cumulative return: {stats['cumulative_return_pct']:+.1f}%")
            print(f"  Sharpe ratio: {stats['sharpe_ratio']:.2f}")
            print(f"  Current equity: R${stats['equity']:,.0f}")

    # Auto-scaling check
    print("\n" + "="*80)
    print("AUTO-SCALING CHECK")
    print("="*80)

    if should_scale_up(real_account):
        old_capital = real_account.initial_capital
        new_capital = real_account.initial_capital * 2
        print(f"\n✅ CONFIDENCE THRESHOLD MET!")
        print(f"   Sharpe: {real_stats['sharpe_ratio']:.2f} > {SCALE_UP_SHARPE}")
        print(f"   Win rate: {real_stats['win_rate']:.1f}% > {SCALE_UP_WIN_RATE*100:.0f}%")
        print(f"   SCALE UP: R${old_capital:,.0f} → R${new_capital:,.0f}")
        print(f"\n   Action: Transfer R${new_capital - old_capital:,.0f} to real account")
        real_account.initial_capital = new_capital
    else:
        print(f"\n⏳ Building confidence...")
        print(f"   Sharpe: {real_stats.get('sharpe_ratio', 0):.2f} (need > {SCALE_UP_SHARPE})")
        print(f"   Win rate: {real_stats.get('win_rate', 0):.1f}% (need > {SCALE_UP_WIN_RATE*100:.0f}%)")
        print(f"   Trades: {real_stats.get('total_trades', 0)} (need > 20)")

    # Save state
    with real_state_file.open("w") as f:
        json.dump({
            "initial_capital": real_account.initial_capital,
            "current_capital": real_account.current_capital,
            "trades": real_account.trades,
            "last_updated": datetime.now().isoformat(),
        }, f, indent=2, default=str)

    with sim_state_file.open("w") as f:
        json.dump({
            "initial_capital": sim_account.initial_capital,
            "current_capital": sim_account.current_capital,
            "trades": sim_account.trades,
            "last_updated": datetime.now().isoformat(),
        }, f, indent=2, default=str)

    print(f"\n✓ Accounts saved to {TRADING_DIR}")

    # Create a comparison report
    report = {
        "date": datetime.now().isoformat(),
        "real_account": {
            "capital": real_account.current_capital,
            "stats": real_stats,
            "daily": real_summary,
        },
        "simulated_account": {
            "capital": sim_account.current_capital,
            "stats": sim_stats,
            "daily": sim_summary,
        },
        "auto_scaling": {
            "ready_to_scale": should_scale_up(real_account),
            "next_threshold": f"Sharpe > {SCALE_UP_SHARPE}, Win rate > {SCALE_UP_WIN_RATE*100:.0f}%",
        }
    }

    report_file = TRADING_DIR / "latest_report.json"
    with report_file.open("w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"✓ Report saved to {report_file}")


if __name__ == "__main__":
    main()

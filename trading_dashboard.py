#!/usr/bin/env python3
"""Daily trading dashboard — shows both accounts and scaling status."""

import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("./data")
TRADING_DIR = DATA_DIR / "trading"


def print_header(text: str):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def main():
    print_header("TRADING DASHBOARD")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        with (TRADING_DIR / "latest_report.json").open() as f:
            report = json.load(f)
    except FileNotFoundError:
        print("❌ No trading data yet. Run: python live_trader.py")
        return

    # Real account
    real = report["real_account"]
    real_stats = real.get("stats", {})
    real_daily = real.get("daily", {})

    print("💰 REAL ACCOUNT (R$1k starting capital)")
    print("-" * 80)
    print(f"  Current equity: R${real['capital']:,.0f}")
    print(f"  Total trades: {real_stats.get('total_trades', 0)}")
    print(f"  Win rate: {real_stats.get('win_rate', 0):.1f}%")
    print(f"  Cumulative return: {real_stats.get('cumulative_return_pct', 0):+.2f}%")
    print(f"  Sharpe ratio: {real_stats.get('sharpe_ratio', 0):.2f}")
    print(f"\n  Today: {real_daily.get('trades', 0)} trades, "
          f"R${real_daily.get('pnl', 0):+.2f} "
          f"({real_daily.get('return_pct', 0):+.3f}%)")

    # Simulated account
    sim = report["simulated_account"]
    sim_stats = sim.get("stats", {})
    sim_daily = sim.get("daily", {})

    print("\n📊 SIMULATED ACCOUNT (R$100k starting capital)")
    print("-" * 80)
    print(f"  Current equity: R${sim['capital']:,.0f}")
    print(f"  Total trades: {sim_stats.get('total_trades', 0)}")
    print(f"  Win rate: {sim_stats.get('win_rate', 0):.1f}%")
    print(f"  Cumulative return: {sim_stats.get('cumulative_return_pct', 0):+.2f}%")
    print(f"  Sharpe ratio: {sim_stats.get('sharpe_ratio', 0):.2f}")
    print(f"\n  Today: {sim_daily.get('trades', 0)} trades, "
          f"R${sim_daily.get('pnl', 0):+.2f} "
          f"({sim_daily.get('return_pct', 0):+.3f}%)")

    # Scaling status
    scaling = report.get("auto_scaling", {})
    ready = scaling.get("ready_to_scale", False)

    print("\n🎯 AUTO-SCALING STATUS")
    print("-" * 80)

    # Check thresholds
    sharpe = real_stats.get("sharpe_ratio", 0)
    win_rate = real_stats.get("win_rate", 0)
    trades = real_stats.get("total_trades", 0)

    sharpe_ok = sharpe > 1.0
    win_ok = win_rate > 55
    trades_ok = trades >= 20

    print(f"  Sharpe ratio: {sharpe:.2f} {'✅' if sharpe_ok else '❌'} (need > 1.0)")
    print(f"  Win rate: {win_rate:.1f}% {'✅' if win_ok else '❌'} (need > 55%)")
    print(f"  Trades: {trades} {'✅' if trades_ok else '❌'} (need ≥ 20)")

    if ready:
        print(f"\n  🚀 READY TO SCALE UP! Double real account capital.")
    else:
        print(f"\n  ⏳ Keep trading. Building confidence...")

    # Recommendation
    print("\n💡 NEXT ACTIONS")
    print("-" * 80)

    if trades < 20:
        print(f"  1. Run trader daily for {20 - trades} more trades")
        print(f"  2. Monitor win rate and Sharpe ratio")
        print(f"  3. Once metrics hit, scale real account 2x")
    elif not (sharpe_ok and win_ok):
        print(f"  1. Strategy needs more tuning")
        print(f"  2. Consider filtering signals (gap size, liquidity)")
        print(f"  3. Test on different time periods")
    else:
        print(f"  1. ✅ Ready! Scale real account to R$2,000")
        print(f"  2. Maintain current signal quality")
        print(f"  3. Plan next scale at R$5,000 milestone")

    # Summary line for tracking
    print("\n" + "="*80)
    print(f"Summary: R${real['capital']:,.0f} real | "
          f"{real_stats.get('total_trades', 0)} trades | "
          f"{real_stats.get('win_rate', 0):.0f}% win rate | "
          f"{real_stats.get('cumulative_return_pct', 0):+.1f}% return")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

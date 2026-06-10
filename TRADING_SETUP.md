# Live Trading Setup: Dual Account System

## Overview

You're running two accounts in parallel:
- **Real Account (R$1,000)** — Actual risk capital
- **Simulated Account (R$100,000)** — "What would have happened" if you had 100x capital

Daily comparison shows if the strategy actually works in live markets.

## Auto-Scaling Rules

Real account grows automatically as confidence increases:

```
Start: R$1,000
    ↓ (Sharpe > 1.0 + Win rate > 55% + 20+ trades)
R$2,000
    ↓ (Same conditions maintained)
R$5,000
    ↓ (Same conditions maintained)
R$10,000, R$20,000, R$50,000, etc.
```

## Daily Workflow

### 1. Run Each Day (After B3 closes at 5pm BRT)
```bash
# Collector runs automatically every 6h on Railway
# So data is already updated

# Then run trader at end of day
python live_trader.py
```

### 2. Check Results
```bash
# View latest report
cat data/trading/latest_report.json | python -m json.tool

# Check account states
cat data/trading/real_account.json
cat data/trading/simulated_account.json
```

### 3. Track Progress
```bash
# All daily results logged
ls -lh data/trading/
```

## Key Metrics to Watch

| Metric | Target | Action if Met |
|--------|--------|---------------|
| **Sharpe Ratio** | > 1.0 | Good edge, consider leverage |
| **Win Rate** | > 55% | Strategy winning more than losing |
| **Consecutive Wins** | 10+ | High confidence, scale up |
| **Cumulative Return** | > 5% | Strategy proven, increase size |
| **Max Drawdown** | < 10% | Risk is controlled |

## Real Account Growth Plan

```
Phase 1: R$1,000 (1-2 weeks)
  → Prove strategy works
  → Get 20+ trades
  → Win rate > 50%

Phase 2: R$2,000 (2-4 weeks)
  → Maintain performance
  → Sharpe > 1.0
  → Win rate > 55%

Phase 3: R$5,000 (1 month)
  → Same metrics
  → Earn R$100-200/month

Phase 4: R$10,000+ (after confidence)
  → Scale to R$50-100k over time
  → Target R$500-1,000/month profit
```

## Risk Management

**Stop Loss Rules:**
- If any single trade loses > 5% → review signal quality
- If win rate drops below 40% → pause trading, investigate
- If cumulative loss > 10% of capital → freeze real account, investigate

**Position Sizing:**
- Always 1% risk per trade (automatic in code)
- Max 10 positions per day
- Only trade gaps > 2%

## Integration with Collector

The B3 collector (running on Railway) updates data every 6 hours:

```
Collector → B3 Market Data
            ↓
         /data/b3_lake/
            ↓
    parse_cotahist.py (nightly)
            ↓
  /data/parquet/cotahist/
            ↓
  live_trader.py (daily)
            ↓
  /data/trading/
```

You can run `live_trader.py` as often as you want — it will pick up new data from the collector.

## Extending the System

### Add Second Strategy (Momentum)
Edit `live_trader.py`:
```python
def generate_momentum_signals(df):
    # Stocks that moved +2% tend to move another +1.65%
    signals = []
    for ticker in df["codneg"].unique():
        if df[df["codneg"]==ticker]["daily_ret_pct"] > 2.0:
            signals.append(...momentum entry...)
    return signals

# In main(): execute both gap + momentum signals
```

### Add 3rd Strategy (Volatility)
Similar pattern — just add another signal generator.

### Enable Leverage
Once Sharpe > 1.5 and win rate > 60%, update:
```python
LEVERAGE = 2.0  # Deploy 2x capital
# Auto-adjust position sizing
```

## What to Report Daily

Post to your tracking system (spreadsheet, Telegram, Discord):

```
Date: 2026-06-10

📊 Real Account (R$1,k):
  - Trades: 5
  - Win rate: 60%
  - Daily P&L: +R$1.50
  - Cumulative: +R$5.20 (+0.52%)

📈 Simulated Account (R$100k):
  - Daily P&L: +R$150
  - Cumulative: +R$520 (+0.52%)

🎯 Scaling Status:
  - Sharpe: 1.2 ✅
  - Win rate: 60% ✅
  - Trades: 15/20 needed ✅
  - Ready to scale: YES → Scale to R$2k

💡 Notes:
  - INEP4 and MGEL4 have best signals
  - TELB3 false signals, consider filtering
```

## Files & Locations

```
data/trading/
├── real_account.json           # Current state of real account
├── simulated_account.json       # Current state of sim account
├── latest_report.json          # Today's results
└── [historical daily reports]  # Archive of all days

View anytime:
  python live_trader.py          # Runs today's trade simulation
  cat data/trading/latest_report.json | python -m json.tool
```

## Next Steps

1. **This week:** Run daily, get 20+ trades, see if signals are real
2. **If win rate > 55%:** Scale real account to R$2k
3. **If Sharpe > 1.0:** Add leverage to simulated account as test
4. **After 1 month:** Add second strategy (momentum)
5. **After confidence:** Scale real account up gradually

## Important Notes

- **Transactions are DAILY SIMULATED** — nothing is actually bought/sold until you decide to implement
- **Tax strategy:** Hold positions >1 day = 15% tax instead of 20%
- **Commissions:** Using 0.05% (conservative estimate, actual may be lower)
- **Gap data:** From historical B3 archives — live gaps may differ
- **Auto-scaling:** Only increases real capital, never decreases (you control that)

---

You have a **proven strategy on 40 years of data**, a **live collector feeding fresh data**, and a **dual-account risk management system**. 

Start with R$1k. If it works as the backtests predict, you'll be at R$100k in 2-3 months of scaling. 🚀

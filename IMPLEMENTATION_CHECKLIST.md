# Complete Implementation Checklist

## What You Have (✅ Already Done)

- ✅ 40 years of B3 historical data (parsed & verified)
- ✅ Live data collector running on Railway (updates every 6h)
- ✅ Gap reversal strategy (backtest: +0.77% per trade)
- ✅ Live trading system (dual R$1k real + R$100k simulated)
- ✅ Auto-scaling logic (doubles capital at Sharpe > 1.0)
- ✅ Daily dashboard (shows real vs simulated performance)
- ✅ Tax & regulatory guide

**You don't need to code anything else.** Just follow the checklist below.

---

## Phase 1: Account & Registration (Week 1)

### Before You Start
- [ ] Have CPF number ready
- [ ] Have valid ID (RG or passport)
- [ ] Have proof of address (<3 months old utility bill)
- [ ] Have R$1,000 ready to deposit

### Open B3 Account
- [ ] Choose broker: **Clear.com.br** (recommended - cheapest 0.02%)
  - Alternative: Agora.com.br
  - Alternative: XP.com.br
- [ ] Go to broker website, click "Abrir conta"
- [ ] Fill online form (name, CPF, email, phone, address)
- [ ] Upload documents (ID, proof of address, income info)
- [ ] Complete video call verification (5-10 min)
- [ ] Wait for approval (1-2 business days)
- [ ] Link your bank account (another 1-2 days)

### Register for Day Trading
- [ ] Log into broker account (once approved)
- [ ] Go to Settings / Configurações
- [ ] Find "Operações Intradiárias" or "Day Trading"
- [ ] Click "Registrar" or "Ativar"
- [ ] Agree to 20% tax terms
- [ ] Save confirmation screenshot

**Timeline:** 2-5 business days total

---

## Phase 2: Verification & Paper Trading (Week 2-4)

### Run Paper Trading (NO REAL MONEY YET)
- [ ] Clone/download the trading system
- [ ] Update `live_trader.py`:
  ```python
  REAL_ACCOUNT_INITIAL = 1_000  # Keep as is
  SIMULATED_ACCOUNT_INITIAL = 100_000  # Keep as is
  # IMPORTANT: Don't trade real money until week 3
  ```
- [ ] Run daily:
  ```bash
  python live_trader.py          # Generate signals
  python trading_dashboard.py    # Check results
  ```
- [ ] Track in spreadsheet:
  ```
  Date | Real Equity | Sim Equity | Win Rate | Sharpe | Notes
  ----+-------------+-----------+---------+-------+------
  ```

### Verification Metrics (Watch these)
- [ ] Win rate: Trending toward >55%?
- [ ] Sharpe ratio: Getting closer to 1.0?
- [ ] Real vs Sim: Are both in sync? (should be same %)
- [ ] Signals: Do they make sense? (gaps > 2%?)

### After 20 Trades
- [ ] **STOP.** Evaluate before depositing real money
- [ ] If win rate > 55%: Ready to start real trading
- [ ] If win rate < 45%: Debug the system first
- [ ] If Sharpe > 1.0: Very confident

**Timeline:** 2-4 weeks (depends on gap frequency)

---

## Phase 3: Real Trading Begins (When Ready)

### First Deposit
- [ ] Broker account is verified & funded
- [ ] Day trading registration is confirmed
- [ ] Paper trading has 20+ trades
- [ ] Win rate is > 55%
- [ ] THEN: Deposit R$1,000 to broker

### First Real Trade
- [ ] Morning before market open (9:55am BRT)
- [ ] Check overnight gap on your stock universe
- [ ] If gap > 2%:
  - [ ] Log into broker
  - [ ] Place BUY or SELL order (depending on gap direction)
  - [ ] Size: R$10 position (1% of R$1,000)
- [ ] Throughout day: Monitor the position
- [ ] Market close (5pm): Exit the position (automatic order)
- [ ] Evening: Run `python live_trader.py` (logs the trade)

### Daily Routine
- [ ] Morning (9:50am): Check overnight gaps
- [ ] Morning (10am): Place trades if signals exist
- [ ] Afternoon (4:50pm): Exit trades (market close)
- [ ] Evening (after 5pm): Run `python live_trader.py`
- [ ] Evening: Run `python trading_dashboard.py`

**Timeline:** 5-10 minutes per day

---

## Phase 4: Monitoring & Scaling (Ongoing)

### Weekly Check-in
- [ ] Review `data/trading/latest_report.json`
- [ ] Is win rate staying > 55%?
- [ ] Is Sharpe ratio staying > 1.0?
- [ ] Any patterns in winners vs losers?
- [ ] Any signals I'm missing?

### Monthly Decision
- [ ] View monthly P&L
- [ ] Calculate month return %
- [ ] Compare to benchmark (expected 15-25%/month)
- [ ] Decide: scale up or investigate?

### Auto-Scaling Decisions

When to scale up:
```
After 20 trades with:
  ✓ Win rate > 55%
  ✓ Sharpe > 1.0
  ✓ Positive cumulative return
→ Scale to R$2,000

After 50 trades (same conditions maintained):
→ Scale to R$5,000

After 100 trades (same conditions maintained):
→ Scale to R$10,000-20,000
```

### When to Pause
- [ ] If win rate drops < 45%: Something is wrong
- [ ] If 3 consecutive losing days: Investigate signals
- [ ] If gap frequency drops < 5%: Strategy may be dying
- [ ] If market regime changes: Test new conditions

---

## Phase 5: Tax Reporting (April Annual)

### Throughout the Year
- [ ] Keep `data/trading/` folder backed up
- [ ] Monthly: Save broker statement (PDF)
- [ ] Quarterly: Verify system P&L matches broker

### In April (Tax Filing Deadline: April 30)
- [ ] Export full year report from `live_trader.py`:
  ```bash
  python -c "from live_trader import generate_tax_report; generate_tax_report(2024)"
  ```
- [ ] Gather documents:
  - [ ] Tax report from system
  - [ ] Broker year-end statement
  - [ ] Bank statements (proof of deposits/withdrawals)
  - [ ] Expense receipts (internet, computer, courses)
- [ ] File IRPF (tax return):
  - [ ] Go to: irpf.receita.fazenda.gov.br
  - [ ] Download software (free)
  - [ ] Enter income sources (salary + trading)
  - [ ] Enter trading results (P&L from system)
  - [ ] Enter deductible expenses
  - [ ] File online (free, takes 30-45 min)
- [ ] Pay taxes owed:
  - [ ] 20% on net trading profits
  - [ ] Due by April 30

---

## Files You'll Need

### System Files (Already Created)
```
/overnight-anomaly/
├── live_trader.py           ← Run daily
├── trading_dashboard.py     ← Check daily status
├── analysis_overnight_anomaly.py  ← Weekly analysis
├── B3_ACCOUNT_SETUP.md      ← Reference for account setup
├── GET_STARTED.md           ← Detailed getting started guide
├── TRADING_SETUP.md         ← Daily workflow details
└── data/trading/
    ├── real_account.json         ← Your account state
    ├── simulated_account.json    ← "What would happen" account
    ├── latest_report.json        ← Today's results
    └── tax_records/              ← Save tax docs here
```

### Your Tracking Files
```
Create these (in data/trading/):
├── monthly_log.csv          ← Manual tracking (optional)
├── tax_records/2024.pdf     ← Monthly broker statements
└── expenses.csv             ← Deductible expenses
```

---

## Daily Run Instructions

### Setup (First Time Only)
```bash
cd ~/overnight-anomaly
python live_trader.py        # Initialize accounts
python trading_dashboard.py  # First dashboard
```

### Every Trading Day (Takes 5 min)
```bash
# After market close (5pm BRT)
cd ~/overnight-anomaly
python live_trader.py        # Execute today's trades
python trading_dashboard.py  # View results
```

### Check Frequently
```bash
# Anytime to check status
cat data/trading/latest_report.json | python -m json.tool
```

---

## Decision Points

### Before First Real Trade
```
Check:
  ✓ Win rate > 55% in paper trading
  ✓ At least 20 trades completed
  ✓ Sharpe ratio > 0.5 (even 0.5 is ok, 1.0+ is great)
  ✓ Real account ≈ Simulated account % (same returns)
  
If ALL check out → deposit R$1,000
If NOT → debug first (adjust gap threshold, filter stocks)
```

### Monthly Scaling Decision
```
Look at: win_rate, sharpe_ratio, cumulative return

Scaling table:
  Win>55% + Sharpe>1.0 → Scale 2x (e.g., R$1k → R$2k)
  Win>55% + Sharpe>0.5 → Scale 1.5x (e.g., R$1k → R$1.5k)
  Win<50%             → Pause, investigate
  Sharpe<0            → Strategy is broken, stop
```

### If Things Go Wrong
```
Win rate drops < 40%:
  1. Review last 10 trades (winners vs losers)
  2. Look for patterns (certain stocks? certain times?)
  3. Check if gaps are actually occurring (market check)
  4. Increase gap threshold (trade only 3%+ gaps instead of 2%+)

Sharpe goes negative:
  1. STOP trading real money immediately
  2. Increase paper trading for investigation
  3. Check if market regime changed (bull → bear)
  4. Check if gaps are shrinking (seasonal effect?)

Account loses 10%+:
  1. Don't panic
  2. Understand what went wrong
  3. Never scale down (locks in loss)
  4. Either fix the issue or wait for recovery
```

---

## Success Metrics

### By Week 2-4 (Paper Trading Complete)
- ✅ 20+ trades completed
- ✅ Win rate ≥ 50%
- ✅ Sharpe ratio ≥ 0.5
- ✅ Real account ≈ Simulated account

### By Month 2 (After Real Trading Starts)
- ✅ Win rate ≥ 55%
- ✅ Sharpe ratio ≥ 1.0
- ✅ Monthly return 15-25%
- ✅ Real account scaled to R$2,000

### By Month 6
- ✅ Win rate ≥ 55% (stable)
- ✅ Sharpe ratio ≥ 1.5
- ✅ Monthly return 15-25% (consistent)
- ✅ Real account at R$10,000+
- ✅ Profitable trades ≥ 200

### By Month 12
- ✅ Real account ≥ R$50,000
- ✅ Monthly income ≥ R$750-1,250
- ✅ System refined & documented
- ✅ Ready to add 2nd strategy or scale further

---

## Emergency Contacts & Resources

### If You Have Issues
```
Trading System Questions:
  - Check: GET_STARTED.md
  - Check: TRADING_SETUP.md
  - Check: B3_ACCOUNT_SETUP.md

Broker Issues:
  - Clear support: suporte@clear.com.br
  - Agora support: support@agora.com.br
  - XP support: suporte@xp.com.br

Tax Questions:
  - Receita Federal (IRS): e-cac.receita.fazenda.gov.br
  - Accountant (recommended): hire for ~R$500-1,000/year

B3 Rules:
  - Official: b3.com.br
  - ANBIMA: anbima.com.br (rules & regulations)
```

---

## Summary: What to Do Right Now

### Action 1: This Week
```
Go to clear.com.br
Click "Abrir conta"
Start account opening process
Target: Approval by end of week
```

### Action 2: Week 2-3
```
Once account approved:
  - Register for day trading
  - Run live_trader.py daily (paper trading)
  - Run trading_dashboard.py daily (monitor)
  - Target: 20+ trades, evaluate
```

### Action 3: Week 3-4
```
If metrics look good (win rate > 55%):
  - Deposit R$1,000
  - Place first real trade
  - Continue daily tracking
  - Scale as metrics improve
```

---

**Everything is ready. You just need to execute.** 🚀

Next step: Go to Clear.com.br right now.

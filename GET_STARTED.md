# Get Started: Trading with R$1,000

## Week 1: Setup & Backtesting

### Day 1-2: Choose Broker & Open Account
```
Requirements:
  ✓ B3 trading account (any retail broker)
  ✓ Minimum deposit: R$1,000
  ✓ Preferred: Cheapest commission (0.02-0.05%)
  
Recommended brokers (low commission):
  - Clear (0.02%)
  - B3 direct (0.02-0.03%)
  - Rico (0.03%)
  
Time needed: 1-2 days (ID verification)
Cost: R$1,000 capital
```

### Day 3-7: Run Backtests & Paper Trade
```bash
# 1. Run analysis + full backtests for every strategy
python analysis_overnight_anomaly.py
# Wait for:
#   data/analysis/strategy_results.json
#   data/analysis/backtest_results.json
#   data/analysis/backtest_trades.parquet
#   data/analysis/backtest_equity_curves.parquet

# 2. Run the live trader (backtesting on recent data)
python live_trader.py
# Check: data/trading/latest_report.json

# 3. View dashboard
python trading_dashboard.py

# 4. Repeat daily for 5-7 days
# Watch the real account grow from R$1,000
```

**What you're watching:**
- Are the signals real? (Compare simulated vs real outcomes)
- What's the actual win rate? (Current: 42.9% — want > 55%)
- Are there patterns in winners vs losers?

## Week 2-4: Build Confidence

### Daily Routine (5 min)
```bash
# Each day after B3 closes (after 5pm)
python live_trader.py      # Execute today's trades
python trading_dashboard.py # Check performance

# After 1 week of trading:
cat data/trading/real_account.json | python -m json.tool
# Monitor: win_rate, sharpe_ratio, total_trades
```

### Milestones
```
After 20 trades:
  ✓ If win rate > 55%: Ready to scale to R$2,000
  ✓ If win rate < 45%: Something is wrong, debug

After 50 trades:
  ✓ If Sharpe > 1.0: Confident edge exists
  ✓ Real account should be ~R$2-5k by now

After 100 trades:
  ✓ Scale to R$10k-20k
  ✓ Consider adding leverage (2x) or second strategy
```

## Your First Real Trade (When Ready)

Once you have:
- ✅ 20+ trades with >55% win rate
- ✅ Sharpe ratio > 1.0
- ✅ Real + simulated accounts in sync
- ✅ Confidence in signals

### Place a Real Trade

**Manual Process (until automated):**

1. **Morning (9:55am BRT, before market open)**
   ```
   Check overnight gap (preabe vs previous preuln)
   If gap > 2%:
     Open broker platform
     Check the gap is real
     Place order for 1% of capital
   ```

2. **Order Details**
   ```
   Size: R$10 (1% of R$1k) per trade
   Entry: Market order at market open (preabe)
   Exit: Market order at close (preuln)
   Type: Day trade (buy and sell same day)
   ```

3. **Throughout Day**
   ```
   Monitor position
   Don't intervene (let the reversal play out)
   Exit at market close
   ```

4. **End of Day**
   ```
   Record in live_trader.py:
     - Ticker traded
     - Entry/exit prices
     - P&L
   
   Run: python live_trader.py (to log the trade)
   Run: python trading_dashboard.py (to see results)
   ```

## Automation Path (Optional)

Once confident, integrate with broker API:

```python
# In live_trader.py, add (pseudocode):
import broker_api

def place_real_trade(ticker, entry_price, signal):
    account = broker_api.login(username, password)
    order = account.place_order(
        ticker=ticker,
        quantity=1,  # 1% of capital
        price=entry_price,
        order_type="market"
    )
    return order

# Then in main():
for signal in signals:
    if REAL_TRADING_ENABLED:
        order = place_real_trade(signal["ticker"], ...)
```

But start manual first — understand what's happening.

## What to Do If Things Go Wrong

### Win Rate Drops Below 40%
```
Signal quality is bad. Options:
  1. Filter gaps: only trade gaps > 3% instead of 2%
  2. Filter liquidity: only trade INEP4, MGEL4, TELB3 (proven winners)
  3. Filter by volatility: skip when vol is extremely low
  4. Pause real trading, increase paper size to 100%
```

### Sharpe Ratio Drops
```
Strategy is getting noise. Options:
  1. Check if market regime changed (bull → bear)
  2. Check if gap frequency changed (you can monitor this)
  3. Add filters for high volatility only
  4. Add second strategy (momentum) to diversify
```

### Real Account Loses >10%
```
Stop trading immediately. Options:
  1. Review every trade: which were winners? which lost?
  2. Look for patterns in losers (specific tickers? days?)
  3. Increase real account only after understanding the issue
  4. Never panic-scale down (that locks in losses)
```

## Scaling Plan

```
Start:        R$1,000 (1 month minimum)
    ↓ (win rate > 55%, Sharpe > 1)
Step 1:       R$2,000 (month 2)
    ↓ (maintain metrics for 2-4 weeks)
Step 2:       R$5,000 (month 3)
    ↓ (same conditions)
Step 3:      R$10,000 (month 4)
    ↓ (consider adding leverage 2x OR second strategy)
Step 4:      R$20-50,000 (months 5-6)
    ↓
Target:     R$100,000 (month 6-12)
```

If each step takes 1 month and profit is 15-25%/month:
- R$1k → R$2k by month 2 (R$150-250 profit)
- R$2k → R$5k by month 3 (R$300-500 profit)
- R$5k → R$10k by month 4 (R$750-1,250 profit)
- **Target: R$100k by month 12, earning R$1.5-2.5k/month**

## Tracking Checklist

### Daily (takes 5 min)
- [ ] Run `python live_trader.py`
- [ ] Run `python trading_dashboard.py`
- [ ] Note any unusual signals or market moves
- [ ] If trading real money: record the trades

### Weekly
- [ ] Review `data/trading/real_account.json`
- [ ] Check win rate trend (going up or down?)
- [ ] Check Sharpe ratio (getting better or worse?)
- [ ] Decide: continue, pause, or scale up?

### Monthly
- [ ] Calculate actual return %
- [ ] Compare real vs simulated (should be same %)
- [ ] Decide next scaling step
- [ ] Review any failed trades for patterns

## Important Reminders

1. **Start with R$1,000, not R$100,000**
   - Proves the strategy works
   - Manageable psychological pressure
   - Auto-scale as confidence builds

2. **Don't skip the simulation phase**
   - Paper trade for 4-8 weeks minimum
   - Real money will come

3. **Watch out for gaps shrinking**
   - Current market: 7.6% of trades have 2%+ gaps (vs 25% historically)
   - If gaps keep shrinking, edge disappears
   - Monitor this metric weekly

4. **Taxes & Fees**
   - Commission: 0.05% per trade (round-trip 0.1%)
   - Taxes: 15% (position trading >30 days) or 20% (swing)
   - Keep records for filing

5. **Never revenge trade**
   - Stick to the system
   - If a trade loses, the next one is independent
   - Don't double down

---

You have everything you need. 

**Next 3 actions:**
1. Open broker account (by end of week)
2. Run `python live_trader.py` daily (20 times minimum)
3. When ready, place your first real R$10 trade

Good luck! 🚀

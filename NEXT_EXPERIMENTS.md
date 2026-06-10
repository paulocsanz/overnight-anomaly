# Next Experiments to Run

We've validated ONE profitable edge (gap reversal) and eliminated two bad ideas. Here's what to test next.

## Tier 1: Validate What Works (Do It Next)

These test if our gap reversal finding is **robust and not a data artifact**.

### 1. Out-of-Sample Test (Most Important)
**Question:** Does gap reversal work on 2024-2026 data (after we found it on 1986-2023)?

```python
def test_gap_reversal_out_of_sample():
    # Train data: 1986–2023
    # Test data: 2024–2026 (ONLY 2.5 years, but recent market)
    # IF edge survives: real edge
    # IF edge dies: data artifact / overfitting
```

**Why:** If edge only works on old data, it's dead. If it works on recent data, we might have something.

---

### 2. Bull vs Bear Market
**Question:** Does gap reversal work in both bull and bear markets?

```python
# Use 2008 crash, 2020 COVID crash, 2022 rate hike crash as test periods
# Hypothesis: gap reversal works in VOLATILITY, not direction
# Expected: profitable in both rising and falling markets
```

---

### 3. By Sector
**Question:** Does reversal work equally well in all sectors?

Use B3 sector indices (available in collector data):
- Banks (BBDC4, ITUB4)
- Energy (PETR4, VALE5)  
- Utilities (TAEE4, EQTL3)
- Retail (MGLU3, VVAR3)

Hypothesis: IT/volatile sectors should show STRONGER reversals.

---

## Tier 2: Find Better Variations (Do After Validating)

These test if we can **improve** the gap reversal strategy.

### 4. Partial Position Sizing
**Question:** Should we size trades based on gap magnitude?

```python
# Instead of: all 1% gaps = same position
# Try: 0.5% gap = 0.5 position, 3% gap = 3 position
# Expected: bigger gaps → bigger positions → better risk-adjusted returns
```

---

### 5. Different Exit Strategies
**Question:** Exit at close? Or at 1% profit? Or at first touch of entry price?

```python
# Current: exit at close (forced 1-day hold)
# Try: exit when price touches pre-gap level (reversal complete)
# Try: exit when 1% reversal achieved
# Try: exit when volume spikes (conviction move)
# Expected: better risk/reward if we exit early
```

---

### 6. Intraday Patterns with PriceReport
**Question:** Do intraday minute-bars show the same reversal?

Requires parsing `PriceReport` XML files (more complex).
- If gaps reverse within first 30 min: can trade micro-patterns
- If reversal takes until close: stick with day-trades

---

## Tier 3: Find NEW Edges (After Validating Tier 1)

### 7. Momentum (Opposite of Reversion)
**Question:** Do stocks that moved +2% yesterday tend to move +% today?

```python
# Previous finding: mean reversion LOSES (stocks continue)
# So: TEST MOMENTUM instead
# Signal: IF yesterday +2%, today buy expecting +%
# Expected: opposite of mean reversion results
```

Why this matters: We found reversion LOSES. That means momentum might WIN.

---

### 8. Volatility Mean Reversion
**Question:** When intraday volatility spikes, does it compress next day?

```python
# Current vol is HIGH (say 5% daily range)
# Hypothesis: next day vol will be LOWER (compress back to mean)
# Signal: when vol > 75th percentile, sell volatility (trade smaller, bet on calm)
```

---

### 9. Sector Rotation
**Question:** When one sector outperforms, do other sectors catch up?

B3 provides index weights. If Banks were up +3% and Energy was flat, does Energy catch up?

```python
# Use B3 index data from collector
# Compute sector returns
# Buy underperformers, short outperformers
# Expected: mean-reversion between sectors
```

---

### 10. Correlated Pairs
**Question:** When two correlated stocks diverge, do they reconverge?

```python
# Find pairs with 0.7+ correlation
# When they diverge >3%, trade to converge
# Example: PETR4 and VALE5 (both commodities)
#   If PETR4 up 2% and VALE5 flat → long VALE5 short PETR4
```

---

## Tier 4: Advanced Experiments (PhD Level)

### 11. Machine Learning Feature Importance
Find which features actually predict returns:

```python
# Features: gap_pct, volume_ratio, vol_regime, sector, day_of_week, ...
# Train gradient boosting to predict next-day return
# See which features matter most
# Expected: validates gap_pct, shows hidden features
```

---

### 12. Regime Switching Models
**Question:** Do markets have 2–3 distinct regimes with different rules?

- Regime 1: Trending up (momentum wins)
- Regime 2: Ranging (reversion wins)
- Regime 3: Volatile crashes (gaps reverse hard)

Switch strategies based on detected regime.

---

### 13. Hidden Markov Model
Estimate regime probabilities and trade probabilistically.

---

## How to Run These

### Quick Template (1-2 hours each)

```python
def test_gap_reversal_out_of_sample(df: pd.DataFrame) -> dict:
    """Test on recent data (2024-2026)."""
    recent = df[df["date"] >= "2024-01-01"]
    
    # Same logic as before
    recent["signal"] = np.where(recent["gap_pct"] > 2.0, -1, 1)
    recent["net_ret"] = ... # same calculation
    
    return {
        "name": "gap_reversal_oos",
        "trades": len(recent[recent["signal"] != 0]),
        "avg_return": recent[recent["signal"] != 0]["net_ret"].mean(),
        "profitable": avg_return > 0,
        "note": "Out-of-sample test (2024-2026 only)"
    }

# Add to experiment_framework.py and run
```

### Medium Effort (3-5 hours)

Add new feature engineering:

```python
# In compute_returns_and_gaps():
df["sector"] = df["codneg"].map(TICKER_TO_SECTOR)
df["is_bull_market"] = df["close_to_close_ret"].rolling(252).mean() > 0
df["vol_spike"] = df["intraday_range_pct"] > df["intraday_range_pct"].quantile(0.75)
```

Then test how these interact with your strategies.

---

## Prioritization

**Do first:**
1. Out-of-sample test (most important)
2. Bull vs bear market
3. By sector

**Do if #1-3 look good:**
4. Position sizing
5. Better exits
6. Momentum test (opposite of reversion finding)

**Do if you have time:**
7-13. Advanced experiments

---

## Tracking Results

All results go to `data/experiments/`:

```bash
# After each experiment round:
python experiment_framework.py

# View results:
cat data/experiments/experiments.json | python -m json.tool

# Compare against baseline (the 24 profitable experiments we found)
```

---

## The Scientific Process

1. **Hypothesis:** "Gap reversal works"
2. **Test:** Run it on all conditions → TRUE ✅
3. **Validate:** Does it work out-of-sample? (do next)
4. **Refine:** Under what exact conditions? (gap size, vol regime, sector)
5. **Improve:** Can we make it better? (position sizing, exits)
6. **Scale:** Trade it for real (only after validation)

You're at step 2. Step 3 is **out-of-sample validation.** That's the gate keeper.

Good luck! 🚀

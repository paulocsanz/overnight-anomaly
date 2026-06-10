# B3 Trading Research Platform

Multi-theory framework for developing and testing non-HFT trading strategies on 40 years of Brazilian equity market data.

## Quick Start

```bash
# 1. Run analysis of patterns
python analysis_overnight_anomaly.py

# 2. Backtest strategies for profitability
python backtest_strategies.py

# 3. Results
cat data/analysis/strategy_results.json
cat data/analysis/backtest_results.json
```

## What You Have

### Data (✅ Ready)
- **40 years of daily OHLCV data** (1986–2026)
- **2.6M records** from 1,860 highly liquid Brazilian equities
- **Live collector** on Railway, updating every 6 hours
- All spot equities filtered (codbdi=02, tpmerc=010) for real trading

### Analysis Framework
**`analysis_overnight_anomaly.py`** — Tests 5 pattern categories:
1. **Overnight Gap Anomaly** — Do gaps mean-revert intraday?
2. **Volume Anomaly** — Do high-volume days predict returns?
3. **Mean Reversion** — Do extreme moves revert next day?
4. **Day-of-Week Effect** — Calendar anomalies (Fri/Mon bias)
5. **Volatility Anomaly** — Does vol predict vol?

### Backtester
**`backtest_strategies.py`** — Simulates real trading with:
- Commission costs (0.05% realistic for B3)
- Slippage (0.02% entry/exit)
- Position sizing (5% max per trade)
- Sharpe ratio and win rates

## Current Findings

| Strategy | Trades | Win Rate | Return/Trade | Total Return |
|----------|--------|----------|--------------|--------------|
| **Gap Reversal** | 1.1M | 42.5% | +0.534% | (signal issue) |
| **High Volume Breakout** | 560K | 42.2% | +0.055% | +30.6% |
| **Mean Reversion** | 63K | 30.3% | -0.801% | **-50.7%** ❌ |
| **Day-of-Week Bias** | 1.6M | 37.6% | +0.065% | +104% ✅ |
| **Benchmark (Buy & Hold)** | 2.7M | 37.5% | +0.175% | +252% 📊 |

**Interpretation:**
- ✅ Day-of-week effect shows measurable edge (+104% cumulative on modest signals)
- ⚠️ Gap reversal has edge but high turnover eats into profits
- ❌ Mean reversion doesn't work on this data
- 📊 Buy & hold returns +252% (likely sector-dependent, not strategy-dependent)

## How to Add New Strategies

### In `analysis_overnight_anomaly.py` (pattern discovery):

```python
def test_your_idea(df: pd.DataFrame) -> dict:
    """Test: [Your hypothesis here]"""
    result = {
        "strategy": "your_idea_name",
        "description": "What you tested",
        "metric_1": value,
        "metric_2": value,
    }
    return result

# Then in main():
print("\n6. YOUR IDEA")
result = test_your_idea(df)
print(f"   Key finding: {result['metric_1']}")
strategies.append(result)
```

### In `backtest_strategies.py` (test for profitability):

```python
def backtest_your_idea(df: pd.DataFrame) -> dict:
    """Backtest with real transaction costs."""
    df = df.copy().sort_values(["codneg", "date"])
    
    # Create signals (1=long, -1=short, 0=no trade)
    df["signal"] = 0  # Your logic here
    
    # Entry/exit prices with slippage
    df["entry_price"] = df["preabe"] * (1 + SLIPPAGE_PCT / 100)
    df["exit_price"] = df["preuln"] * (1 - SLIPPAGE_PCT / 100)
    
    # Calculate returns
    df["gross_ret"] = (df["exit_price"] - df["entry_price"]) / df["entry_price"] * 100
    df["gross_ret"] *= df["signal"]
    df["net_ret"] = df["gross_ret"] - (2 * COMMISSION_PCT)
    
    trades = df[df["signal"] != 0]
    
    return {
        "strategy": "your_idea_name",
        "trades": len(trades),
        "win_rate": (trades["net_ret"] > 0).sum() / len(trades) * 100,
        "avg_return_per_trade": trades["net_ret"].mean(),
        ...
    }
```

## Available Data Columns

After `compute_returns_and_gaps()`, you can use:

```
Prices:
  preabe, premax, premin, preuln (OHLC in R$)

Volumes:
  quatot (shares), voltot (R$ volume)

Computed metrics:
  gap_pct: overnight gap %
  daily_ret_pct: open-to-close return %
  close_to_close_ret: previous close to current close %
  intraday_range_pct: high-low / low %
  volume_ratio: today vs 20-day MA
  volatility_ma20: 20-day intraday range MA

Time:
  date (datetime)
  codneg (ticker symbol)
```

## Ideas to Explore

### Quick Wins (easy to implement)
- [ ] Earnings surprises (need earnings data)
- [ ] Support/resistance rebounds (historical levels)
- [ ] Relative strength vs market (beta-adjusted)
- [ ] Reversal after N consecutive days up/down
- [ ] Volume & price breakouts (already tested partially)

### Medium (require more data)
- [ ] Sector rotation (use B3 index portfolios from collector)
- [ ] Correlation pairs trading (long one, short correlated one)
- [ ] Intraday patterns (need PriceReport XML parsing)
- [ ] News sentiment (if you source news feeds)

### Complex (academic approaches)
- [ ] Statistical arbitrage / cointegration
- [ ] Machine learning (gradient boosting on features)
- [ ] Hidden Markov models for regime detection
- [ ] Options implied vol anomalies

## Testing Best Practices

1. **Walk-forward validation** — Train on 1986–2015, test on 2016–2026
2. **Out-of-sample testing** — Don't optimize on same data you test
3. **Transaction costs matter** — 0.05% commission kills thin edges
4. **Look for stability** — Does strategy work across all years/sectors?
5. **Economic rationale** — Can you explain *why* it should work?
6. **Statistical rigor** — With millions of data points, tiny correlations become "significant"

## Data Updates

Collector runs every 6 hours on Railway:
```
b3-public-data-collector / b3-collector service
├─ Index API snapshots (27 indices)
├─ Pesquisa por Pregão daily files
└─ COTAHIST yearly updates

Data location: /data/b3_lake/ (Railway persistent volume)
Local: ./data/parquet/cotahist/YYYY.parquet (41 files, 1.6 GB)
```

New analysis data updates on each run of `analysis_overnight_anomaly.py`:
```
./data/analysis/
├─ strategy_results.json
├─ liquidity_filtered_with_metrics.parquet
└─ backtest_results.json
```

## Next Steps

1. **Add your theories** — Edit `analysis_overnight_anomaly.py` and `backtest_strategies.py`
2. **Test profitability** — Run backtester, check Sharpe ratio and win rate
3. **Validate rigorously** — Walk-forward, out-of-sample, statistical significance
4. **Paper trade** — Small positions in real market to verify live behavior
5. **Scale gradually** — Only risk capital on proven strategies with edge

## Project Structure

```
overnight-anomaly/
├─ b3_data_collector.py              (Railway collector daemon)
├─ parse_cotahist.py                 (COTAHIST parser)
├─ analysis_overnight_anomaly.py      (Pattern discovery)
├─ backtest_strategies.py             (Profitability testing)
├─ data/
│  ├─ parquet/cotahist/YYYY.parquet  (41 years OHLCV)
│  └─ analysis/
│     ├─ strategy_results.json
│     ├─ backtest_results.json
│     └─ liquidity_filtered_with_metrics.parquet
├─ README.md                          (this file)
├─ TRADING_ALGOS_FRAMEWORK.md         (how to add strategies)
└─ B3_COLLECTOR_RUNBOOK.md            (deployment notes)
```

## Disclaimer

Trading is risky. Backtested returns are not guaranteed in live trading.
- Past performance ≠ future results
- Slippage/commission can eliminate small edges
- Market conditions change; strategies need continuous monitoring
- Only trade what you can afford to lose

---

Happy trading! 🚀

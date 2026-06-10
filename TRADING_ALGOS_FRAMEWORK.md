# Trading Algos Research Framework

Multi-theory platform for testing trading strategies against 40 years of B3 historical data.

## Quick Start

```bash
python analysis_overnight_anomaly.py
```

This runs all registered strategies and outputs results to `data/analysis/strategy_results.json`.

## Current Strategies Implemented

1. **Overnight Gap Anomaly** — Do overnight gaps persist or mean-revert?
2. **Volume Anomaly** — Do abnormally high/low volume days predict direction?
3. **Mean Reversion** — After extreme moves, do prices revert the next day?
4. **Day-of-Week Effect** — Do certain weekdays have inherent bias?
5. **Volatility Anomaly** — Do high-volatility days predict larger next-day moves?

## How to Add a New Strategy

### 1. Create a test function in `analysis_overnight_anomaly.py`

```python
def test_your_strategy_name(df: pd.DataFrame) -> dict:
    """Test: [one-line description of what you're testing]
    
    Reference: [link to article/paper if applicable]
    """
    # Your analysis code here
    result = {
        "strategy": "your_strategy_name",
        "description": "What you tested",
        "sample_size": len(df),
        # Add your metrics
        "metric_1": value,
        "metric_2": value,
    }
    return result
```

### 2. Call it in `main()`

```python
    print("\n6. YOUR STRATEGY NAME")
    result = test_your_strategy_name(df)
    # Print key findings
    print(f"   Key metric: {result['metric_1']}")
    strategies.append(result)
```

### 3. Available data columns

After `compute_returns_and_gaps()`, the DataFrame has:

```
Core COTAHIST data:
  - codneg: ticker symbol
  - date: trading date
  - preabe, premax, premin, preuln: OHLC prices
  - quatot: share volume
  - voltot: financial volume (R$)

Computed metrics:
  - gap_pct: overnight gap %
  - daily_ret_pct: open-to-close return %
  - close_to_close_ret: previous close to current close %
  - intraday_range_pct: high-low range as % of low price
  - volume_ratio: today's volume vs 20-day MA
  - volatility_ma20: 20-day avg intraday range
```

## Example Strategies to Explore

### Earnings-Related (if you can source earnings dates)
- Do stocks gap up/down more on certain earnings seasons?
- Historical earnings anomalies in Brazilian market?

### Technical Patterns
- After 3 down days, what's the probability of reversal?
- Support/resistance levels based on historical data
- Moving average crossovers

### Market Microstructure
- Bid-ask bounce effects (if we add intraday data)
- Market maker inventory levels

### Seasonality
- Month-end effects
- Holiday clustering
- Summer holidays (BR-specific)

### Macro Correlations (if we add macro data)
- Interest rate announcement effects
- Currency (BRL/USD) correlation with equity gaps
- Commodity price (oil) correlation with specific sectors

### Statistical Arbitrage
- Pairs trading between correlated stocks
- Mean reversion in sector indices
- Cointegration tests

## Data Pipeline

```
Raw B3 data (COTAHIST zip files)
    ↓
parse_cotahist.py → /data/parquet/cotahist/YYYY.parquet
    ↓
analysis_overnight_anomaly.py
    ├→ Load & concat all years
    ├→ Filter liquid stocks (avg daily volume > R$100k, 252+ trading days)
    ├→ Compute metrics (gaps, returns, volume ratios, etc.)
    └→ Run all strategy tests
    ↓
/data/analysis/
    ├→ strategy_results.json (summaries)
    └→ liquidity_filtered_with_metrics.parquet (full data for custom analysis)
```

## Testing Best Practices

1. **Always filter for liquidity** — Delisted/tiny stocks create extreme gaps that distort results
2. **Use realistic transaction costs** — Add 0.05-0.10% per trade when scoring
3. **Walk-forward validation** — Train on early years, test on later years
4. **Look for statistical significance** — With 2.6M observations, tiny effects become "significant"
5. **Out-of-sample testing** — Don't optimize on the same data you test on

## Interpreting Results

### Red Flags
- **Extreme values (inf, -inf, nan)** → Data quality issue or division by zero. Check filters.
- **Zero correlation** → No relationship, strategy won't work
- **Tiny p-value with tiny effect size** → Statistical artifact, not tradeable
- **Only works on day 1** → Likely a data artifact from stock list changes

### Green Flags
- **Consistent across all years** → Robust pattern
- **Works across different market conditions** → Not regime-dependent
- **Economic rationale** → You can explain *why* it should work
- **Profitable after costs** → At least +1-2% annual Sharpe ratio

## Next Steps

1. **Add intraday data** — Parse PriceReport (PR*.xml) for minute-level data
2. **Add sector/index data** — B3 index portfolios can identify sector rotations
3. **Correlation analysis** — Which strategies work together? Which are redundant?
4. **Backtester** — Simulate real trading with slippage, commissions, capital limits
5. **Risk management** — Position sizing, drawdown limits, hedging

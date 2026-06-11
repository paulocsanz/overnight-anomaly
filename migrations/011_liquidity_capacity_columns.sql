-- Store liquidity-aware sizing diagnostics for backtest trades.
ALTER TABLE trades ADD COLUMN IF NOT EXISTS intended_position_size DECIMAL(12, 2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS liquidity_cap_brl DECIMAL(12, 2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS capacity_used_pct DECIMAL(10, 4);

-- Default capacity policy applied by the Rust backtest runner if omitted:
--   max position <= 2% of trailing 10-day average BRL volume
--   max position <= 5% of prior-day BRL volume
--   skip if capped position < R$500
--   max same-day gross exposure per strategy account <= 100% equity

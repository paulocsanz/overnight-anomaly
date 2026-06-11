CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    total_trades INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE trades ADD COLUMN IF NOT EXISTS backtest_run_id UUID REFERENCES backtest_runs(id);
CREATE INDEX IF NOT EXISTS idx_trades_backtest_run_id ON trades(backtest_run_id);

CREATE TABLE IF NOT EXISTS backtest_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status       VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending | running | completed | failed
    years_run    INTEGER[] DEFAULT '{}',
    total_trades INTEGER DEFAULT 0,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_jobs_created ON backtest_jobs(created_at DESC);

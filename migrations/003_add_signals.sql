CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategies(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,
    gap_pct DECIMAL(10, 4) NOT NULL,
    prev_close DECIMAL(10, 4),
    open_price DECIMAL(10, 4),
    signal_date VARCHAR(10) NOT NULL,
    executed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_pending ON signals(executed, created_at) WHERE executed = false;
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_id);

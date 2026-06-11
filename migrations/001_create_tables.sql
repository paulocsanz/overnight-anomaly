CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    signal_config JSONB NOT NULL,
    trading_rules JSONB NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY,
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    account_type VARCHAR(50) NOT NULL,
    initial_capital DECIMAL(12, 2) NOT NULL,
    current_equity DECIMAL(12, 2) NOT NULL,
    num_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 2) DEFAULT 0,
    sharpe_ratio DECIMAL(10, 4) DEFAULT 0,
    cumulative_return DECIMAL(10, 4) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    trade_date VARCHAR(10) NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    entry_price DECIMAL(10, 4) NOT NULL,
    exit_price DECIMAL(10, 4) NOT NULL,
    gap_pct DECIMAL(10, 4) NOT NULL,
    signal VARCHAR(20) NOT NULL,
    gross_return_pct DECIMAL(10, 4),
    net_return_pct DECIMAL(10, 4),
    pnl DECIMAL(12, 2),
    position_size DECIMAL(12, 2),
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY,
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT,
    acknowledged BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS tax_records (
    id UUID PRIMARY KEY,
    strategy_id UUID NOT NULL REFERENCES strategies(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    total_trades INTEGER,
    gross_pnl DECIMAL(12, 2),
    commissions DECIMAL(12, 2),
    net_pnl DECIMAL(12, 2),
    tax_owed DECIMAL(12, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_strategy ON accounts(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_alerts_strategy ON alerts(strategy_id);
CREATE INDEX IF NOT EXISTS idx_tax_strategy ON tax_records(strategy_id);

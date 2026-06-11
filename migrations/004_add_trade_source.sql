ALTER TABLE trades ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'live';
CREATE INDEX IF NOT EXISTS idx_trades_source ON trades(source);

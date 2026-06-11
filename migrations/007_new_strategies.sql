-- Add 4 research-inspired strategies (idempotent via ON CONFLICT DO NOTHING)

INSERT INTO strategies (id, name, description, signal_config, trading_rules, active) VALUES
(
  'a1b2c3d4-0004-0004-0004-000000000004',
  'Trend Confirmation Gap',
  'Momentum strategy that only fires when the overnight gap aligns with the prior day''s close-to-close return direction. Filters out "counter-trend" gaps that often reverse. Based on information-cascade theory: when two consecutive sessions agree on direction, institutional flow tends to continue intraday.',
  '{"gap_threshold": 1.2, "direction": "momentum", "require_trend_confirmation": true, "tickers": ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "RENT3", "B3SA3", "LREN3", "JBSS3", "SUZB3", "RADL3", "GGBR4", "KLBN11", "CSAN3"]}',
  '{"position_pct": 8.0, "max_loss_pct": 1.2, "take_profit_pct": 2.5, "close_eod": true, "slippage_bps": 6}',
  true
),
(
  'a1b2c3d4-0005-0005-0005-000000000005',
  'Volume Surge Reversal',
  'Fades gaps that occurred after a high-volume session (prior day volume > 1.5× 10-day average). High-volume days indicate crowded positioning — when the crowd is wrong on the gap direction, the reversal is sharper. Inspired by the research finding that liquidity-confirmed mispricing reverts faster.',
  '{"gap_threshold": 1.5, "direction": "reversal", "volume_multiplier": 1.5, "tickers": ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "RENT3", "B3SA3"]}',
  '{"position_pct": 8.0, "max_loss_pct": 1.0, "take_profit_pct": 2.0, "close_eod": true, "slippage_bps": 5}',
  true
),
(
  'a1b2c3d4-0006-0006-0006-000000000006',
  'Extreme Gap Fade',
  'Fades extreme overnight gaps > 5% on any B3 equity. At 5%+ moves are 2+ standard-deviation events; statistical reversion is very high (historically > 65% fill rate). No ticker filter — casts wide net across all liquid B3 stocks. Higher slippage budget to account for wide spreads on gap-open.',
  '{"gap_threshold": 5.0, "direction": "reversal"}',
  '{"position_pct": 5.0, "max_loss_pct": 2.5, "take_profit_pct": 4.0, "close_eod": true, "slippage_bps": 12}',
  true
),
(
  'a1b2c3d4-0007-0007-0007-000000000007',
  'Tight Range Breakout',
  'Momentum strategy that triggers when: (1) the prior day had very compressed range (high-low < 1.5% of close, indicating volatility consolidation) and (2) today gaps > 1%. Volatility compression followed by a gap suggests accumulated pressure breaking out — momentum tends to follow through. Inspired by walk-forward research showing microstructure signals are regime-dependent.',
  '{"gap_threshold": 1.0, "direction": "momentum", "require_tight_prior_range": true, "tight_range_threshold": 1.5, "tickers": ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "RENT3", "B3SA3", "LREN3", "JBSS3", "SUZB3", "RADL3", "GGBR4", "MGLU3", "CSAN3"]}',
  '{"position_pct": 8.0, "max_loss_pct": 1.2, "take_profit_pct": 2.5, "close_eod": true, "slippage_bps": 6}',
  true
)
ON CONFLICT (id) DO NOTHING;

-- Simulated + real accounts for each new strategy
INSERT INTO accounts (id, strategy_id, account_type, initial_capital, current_equity)
SELECT gen_random_uuid(), s.id, t.account_type, t.initial_capital, t.initial_capital
FROM (VALUES
  ('a1b2c3d4-0004-0004-0004-000000000004'),
  ('a1b2c3d4-0005-0005-0005-000000000005'),
  ('a1b2c3d4-0006-0006-0006-000000000006'),
  ('a1b2c3d4-0007-0007-0007-000000000007')
) AS strats(sid)
JOIN strategies s ON s.id = strats.sid::uuid
CROSS JOIN (VALUES ('real', 1000.00), ('simulated', 100000.00)) AS t(account_type, initial_capital)
WHERE NOT EXISTS (
  SELECT 1 FROM accounts a WHERE a.strategy_id = strats.sid::uuid AND a.account_type = t.account_type
);

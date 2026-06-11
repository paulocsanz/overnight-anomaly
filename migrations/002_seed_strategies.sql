-- Seed only if no strategies exist yet
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM strategies LIMIT 1) THEN

    INSERT INTO strategies (id, name, description, signal_config, trading_rules, active) VALUES
    (
      'a1b2c3d4-0001-0001-0001-000000000001',
      'Gap Reversal',
      'Mean reversion on B3 overnight gaps. Shorts large gap-ups, longs large gap-downs. Best edge on liquid large-caps (PETR4, VALE3, ITUB4). Historical win rate ~58% on gaps >2%.',
      '{"gap_threshold": 2.0, "direction": "reversal", "tickers": ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "MGLU3", "WEGE3", "RENT3"]}',
      '{"position_pct": 10.0, "max_loss_pct": 1.0, "take_profit_pct": 2.0, "close_eod": true, "slippage_bps": 5}',
      true
    ),
    (
      'a1b2c3d4-0002-0002-0002-000000000002',
      'Gap Momentum',
      'Follows strong gaps confirmed by pre-market volume. Enters in gap direction when volume > 1.5x average. Works best on gaps >3% with earnings or news catalyst.',
      '{"gap_threshold": 3.0, "direction": "momentum", "volume_multiplier": 1.5, "tickers": ["PETR4", "VALE3", "ITUB4", "BBDC4", "B3SA3", "LREN3"]}',
      '{"position_pct": 8.0, "max_loss_pct": 1.5, "take_profit_pct": 3.5, "close_eod": true, "slippage_bps": 8}',
      true
    ),
    (
      'a1b2c3d4-0003-0003-0003-000000000003',
      'High Volatility Fade',
      'Fades extreme gap moves >4% that lack fundamental catalyst. High-risk high-reward. Sized conservatively, targets quick snap-back within first 30 minutes. Complementary to Gap Reversal.',
      '{"gap_threshold": 4.0, "direction": "reversal", "atr_filter": true, "tickers": ["PETR4", "VALE3", "MGLU3", "VIIA3", "COGN3"]}',
      '{"position_pct": 5.0, "max_loss_pct": 2.0, "take_profit_pct": 4.0, "close_eod": true, "slippage_bps": 10}',
      false
    );

    -- Create real (R$1k) + simulated (R$100k) accounts for each strategy
    INSERT INTO accounts (id, strategy_id, account_type, initial_capital, current_equity) VALUES
      (gen_random_uuid(), 'a1b2c3d4-0001-0001-0001-000000000001', 'real',      1000.00,   1000.00),
      (gen_random_uuid(), 'a1b2c3d4-0001-0001-0001-000000000001', 'simulated', 100000.00, 100000.00),
      (gen_random_uuid(), 'a1b2c3d4-0002-0002-0002-000000000002', 'real',      1000.00,   1000.00),
      (gen_random_uuid(), 'a1b2c3d4-0002-0002-0002-000000000002', 'simulated', 100000.00, 100000.00),
      (gen_random_uuid(), 'a1b2c3d4-0003-0003-0003-000000000003', 'real',      1000.00,   1000.00),
      (gen_random_uuid(), 'a1b2c3d4-0003-0003-0003-000000000003', 'simulated', 100000.00, 100000.00);

  END IF;
END $$;

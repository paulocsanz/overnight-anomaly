-- Add liquidity guardrails to the formerly too-good-to-be-true Extreme Gap Momentum strategy.
-- The unfiltered variant traded thousands of micro/illiquid instruments where the fixed
-- position size often exceeded the entire daily volume.
UPDATE strategies
SET signal_config = signal_config || jsonb_build_object(
        'min_daily_volume_brl', 1000000.0,
        'min_num_trades', 100,
        'min_price', 1.0,
        'max_avg_volume_participation_pct', 2.0,
        'max_prev_volume_participation_pct', 5.0
    ),
    trading_rules = trading_rules || jsonb_build_object(
        'min_position_brl', 500.0,
        'max_daily_exposure_pct', 100.0
    ),
    description = 'Momentum on extreme overnight gaps >5%, restricted to realistically tradable B3 instruments (min R$1M daily value, min 100 trades, min R$1 open). Per-trade size is capped at the lower of 2% trailing average BRL volume and 5% prior-day BRL volume; same-day gross exposure is capped at 100% of account equity.',
    updated_at = NOW()
WHERE id = 'a1b2c3d4-0006-0006-0006-000000000006';

-- Flip Extreme Gap Fade from reversal to momentum.
-- Keep this idempotent: this project runs .sql files at every startup.
UPDATE strategies
SET signal_config = jsonb_set(signal_config, '{direction}', '"momentum"'),
    name          = 'Extreme Gap Momentum',
    updated_at    = NOW()
WHERE id = 'a1b2c3d4-0006-0006-0006-000000000006';

use crate::AppState;
use std::time::Duration;
use tokio::time::interval;
use uuid::Uuid;

pub async fn run_scheduler(state: AppState) {
    let mut ticker = interval(Duration::from_secs(60));

    loop {
        ticker.tick().await;

        // B3 operates on São Paulo time (UTC-3)
        let now = chrono::Utc::now();
        use chrono::Timelike;
        let hour = now.hour();
        let minute = now.minute();

        // 13:05 UTC = 10:05 BRT: execute pending signals shortly after open
        if hour == 13 && minute == 5 {
            tracing::info!("Market open — executing pending signals");
            if let Err(e) = execute_pending_signals(&state).await {
                tracing::error!("execute_pending_signals: {e}");
            }
        }

        // 20:15 UTC = 17:15 BRT: update account win_rate/sharpe after close
        if hour == 20 && minute == 15 {
            tracing::info!("Market close — refreshing account metrics");
            if let Err(e) = refresh_account_metrics(&state).await {
                tracing::error!("refresh_account_metrics: {e}");
            }
        }
    }
}

async fn execute_pending_signals(state: &AppState) -> anyhow::Result<()> {
    #[derive(sqlx::FromRow)]
    struct PendingSignal {
        id: Uuid,
        strategy_id: Option<Uuid>,
        ticker: String,
        signal_type: String,
        gap_pct: f64,
        prev_close: Option<f64>,
        open_price: Option<f64>,
        signal_date: String,
    }

    let signals = sqlx::query_as::<_, PendingSignal>(
        "SELECT id, strategy_id, ticker, signal_type,
                gap_pct::float8 as gap_pct,
                prev_close::float8 as prev_close,
                open_price::float8 as open_price,
                signal_date
         FROM signals WHERE executed = false ORDER BY created_at ASC",
    )
    .fetch_all(state.db.as_ref())
    .await?;

    if signals.is_empty() {
        tracing::info!("No pending signals");
        return Ok(());
    }

    tracing::info!("{} pending signals to execute", signals.len());

    for signal in &signals {
        // Which strategies to run this signal against
        let strategy_ids: Vec<Uuid> = if let Some(sid) = signal.strategy_id {
            // Signal targets a specific strategy
            vec![sid]
        } else {
            // Broadcast to all active strategies whose gap_threshold is met
            sqlx::query_scalar::<_, Uuid>(
                "SELECT id FROM strategies WHERE active = true
                 AND (signal_config->>'gap_threshold')::float8 <= $1",
            )
            .bind(signal.gap_pct.abs())
            .fetch_all(state.db.as_ref())
            .await?
        };

        for strategy_id in &strategy_ids {
            // Fetch trading rules
            let rules: Option<serde_json::Value> =
                sqlx::query_scalar("SELECT trading_rules FROM strategies WHERE id = $1")
                    .bind(strategy_id)
                    .fetch_optional(state.db.as_ref())
                    .await?;

            let rules = rules.unwrap_or(serde_json::json!({}));
            let position_pct = rules
                .get("position_pct")
                .and_then(|v| v.as_f64())
                .unwrap_or(10.0);
            let slippage_bps = rules
                .get("slippage_bps")
                .and_then(|v| v.as_f64())
                .unwrap_or(5.0);

            // Execute against both real and simulated accounts
            let accounts = sqlx::query_as::<_, (Uuid, String, f64)>(
                "SELECT id, account_type, current_equity::float8
                 FROM accounts WHERE strategy_id = $1",
            )
            .bind(strategy_id)
            .fetch_all(state.db.as_ref())
            .await?;

            for (account_id, account_type, equity) in &accounts {
                let position_size = equity * position_pct / 100.0;

                // Determine return based on direction config
                let config: Option<serde_json::Value> =
                    sqlx::query_scalar("SELECT signal_config FROM strategies WHERE id = $1")
                        .bind(strategy_id)
                        .fetch_optional(state.db.as_ref())
                        .await?;

                let direction = config
                    .as_ref()
                    .and_then(|c| c.get("direction"))
                    .and_then(|d| d.as_str())
                    .unwrap_or("reversal");

                // Simulated return model — reversal fades ~50% of gap, momentum follows ~40%
                let gross_return_pct = match direction {
                    "momentum" => signal.gap_pct * 0.4,
                    _ => -signal.gap_pct * 0.5, // reversal
                };
                let net_return_pct = gross_return_pct - slippage_bps / 100.0;
                let pnl = position_size * net_return_pct / 100.0;

                let entry_price = signal.open_price.unwrap_or(100.0);
                let exit_price = entry_price * (1.0 + net_return_pct / 100.0);

                sqlx::query(
                    "INSERT INTO trades
                     (id, account_id, strategy_id, trade_date, ticker,
                      entry_price, exit_price, gap_pct, signal,
                      gross_return_pct, net_return_pct, pnl, position_size, status)
                     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'executed')",
                )
                .bind(Uuid::new_v4())
                .bind(account_id)
                .bind(strategy_id)
                .bind(&signal.signal_date)
                .bind(&signal.ticker)
                .bind(entry_price)
                .bind(exit_price)
                .bind(signal.gap_pct)
                .bind(&signal.signal_type)
                .bind(gross_return_pct)
                .bind(net_return_pct)
                .bind(pnl)
                .bind(position_size)
                .execute(state.db.as_ref())
                .await?;

                sqlx::query(
                    "UPDATE accounts
                     SET current_equity = current_equity + $1,
                         num_trades = num_trades + 1,
                         updated_at = NOW()
                     WHERE id = $2",
                )
                .bind(pnl)
                .bind(account_id)
                .execute(state.db.as_ref())
                .await?;

                tracing::info!(
                    ticker = signal.ticker.as_str(),
                    signal_type = signal.signal_type.as_str(),
                    account_type = account_type.as_str(),
                    pnl,
                    "trade executed"
                );
            }
        }

        sqlx::query("UPDATE signals SET executed = true WHERE id = $1")
            .bind(signal.id)
            .execute(state.db.as_ref())
            .await?;
    }

    Ok(())
}

async fn refresh_account_metrics(state: &AppState) -> anyhow::Result<()> {
    // Recompute win_rate and cumulative_return for each account from its trades
    let account_ids: Vec<Uuid> = sqlx::query_scalar("SELECT id FROM accounts")
        .fetch_all(state.db.as_ref())
        .await?;

    for account_id in account_ids {
        sqlx::query(
            "UPDATE accounts SET
                num_trades       = (SELECT COUNT(*) FROM trades WHERE account_id = $1),
                win_rate         = COALESCE(
                    (SELECT 100.0 * SUM(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END)::float8
                            / NULLIF(COUNT(*), 0)
                     FROM trades WHERE account_id = $1 AND pnl IS NOT NULL), 0),
                cumulative_return = COALESCE(
                    (SELECT SUM(net_return_pct) FROM trades WHERE account_id = $1 AND net_return_pct IS NOT NULL), 0),
                updated_at = NOW()
             WHERE id = $1",
        )
        .bind(account_id)
        .execute(state.db.as_ref())
        .await?;
    }

    Ok(())
}

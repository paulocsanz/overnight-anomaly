use crate::auth::{generate_token, verify_password, verify_token, LoginRequest, LoginResponse};
use crate::models::*;
use crate::AppState;
use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    Json,
};
use chrono::Datelike as _;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

const UNBOUNDED_LIQUIDITY_CAP_BRL: f64 = 9_999_999_999.0;

fn auth_check(headers: &HeaderMap) -> Result<(), StatusCode> {
    let token = headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .unwrap_or("");
    if verify_token(token) {
        Ok(())
    } else {
        Err(StatusCode::UNAUTHORIZED)
    }
}

pub async fn login(Json(req): Json<LoginRequest>) -> Result<Json<LoginResponse>, StatusCode> {
    if verify_password(&req.password) {
        Ok(Json(LoginResponse {
            success: true,
            token: generate_token(),
            message: "Login successful".to_string(),
        }))
    } else {
        Err(StatusCode::UNAUTHORIZED)
    }
}

pub async fn create_strategy(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<CreateStrategyRequest>,
) -> Result<Json<Strategy>, StatusCode> {
    auth_check(&headers)?;
    let id = Uuid::new_v4();
    let strategy = sqlx::query_as::<_, Strategy>(
        "INSERT INTO strategies (id, name, description, signal_config, trading_rules)
         VALUES ($1, $2, $3, $4, $5)
         RETURNING id, name, description, signal_config, trading_rules, active, created_at, updated_at",
    )
    .bind(id)
    .bind(&req.name)
    .bind(req.description.as_deref())
    .bind(&req.signal_config)
    .bind(&req.trading_rules)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("create_strategy: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    for (account_type, capital) in [("real", 1000.0_f64), ("simulated", 100000.0_f64)] {
        sqlx::query(
            "INSERT INTO accounts (id, strategy_id, account_type, initial_capital, current_equity)
             VALUES ($1, $2, $3, $4, $5)",
        )
        .bind(Uuid::new_v4())
        .bind(id)
        .bind(account_type)
        .bind(capital)
        .bind(capital)
        .execute(state.db.as_ref())
        .await
        .map_err(|e| {
            tracing::error!("create_account: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;
    }

    Ok(Json(strategy))
}

pub async fn list_strategies(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<Strategy>>, StatusCode> {
    auth_check(&headers)?;
    let strategies = sqlx::query_as::<_, Strategy>(
        "SELECT id, name, description, signal_config, trading_rules, active, created_at, updated_at
         FROM strategies ORDER BY created_at DESC",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("list_strategies: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(strategies))
}

pub async fn get_strategy(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Result<Json<Strategy>, StatusCode> {
    auth_check(&headers)?;
    let strategy = sqlx::query_as::<_, Strategy>(
        "SELECT id, name, description, signal_config, trading_rules, active, created_at, updated_at
         FROM strategies WHERE id = $1",
    )
    .bind(id)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(strategy))
}

pub async fn update_strategy(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
    Json(req): Json<CreateStrategyRequest>,
) -> Result<Json<Strategy>, StatusCode> {
    auth_check(&headers)?;
    let strategy = sqlx::query_as::<_, Strategy>(
        "UPDATE strategies
         SET name=$2, description=$3, signal_config=$4, trading_rules=$5, updated_at=NOW()
         WHERE id=$1
         RETURNING id, name, description, signal_config, trading_rules, active, created_at, updated_at",
    )
    .bind(id)
    .bind(&req.name)
    .bind(req.description.as_deref())
    .bind(&req.signal_config)
    .bind(&req.trading_rules)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(strategy))
}

pub async fn delete_strategy(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    auth_check(&headers)?;
    sqlx::query("DELETE FROM strategies WHERE id=$1")
        .bind(id)
        .execute(state.db.as_ref())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(StatusCode::NO_CONTENT)
}

pub async fn list_accounts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<Account>>, StatusCode> {
    auth_check(&headers)?;
    let accounts = sqlx::query_as::<_, Account>(
        "SELECT id, strategy_id, account_type,
                initial_capital::float8 as initial_capital,
                current_equity::float8 as current_equity,
                num_trades,
                win_rate::float8 as win_rate,
                sharpe_ratio::float8 as sharpe_ratio,
                cumulative_return::float8 as cumulative_return,
                created_at, updated_at
         FROM accounts ORDER BY created_at DESC",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("list_accounts: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(accounts))
}

pub async fn get_account(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Result<Json<Account>, StatusCode> {
    auth_check(&headers)?;
    let account = sqlx::query_as::<_, Account>(
        "SELECT id, strategy_id, account_type,
                initial_capital::float8 as initial_capital,
                current_equity::float8 as current_equity,
                num_trades,
                win_rate::float8 as win_rate,
                sharpe_ratio::float8 as sharpe_ratio,
                cumulative_return::float8 as cumulative_return,
                created_at, updated_at
         FROM accounts WHERE id = $1",
    )
    .bind(id)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(account))
}

pub async fn list_trades(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<Trade>>, StatusCode> {
    auth_check(&headers)?;
    let trades = sqlx::query_as::<_, Trade>(
        "SELECT id, account_id, strategy_id, trade_date, ticker,
                entry_price::float8 as entry_price,
                exit_price::float8 as exit_price,
                gap_pct::float8 as gap_pct,
                signal,
                gross_return_pct::float8 as gross_return_pct,
                net_return_pct::float8 as net_return_pct,
                pnl::float8 as pnl,
                position_size::float8 as position_size,
                status, created_at
         FROM trades ORDER BY created_at DESC LIMIT 500",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("list_trades: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(trades))
}

pub async fn get_trade(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Result<Json<Trade>, StatusCode> {
    auth_check(&headers)?;
    let trade = sqlx::query_as::<_, Trade>(
        "SELECT id, account_id, strategy_id, trade_date, ticker,
                entry_price::float8 as entry_price,
                exit_price::float8 as exit_price,
                gap_pct::float8 as gap_pct,
                signal,
                gross_return_pct::float8 as gross_return_pct,
                net_return_pct::float8 as net_return_pct,
                pnl::float8 as pnl,
                position_size::float8 as position_size,
                status, created_at
         FROM trades WHERE id = $1",
    )
    .bind(id)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|_| StatusCode::NOT_FOUND)?;
    Ok(Json(trade))
}

pub async fn get_performance(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<PerformanceMetrics>, StatusCode> {
    auth_check(&headers)?;
    let metrics = sqlx::query_as::<_, PerformanceMetrics>(
        "SELECT
            COUNT(*)::int4 as total_trades,
            COALESCE(
                (SUM(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END)::float8
                 / NULLIF(COUNT(*)::float8, 0.0)) * 100.0,
                0.0
            ) as win_rate,
            COALESCE(AVG(net_return_pct::float8), 0.0) as avg_return,
            COALESCE(
                CASE
                    WHEN STDDEV_SAMP(net_return_pct::float8) > 0
                    THEN (AVG(net_return_pct::float8) / STDDEV_SAMP(net_return_pct::float8)) * SQRT(252.0)
                    ELSE 0.0
                END,
                0.0
            ) as sharpe_ratio,
            COALESCE(SUM(net_return_pct::float8), 0.0) as cumulative_return
         FROM trades
         WHERE pnl IS NOT NULL",
    )
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("get_performance: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(metrics))
}

pub async fn get_strategy_performance(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(strategy_id): Path<Uuid>,
) -> Result<Json<PerformanceMetrics>, StatusCode> {
    auth_check(&headers)?;
    let metrics = sqlx::query_as::<_, PerformanceMetrics>(
        "SELECT
            COUNT(*)::int4 as total_trades,
            COALESCE(
                (SUM(CASE WHEN pnl > 0 THEN 1.0 ELSE 0.0 END)::float8
                 / NULLIF(COUNT(*)::float8, 0.0)) * 100.0,
                0.0
            ) as win_rate,
            COALESCE(AVG(net_return_pct::float8), 0.0) as avg_return,
            COALESCE(
                CASE
                    WHEN STDDEV_SAMP(net_return_pct::float8) > 0
                    THEN (AVG(net_return_pct::float8) / STDDEV_SAMP(net_return_pct::float8)) * SQRT(252.0)
                    ELSE 0.0
                END,
                0.0
            ) as sharpe_ratio,
            COALESCE(SUM(net_return_pct::float8), 0.0) as cumulative_return
         FROM trades
         WHERE strategy_id = $1 AND pnl IS NOT NULL",
    )
    .bind(strategy_id)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("get_strategy_performance: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(metrics))
}

pub async fn list_alerts(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<Alert>>, StatusCode> {
    auth_check(&headers)?;
    let alerts = sqlx::query_as::<_, Alert>(
        "SELECT id, strategy_id, alert_type, severity, message, acknowledged, created_at, acknowledged_at
         FROM alerts ORDER BY created_at DESC",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("list_alerts: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(alerts))
}

pub async fn acknowledge_alert(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<Uuid>,
) -> Result<StatusCode, StatusCode> {
    auth_check(&headers)?;
    sqlx::query("UPDATE alerts SET acknowledged=true, acknowledged_at=NOW() WHERE id=$1")
        .bind(id)
        .execute(state.db.as_ref())
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(StatusCode::OK)
}

pub async fn get_tax_report(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(year): Path<i32>,
) -> Result<Json<TaxReport>, StatusCode> {
    auth_check(&headers)?;

    #[derive(sqlx::FromRow)]
    struct TaxSummary {
        total_trades: i32,
        gross_pnl: f64,
        net_pnl: f64,
        tax_owed: f64,
    }

    let summary = sqlx::query_as::<_, TaxSummary>(
        "SELECT
            COUNT(*)::int4 as total_trades,
            COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END)::float8, 0.0) as gross_pnl,
            COALESCE(SUM(pnl)::float8, 0.0) as net_pnl,
            GREATEST(COALESCE(SUM(pnl)::float8, 0.0) * 0.20, 0.0) as tax_owed
         FROM trades
         WHERE EXTRACT(YEAR FROM created_at)::int4 = $1
         AND pnl IS NOT NULL",
    )
    .bind(year)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("get_tax_report: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(TaxReport {
        year,
        total_trades: summary.total_trades,
        gross_pnl: summary.gross_pnl,
        commissions: 0.0,
        net_pnl: summary.net_pnl,
        tax_owed: summary.tax_owed,
    }))
}

// ── Equity Curve ────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct EquityPoint {
    pub date: String,
    pub real: f64,
    pub simulated: f64,
}

pub async fn get_equity_curve(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<EquityPoint>>, StatusCode> {
    auth_check(&headers)?;

    // Get starting capitals from the first strategy's accounts
    #[derive(sqlx::FromRow)]
    struct StartCapital {
        real_start: f64,
        sim_start: f64,
    }

    let start = sqlx::query_as::<_, StartCapital>(
        "SELECT
            COALESCE(MAX(CASE WHEN account_type='real'      THEN initial_capital::float8 END), 1000.0)   as real_start,
            COALESCE(MAX(CASE WHEN account_type='simulated' THEN initial_capital::float8 END), 100000.0) as sim_start
         FROM accounts",
    )
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("equity_curve start: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // Running equity from cumulative daily PnL per account type
    let points = sqlx::query_as::<_, EquityPoint>(
        "WITH daily AS (
            SELECT
                t.trade_date as date,
                SUM(CASE WHEN a.account_type='real'      THEN COALESCE(t.pnl::float8, 0) ELSE 0 END) as real_pnl,
                SUM(CASE WHEN a.account_type='simulated' THEN COALESCE(t.pnl::float8, 0) ELSE 0 END) as sim_pnl
            FROM trades t
            JOIN accounts a ON a.id = t.account_id
            GROUP BY t.trade_date
        )
        SELECT
            date,
            $1::float8 + SUM(real_pnl) OVER (ORDER BY date) as real,
            $2::float8 + SUM(sim_pnl)  OVER (ORDER BY date) as simulated
        FROM daily
        ORDER BY date",
    )
    .bind(start.real_start)
    .bind(start.sim_start)
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("equity_curve points: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    // If no trades yet, return just the starting point
    if points.is_empty() {
        let today = chrono::Utc::now().format("%Y-%m-%d").to_string();
        return Ok(Json(vec![EquityPoint {
            date: today,
            real: start.real_start,
            simulated: start.sim_start,
        }]));
    }

    Ok(Json(points))
}

// ── Signals (posted by B3 collector) ────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct CreateSignalRequest {
    pub strategy_id: Option<Uuid>,
    pub ticker: String,
    pub signal_type: String,
    pub gap_pct: f64,
    pub prev_close: Option<f64>,
    pub open_price: Option<f64>,
    pub signal_date: String,
}

pub async fn create_signal(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<CreateSignalRequest>,
) -> Result<StatusCode, StatusCode> {
    auth_check(&headers)?;
    sqlx::query(
        "INSERT INTO signals (strategy_id, ticker, signal_type, gap_pct, prev_close, open_price, signal_date)
         VALUES ($1, $2, $3, $4, $5, $6, $7)",
    )
    .bind(req.strategy_id)
    .bind(&req.ticker)
    .bind(&req.signal_type)
    .bind(req.gap_pct)
    .bind(req.prev_close)
    .bind(req.open_price)
    .bind(&req.signal_date)
    .execute(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("create_signal: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(StatusCode::CREATED)
}

// ── Backtest bulk insert ─────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct BacktestTrade {
    pub strategy_id: Uuid,
    pub run_id: Option<Uuid>,
    pub ticker: String,
    pub signal_type: String,
    pub gap_pct: f64,
    pub prev_close: f64,
    pub open_price: f64,
    pub close_price: f64,
    pub signal_date: String,
    pub gross_return_pct: f64,
    pub net_return_pct: f64,
    pub pos_pct: f64,
    pub liquidity_cap_brl: Option<f64>,
    pub min_position_brl: Option<f64>,
}

#[derive(Debug, Serialize)]
pub struct BacktestResult {
    pub inserted: usize,
    pub skipped: usize,
}

pub async fn run_backtest(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(trades): Json<Vec<BacktestTrade>>,
) -> Result<Json<BacktestResult>, StatusCode> {
    auth_check(&headers)?;

    let mut inserted = 0usize;
    let mut skipped = 0usize;

    for t in &trades {
        // Backtest trades should only mutate simulated accounts, never real/live accounts.
        let accounts = sqlx::query_as::<_, (Uuid, String, f64)>(
            "SELECT id, account_type, current_equity::float8
             FROM accounts WHERE strategy_id = $1 AND account_type = 'simulated'",
        )
        .bind(t.strategy_id)
        .fetch_all(state.db.as_ref())
        .await
        .map_err(|e| {
            tracing::error!("backtest accounts: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

        if accounts.is_empty() {
            skipped += 1;
            continue;
        }

        for (account_id, _account_type, equity) in &accounts {
            let intended_position_size = equity * t.pos_pct / 100.0;
            let liquidity_cap_brl = t.liquidity_cap_brl.unwrap_or(UNBOUNDED_LIQUIDITY_CAP_BRL);
            let position_size = intended_position_size.min(liquidity_cap_brl);
            if position_size < t.min_position_brl.unwrap_or(500.0) {
                skipped += 1;
                continue;
            }
            let capacity_used_pct =
                if liquidity_cap_brl > 0.0 && liquidity_cap_brl < UNBOUNDED_LIQUIDITY_CAP_BRL {
                    position_size / liquidity_cap_brl * 100.0
                } else {
                    0.0
                };
            let pnl = position_size * t.net_return_pct / 100.0;
            let exit_price = t.open_price * (1.0 + t.net_return_pct / 100.0);

            sqlx::query(
                "INSERT INTO trades
                 (id, account_id, strategy_id, trade_date, ticker,
                  entry_price, exit_price, gap_pct, signal,
                  gross_return_pct, net_return_pct, pnl, position_size, status, source, backtest_run_id,
                  intended_position_size, liquidity_cap_brl, capacity_used_pct)
                 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'executed','backtest',$14,$15,$16,$17)
                 ON CONFLICT DO NOTHING",
            )
            .bind(Uuid::new_v4())
            .bind(account_id)
            .bind(t.strategy_id)
            .bind(&t.signal_date)
            .bind(&t.ticker)
            .bind(t.open_price)
            .bind(exit_price)
            .bind(t.gap_pct)
            .bind(&t.signal_type)
            .bind(t.gross_return_pct)
            .bind(t.net_return_pct)
            .bind(pnl)
            .bind(position_size)
            .bind(t.run_id)
            .bind(intended_position_size)
            .bind(liquidity_cap_brl)
            .bind(capacity_used_pct)
            .execute(state.db.as_ref())
            .await
            .map_err(|e| { tracing::error!("backtest insert: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

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
            .await
            .map_err(|e| {
                tracing::error!("backtest equity: {e}");
                StatusCode::INTERNAL_SERVER_ERROR
            })?;
        }

        inserted += 1;
    }

    // Update total_trades on any backtest_run referenced in this batch
    if let Some(run_id) = trades.iter().find_map(|t| t.run_id) {
        sqlx::query(
            "UPDATE backtest_runs SET total_trades = (
                SELECT COUNT(*)::int4 FROM trades WHERE backtest_run_id = $1
                AND account_id IN (SELECT id FROM accounts WHERE account_type = 'simulated')
            ) WHERE id = $1",
        )
        .bind(run_id)
        .execute(state.db.as_ref())
        .await
        .ok();
    }

    Ok(Json(BacktestResult { inserted, skipped }))
}

// ── Backtest analytics ───────────────────────────────────────────────────────

pub async fn get_backtest_summary(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BacktestSummary>>, StatusCode> {
    auth_check(&headers)?;
    let rows = sqlx::query_as::<_, BacktestSummary>(
        "SELECT
            t.strategy_id,
            s.name as strategy_name,
            COUNT(t.id)::int4 as total_trades,
            COALESCE(
                SUM(CASE WHEN t.pnl > 0 THEN 1.0 ELSE 0.0 END)::float8
                / NULLIF(COUNT(t.id)::float8, 0.0) * 100.0,
                0.0
            ) as win_rate,
            COALESCE(AVG(t.net_return_pct::float8), 0.0) as avg_return_pct,
            COALESCE(SUM(t.net_return_pct::float8), 0.0) as total_return_pct,
            COALESCE(MAX(t.net_return_pct::float8), 0.0) as best_trade_pct,
            COALESCE(MIN(t.net_return_pct::float8), 0.0) as worst_trade_pct,
            COALESCE(SUM(t.pnl::float8), 0.0) as total_pnl,
            COALESCE(
                CASE
                    WHEN STDDEV_SAMP(t.net_return_pct::float8) > 0
                    THEN AVG(t.net_return_pct::float8)
                         / STDDEV_SAMP(t.net_return_pct::float8)
                         * SQRT(252.0)
                    ELSE 0.0
                END,
                0.0
            ) as sharpe_ratio,
            MIN(t.trade_date) as first_trade_date,
            MAX(t.trade_date) as last_trade_date
         FROM trades t
         JOIN strategies s ON s.id = t.strategy_id
         JOIN accounts a ON a.id = t.account_id
         WHERE t.source = 'backtest'
           AND a.account_type = 'simulated'
         GROUP BY t.strategy_id, s.name
         ORDER BY s.name",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("get_backtest_summary: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(rows))
}

#[derive(Debug, Deserialize)]
pub struct BacktestTradesQuery {
    pub strategy_id: Option<Uuid>,
    pub run_id: Option<Uuid>,
    pub ticker: Option<String>,
    pub page: Option<i64>,
    pub per_page: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct BacktestTradesResponse {
    pub trades: Vec<BacktestTradeRow>,
    pub total: i64,
    pub page: i64,
    pub per_page: i64,
}

pub async fn get_backtest_trades(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(query): Query<BacktestTradesQuery>,
) -> Result<Json<BacktestTradesResponse>, StatusCode> {
    auth_check(&headers)?;

    let page = query.page.unwrap_or(1).max(1);
    let per_page = query.per_page.unwrap_or(50).min(200);
    let offset = (page - 1) * per_page;
    let ticker_like = query
        .ticker
        .as_deref()
        .map(|t| format!("%{}%", t.to_uppercase()))
        .unwrap_or_else(|| "%".to_string());

    let (total,): (i64,) = sqlx::query_as(
        "SELECT COUNT(t.id)::int8
         FROM trades t
         JOIN accounts a ON a.id = t.account_id
         WHERE t.source = 'backtest'
           AND a.account_type = 'simulated'
           AND ($1::UUID IS NULL OR t.strategy_id = $1)
           AND ($2::UUID IS NULL OR t.backtest_run_id = $2)
           AND UPPER(t.ticker) LIKE $3",
    )
    .bind(query.strategy_id)
    .bind(query.run_id)
    .bind(&ticker_like)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("backtest trades count: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let trades = sqlx::query_as::<_, BacktestTradeRow>(
        "SELECT
            t.id, t.strategy_id,
            s.name as strategy_name,
            t.trade_date, t.ticker,
            t.signal as signal_type,
            COALESCE(t.gap_pct::float8, 0.0)          as gap_pct,
            COALESCE(t.entry_price::float8, 0.0)       as entry_price,
            COALESCE(t.exit_price::float8, 0.0)        as exit_price,
            COALESCE(t.net_return_pct::float8, 0.0)    as net_return_pct,
            COALESCE(t.pnl::float8, 0.0)                    as pnl,
            COALESCE(t.position_size::float8, 0.0)          as position_size,
            COALESCE(t.intended_position_size::float8, 0.0) as intended_position_size,
            COALESCE(t.liquidity_cap_brl::float8, 0.0)      as liquidity_cap_brl,
            COALESCE(t.capacity_used_pct::float8, 0.0)      as capacity_used_pct,
            t.backtest_run_id
         FROM trades t
         JOIN strategies s ON s.id = t.strategy_id
         JOIN accounts a ON a.id = t.account_id
         WHERE t.source = 'backtest'
           AND a.account_type = 'simulated'
           AND ($1::UUID IS NULL OR t.strategy_id = $1)
           AND ($2::UUID IS NULL OR t.backtest_run_id = $2)
           AND UPPER(t.ticker) LIKE $3
         ORDER BY t.trade_date DESC, t.ticker
         LIMIT $4 OFFSET $5",
    )
    .bind(query.strategy_id)
    .bind(query.run_id)
    .bind(&ticker_like)
    .bind(per_page)
    .bind(offset)
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("backtest trades list: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(BacktestTradesResponse {
        trades,
        total,
        page,
        per_page,
    }))
}

#[derive(Debug, Serialize)]
pub struct BacktestStrategyCurve {
    pub strategy_id: Uuid,
    pub strategy_name: String,
    pub initial_capital: f64,
    pub curve: Vec<BacktestEquityPoint>,
}

#[derive(Debug, Serialize)]
pub struct BacktestEquityPoint {
    pub date: String,
    pub equity: f64,
}

#[derive(sqlx::FromRow)]
struct BacktestEquityRow {
    strategy_id: Uuid,
    strategy_name: String,
    date: String,
    equity: f64,
}

pub async fn get_backtest_equity_curves(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BacktestStrategyCurve>>, StatusCode> {
    auth_check(&headers)?;

    let rows = sqlx::query_as::<_, BacktestEquityRow>(
        "WITH initial_caps AS (
            SELECT strategy_id, COALESCE(MAX(initial_capital::float8), 100000.0) as cap
            FROM accounts
            WHERE account_type = 'simulated'
            GROUP BY strategy_id
         ),
         daily_pnl AS (
            SELECT t.strategy_id, t.trade_date as date,
                   SUM(COALESCE(t.pnl::float8, 0.0)) as daily_pnl
            FROM trades t
            JOIN accounts a ON a.id = t.account_id
            WHERE t.source = 'backtest' AND a.account_type = 'simulated'
            GROUP BY t.strategy_id, t.trade_date
         )
         SELECT dp.strategy_id,
                s.name as strategy_name,
                dp.date,
                ic.cap + SUM(dp.daily_pnl) OVER (PARTITION BY dp.strategy_id ORDER BY dp.date) as equity
         FROM daily_pnl dp
         JOIN initial_caps ic ON ic.strategy_id = dp.strategy_id
         JOIN strategies s ON s.id = dp.strategy_id
         ORDER BY dp.strategy_id, dp.date",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("backtest equity curves: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let caps: Vec<(Uuid, f64)> = sqlx::query_as(
        "SELECT strategy_id, COALESCE(initial_capital::float8, 100000.0) as cap
         FROM accounts WHERE account_type = 'simulated'",
    )
    .fetch_all(state.db.as_ref())
    .await
    .unwrap_or_default();
    let cap_map: std::collections::HashMap<Uuid, f64> = caps.into_iter().collect();

    let mut map: std::collections::HashMap<Uuid, (String, Vec<BacktestEquityPoint>)> =
        Default::default();
    for row in rows {
        let entry = map
            .entry(row.strategy_id)
            .or_insert((row.strategy_name, vec![]));
        entry.1.push(BacktestEquityPoint {
            date: row.date,
            equity: row.equity,
        });
    }

    let mut result: Vec<BacktestStrategyCurve> = map
        .into_iter()
        .map(|(id, (name, curve))| BacktestStrategyCurve {
            strategy_id: id,
            strategy_name: name,
            initial_capital: *cap_map.get(&id).unwrap_or(&100000.0),
            curve,
        })
        .collect();
    result.sort_by(|a, b| a.strategy_name.cmp(&b.strategy_name));

    Ok(Json(result))
}

// ── Backtest runs ────────────────────────────────────────────────────────────

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct BacktestRunSummary {
    pub id: Uuid,
    pub name: String,
    pub params: serde_json::Value,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub total_trades: i64,
    pub win_rate: f64,
    pub avg_return_pct: f64,
    pub total_pnl: f64,
}

pub async fn list_backtest_runs(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<Vec<BacktestRunSummary>>, StatusCode> {
    auth_check(&headers)?;
    let runs = sqlx::query_as::<_, BacktestRunSummary>(
        "SELECT
            r.id, r.name, r.params, r.created_at,
            COALESCE(ts.total_trades, 0)::int8  as total_trades,
            COALESCE(ts.win_rate, 0.0)          as win_rate,
            COALESCE(ts.avg_return_pct, 0.0)    as avg_return_pct,
            COALESCE(ts.total_pnl, 0.0)         as total_pnl
         FROM backtest_runs r
         LEFT JOIN (
             SELECT
                 t.backtest_run_id,
                 COUNT(t.id)::float8 as total_trades,
                 SUM(CASE WHEN t.pnl > 0 THEN 1.0 ELSE 0.0 END)
                     / NULLIF(COUNT(t.id)::float8, 0) * 100 as win_rate,
                 AVG(t.net_return_pct::float8)   as avg_return_pct,
                 SUM(t.pnl::float8)              as total_pnl
             FROM trades t
             JOIN accounts a ON a.id = t.account_id
             WHERE a.account_type = 'simulated'
               AND t.backtest_run_id IS NOT NULL
             GROUP BY t.backtest_run_id
         ) ts ON ts.backtest_run_id = r.id
         ORDER BY r.created_at DESC",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("list_backtest_runs: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(runs))
}

#[derive(Debug, Deserialize)]
pub struct CreateBacktestRunRequest {
    pub name: String,
    pub params: serde_json::Value,
}

pub async fn create_backtest_run(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<CreateBacktestRunRequest>,
) -> Result<Json<BacktestRun>, StatusCode> {
    auth_check(&headers)?;
    let run = sqlx::query_as::<_, BacktestRun>(
        "INSERT INTO backtest_runs (id, name, params)
         VALUES ($1, $2, $3)
         RETURNING id, name, params, total_trades, created_at",
    )
    .bind(Uuid::new_v4())
    .bind(&req.name)
    .bind(&req.params)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("create_backtest_run: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(run))
}

pub async fn list_signals(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth_check(&headers)?;
    #[derive(sqlx::FromRow, Serialize)]
    struct SignalRow {
        id: Uuid,
        strategy_id: Option<Uuid>,
        ticker: String,
        signal_type: String,
        gap_pct: f64,
        signal_date: String,
        executed: bool,
    }
    let rows = sqlx::query_as::<_, SignalRow>(
        "SELECT id, strategy_id, ticker, signal_type, gap_pct::float8 as gap_pct, signal_date, executed
         FROM signals ORDER BY created_at DESC LIMIT 100",
    )
    .fetch_all(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("list_signals: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;
    Ok(Json(serde_json::json!(rows)))
}

// ─── Backtest job status ───────────────────────────────────────────────────────

pub async fn get_backtest_job_status(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth_check(&headers)?;

    #[derive(Serialize, sqlx::FromRow)]
    struct JobRow {
        id: Uuid,
        status: String,
        total_trades: Option<i32>,
        started_at: Option<chrono::DateTime<chrono::Utc>>,
        completed_at: Option<chrono::DateTime<chrono::Utc>>,
        error_message: Option<String>,
        created_at: chrono::DateTime<chrono::Utc>,
    }

    let job: Option<JobRow> = sqlx::query_as(
        "SELECT id, status, total_trades, started_at, completed_at, error_message, created_at
         FROM backtest_jobs
         ORDER BY created_at DESC
         LIMIT 1",
    )
    .fetch_optional(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("get_backtest_job_status: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let trade_count: i64 =
        sqlx::query_scalar("SELECT COUNT(*) FROM trades WHERE source = 'backtest'")
            .fetch_one(state.db.as_ref())
            .await
            .unwrap_or(0);

    Ok(Json(serde_json::json!({
        "job": job,
        "total_backtest_trades": trade_count,
    })))
}

// ─── Trigger a manual backtest run ────────────────────────────────────────────

#[derive(Deserialize)]
pub struct TriggerBacktestRequest {
    pub years: Option<Vec<i32>>,
}

pub async fn trigger_backtest(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(req): Json<TriggerBacktestRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth_check(&headers)?;

    // Refuse if a job is already running
    let running: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM backtest_jobs WHERE status IN ('pending','running'))",
    )
    .fetch_one(state.db.as_ref())
    .await
    .unwrap_or(false);

    if running {
        return Ok(Json(serde_json::json!({
            "ok": false,
            "message": "A backtest job is already running"
        })));
    }

    let years = req.years.unwrap_or_else(|| {
        let y = chrono::Utc::now().naive_utc().date().year();
        vec![y - 1, y]
    });

    let job_id: Uuid = sqlx::query_scalar(
        "INSERT INTO backtest_jobs (status, years_run) VALUES ('pending', $1) RETURNING id",
    )
    .bind(&years)
    .fetch_one(state.db.as_ref())
    .await
    .map_err(|e| {
        tracing::error!("trigger_backtest insert job: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let pool = state.db.clone();
    tokio::spawn(async move {
        match crate::backtest_runner::run_for_years(pool.clone(), years, job_id).await {
            Ok(n) => tracing::info!(trades = n, "Manual backtest completed"),
            Err(e) => {
                tracing::error!("Manual backtest failed: {e}");
                let _ = sqlx::query(
                    "UPDATE backtest_jobs SET status='failed', completed_at=NOW(), error_message=$2 WHERE id=$1",
                )
                .bind(job_id)
                .bind(e.to_string())
                .execute(pool.as_ref())
                .await;
            }
        }
    });

    Ok(Json(serde_json::json!({
        "ok": true,
        "job_id": job_id,
        "message": "Backtest job started"
    })))
}

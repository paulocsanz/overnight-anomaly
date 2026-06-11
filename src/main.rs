pub mod accounts;
pub mod auth;
pub mod backtest_runner;
pub mod db;
pub mod models;
pub mod routes;
pub mod scheduler;
pub mod strategies;
pub mod utils;

use axum::{
    routing::{delete, get, post, put},
    Router,
};
use sqlx::postgres::PgPoolOptions;
use std::sync::Arc;
use tower_http::cors::CorsLayer;

#[derive(Clone)]
pub struct AppState {
    pub db: Arc<sqlx::PgPool>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://localhost/trading_saas".to_string());

    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect(&database_url)
        .await?;

    sqlx::query("SELECT 1").execute(&pool).await?;

    let state = AppState { db: Arc::new(pool) };

    // Run migrations
    sqlx::raw_sql(include_str!("../migrations/001_create_tables.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/002_seed_strategies.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/003_add_signals.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/004_add_trade_source.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/005_backtest_runs.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/006_activate_hvf.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/007_new_strategies.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/008_backtest_jobs.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!("../migrations/009_flip_extreme_gap_fade.sql"))
        .execute(state.db.as_ref())
        .await?;
    sqlx::raw_sql(include_str!(
        "../migrations/010_extreme_gap_liquidity_filters.sql"
    ))
    .execute(state.db.as_ref())
    .await?;
    sqlx::raw_sql(include_str!(
        "../migrations/011_liquidity_capacity_columns.sql"
    ))
    .execute(state.db.as_ref())
    .await?;

    // API Routes
    let app = Router::new()
        .route("/api/health", get(|| async { "OK" }))
        .route("/api/login", post(routes::login))
        // Strategies
        .route("/api/strategies", post(routes::create_strategy))
        .route("/api/strategies", get(routes::list_strategies))
        .route("/api/strategies/:id", get(routes::get_strategy))
        .route("/api/strategies/:id", put(routes::update_strategy))
        .route("/api/strategies/:id", delete(routes::delete_strategy))
        // Accounts
        .route("/api/accounts", get(routes::list_accounts))
        .route("/api/accounts/:id", get(routes::get_account))
        // Trades
        .route("/api/trades", get(routes::list_trades))
        .route("/api/trades/:id", get(routes::get_trade))
        // Performance
        .route("/api/performance", get(routes::get_performance))
        .route(
            "/api/performance/:strategy_id",
            get(routes::get_strategy_performance),
        )
        // Alerts
        .route("/api/alerts", get(routes::list_alerts))
        .route(
            "/api/alerts/:id/acknowledge",
            post(routes::acknowledge_alert),
        )
        // Tax
        .route("/api/tax-report/:year", get(routes::get_tax_report))
        // Equity curve
        .route("/api/equity-curve", get(routes::get_equity_curve))
        // Signals (from B3 collector)
        .route("/api/signals", post(routes::create_signal))
        .route("/api/signals", get(routes::list_signals))
        // Backtest
        .route("/api/backtest/run", post(routes::run_backtest))
        .route("/api/backtest/summary", get(routes::get_backtest_summary))
        .route("/api/backtest/trades", get(routes::get_backtest_trades))
        .route(
            "/api/backtest/equity-curves",
            get(routes::get_backtest_equity_curves),
        )
        .route("/api/backtest/runs", get(routes::list_backtest_runs))
        .route(
            "/api/backtest/create-run",
            post(routes::create_backtest_run),
        )
        .route(
            "/api/backtest/job-status",
            get(routes::get_backtest_job_status),
        )
        .route("/api/backtest/trigger", post(routes::trigger_backtest))
        .layer(CorsLayer::permissive())
        .with_state(state.clone());

    // Spawn scheduler
    tokio::spawn(scheduler::run_scheduler(state.clone()));

    // Auto-seed backtest data if any strategy has no backtest trades
    tokio::spawn(backtest_runner::auto_seed_if_needed(state.db.clone()));

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8000").await?;
    tracing::info!("listening on {}", listener.local_addr()?);

    axum::serve(listener, app).await?;

    Ok(())
}

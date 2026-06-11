use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Strategy {
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub signal_config: serde_json::Value,
    pub trading_rules: serde_json::Value,
    pub active: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Account {
    pub id: Uuid,
    pub strategy_id: Uuid,
    pub account_type: String,
    pub initial_capital: f64,
    pub current_equity: f64,
    pub num_trades: i32,
    pub win_rate: f64,
    pub sharpe_ratio: f64,
    pub cumulative_return: f64,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Trade {
    pub id: Uuid,
    pub account_id: Uuid,
    pub strategy_id: Uuid,
    pub trade_date: String,
    pub ticker: String,
    pub entry_price: f64,
    pub exit_price: f64,
    pub gap_pct: f64,
    pub signal: String,
    pub gross_return_pct: Option<f64>,
    pub net_return_pct: Option<f64>,
    pub pnl: Option<f64>,
    pub position_size: Option<f64>,
    pub status: String,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Alert {
    pub id: Uuid,
    pub strategy_id: Uuid,
    pub alert_type: String,
    pub severity: String,
    pub message: Option<String>,
    pub acknowledged: bool,
    pub created_at: DateTime<Utc>,
    pub acknowledged_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateStrategyRequest {
    pub name: String,
    pub description: Option<String>,
    pub signal_config: serde_json::Value,
    pub trading_rules: serde_json::Value,
}

#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct PerformanceMetrics {
    pub total_trades: i32,
    pub win_rate: f64,
    pub avg_return: f64,
    pub sharpe_ratio: f64,
    pub cumulative_return: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct BacktestRun {
    pub id: Uuid,
    pub name: String,
    pub params: serde_json::Value,
    pub total_trades: i32,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct BacktestSummary {
    pub strategy_id: Uuid,
    pub strategy_name: String,
    pub total_trades: i32,
    pub win_rate: f64,
    pub avg_return_pct: f64,
    pub total_return_pct: f64,
    pub best_trade_pct: f64,
    pub worst_trade_pct: f64,
    pub total_pnl: f64,
    pub sharpe_ratio: f64,
    pub first_trade_date: Option<String>,
    pub last_trade_date: Option<String>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct BacktestTradeRow {
    pub id: Uuid,
    pub strategy_id: Uuid,
    pub strategy_name: String,
    pub trade_date: String,
    pub ticker: String,
    pub signal_type: String,
    pub gap_pct: f64,
    pub entry_price: f64,
    pub exit_price: f64,
    pub net_return_pct: f64,
    pub pnl: f64,
    pub position_size: f64,
    pub intended_position_size: f64,
    pub liquidity_cap_brl: f64,
    pub capacity_used_pct: f64,
    pub backtest_run_id: Option<Uuid>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TaxReport {
    pub year: i32,
    pub total_trades: i32,
    pub gross_pnl: f64,
    pub commissions: f64,
    pub net_pnl: f64,
    pub tax_owed: f64,
}

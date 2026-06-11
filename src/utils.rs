use crate::models::Trade;

pub fn calculate_commission(pnl: f64, rate: f64) -> f64 {
    pnl.abs() * rate
}

pub fn calculate_tax(net_pnl: f64) -> f64 {
    if net_pnl > 0.0 {
        net_pnl * 0.20 // 20% day trading tax
    } else {
        0.0
    }
}

pub fn calculate_performance_metrics(trades: &[Trade]) -> (f64, f64, f64) {
    if trades.is_empty() {
        return (0.0, 0.0, 0.0);
    }

    let winning_trades = trades.iter().filter(|t| t.pnl.unwrap_or(0.0) > 0.0).count() as f64;
    let win_rate = (winning_trades / trades.len() as f64) * 100.0;

    let total_pnl: f64 = trades.iter().map(|t| t.pnl.unwrap_or(0.0)).sum();
    let avg_return = total_pnl / trades.len() as f64;

    // Simplified Sharpe ratio: avg_return / std_dev
    let variance: f64 = trades
        .iter()
        .map(|t| (t.pnl.unwrap_or(0.0) - avg_return).powi(2))
        .sum::<f64>()
        / trades.len() as f64;
    let std_dev = variance.sqrt();
    let sharpe_ratio = if std_dev > 0.0 {
        avg_return / std_dev
    } else {
        0.0
    };

    (win_rate, avg_return, sharpe_ratio)
}

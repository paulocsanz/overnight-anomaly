pub struct AccountManager {
    real_capital: f64,
    simulated_capital: f64,
}

impl AccountManager {
    pub fn new(real_capital: f64, simulated_capital: f64) -> Self {
        Self {
            real_capital,
            simulated_capital,
        }
    }

    pub fn auto_scale(&mut self, sharpe_ratio: f64, win_rate: f64) {
        // Auto-scale real capital if Sharpe > 1.0 AND win rate > 55%
        if sharpe_ratio > 1.0 && win_rate > 55.0 {
            self.real_capital *= 2.0;
        }
    }

    pub fn get_real_capital(&self) -> f64 {
        self.real_capital
    }

    pub fn get_simulated_capital(&self) -> f64 {
        self.simulated_capital
    }

    pub fn calculate_position_size(&self, capital: f64, risk_pct: f64) -> f64 {
        capital * (risk_pct / 100.0)
    }
}

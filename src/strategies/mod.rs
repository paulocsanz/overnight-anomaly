use async_trait::async_trait;

#[async_trait]
pub trait Strategy: Send + Sync {
    async fn evaluate(&self, ticker: &str, gap_pct: f64) -> Option<Signal>;
    fn name(&self) -> &str;
}

#[derive(Clone, Debug)]
pub enum Signal {
    Long,
    Short,
}

pub struct GapReversal {
    long_threshold: f64,
    short_threshold: f64,
}

impl Default for GapReversal {
    fn default() -> Self {
        Self::new()
    }
}

impl GapReversal {
    pub fn new() -> Self {
        Self {
            long_threshold: -2.0,
            short_threshold: 2.0,
        }
    }
}

#[async_trait]
impl Strategy for GapReversal {
    async fn evaluate(&self, _ticker: &str, gap_pct: f64) -> Option<Signal> {
        if gap_pct > self.short_threshold {
            Some(Signal::Short)
        } else if gap_pct < self.long_threshold {
            Some(Signal::Long)
        } else {
            None
        }
    }

    fn name(&self) -> &str {
        "gap_reversal"
    }
}

pub struct Momentum;

#[async_trait]
impl Strategy for Momentum {
    async fn evaluate(&self, _ticker: &str, _gap_pct: f64) -> Option<Signal> {
        None
    }

    fn name(&self) -> &str {
        "momentum"
    }
}

pub struct Volatility;

#[async_trait]
impl Strategy for Volatility {
    async fn evaluate(&self, _ticker: &str, _gap_pct: f64) -> Option<Signal> {
        None
    }

    fn name(&self) -> &str {
        "volatility"
    }
}

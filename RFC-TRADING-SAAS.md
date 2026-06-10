# RFC: Trading Strategy SaaS Platform

**Status:** Proposed  
**Date:** 2026-06-09  
**Author:** Paulo  
**Revision:** 1.0

---

## 1. Executive Summary

Build an automated trading strategy management platform that:
- Registers and manages multiple trading strategies (gap reversal, momentum, volatility, etc.)
- Automatically executes daily trading logic on B3 market data
- Tracks both real (R$1k minimum) and simulated (R$100k) accounts in parallel
- Auto-scales real capital based on strategy performance metrics
- Provides real-time dashboard monitoring
- Handles tax reporting and record-keeping
- Deploys on Railway with PostgreSQL backend

**Goal:** Reduce manual work from 5min/day (running scripts) to ~1min/day (monitoring dashboard)

---

## 2. Problem Statement

Current system requires:
- ❌ Manual daily execution: `python live_trader.py`
- ❌ Manual daily monitoring: `python trading_dashboard.py`
- ❌ Single strategy only (gap reversal)
- ❌ Manual account scaling decisions
- ❌ Manual tax record tracking
- ❌ No API for integration with brokers

**Desired state:**
- ✅ Fully automated daily execution
- ✅ Multi-strategy support (5-10+ strategies running in parallel)
- ✅ Single dashboard showing all strategies
- ✅ Auto-scaling based on predefined rules
- ✅ Centralized tax record keeping
- ✅ API for future broker integration
- ✅ Web-based access (no terminal needed)

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│           Railway Deployment Environment             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐  ┌──────────────┐               │
│  │  FastAPI     │  │  PostgreSQL  │               │
│  │  Backend     │  │  Database    │               │
│  │  (Port 8000) │  │              │               │
│  └──────────────┘  └──────────────┘               │
│        ▲                   ▲                        │
│        │                   │                        │
│  ┌─────┴───────────────────┴─────┐               │
│  │   APScheduler (Daily Jobs)    │               │
│  │  • 10am: Execute all strategies                │
│  │  • 5pm: Process closes & logs                  │
│  │  • Midnight: Daily reports                    │
│  └───────────────────────────────┘               │
│                                                     │
│  ┌─────────────────────────────┐                 │
│  │  Static Dashboard (React)    │                 │
│  │  • Strategy list & metrics   │                 │
│  │  • Real-time account values  │                 │
│  │  • Performance charts        │                 │
│  │  • Tax reports              │                 │
│  └─────────────────────────────┘                 │
│                                                     │
└─────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌──────────────────────┐  ┌──────────────────────┐
│ B3 Market Data       │  │ Broker APIs          │
│ (via Collector)      │  │ (Manual for now)     │
│ /data/b3_lake/       │  │ (Future: automated)  │
└──────────────────────┘  └──────────────────────┘
```

---

## 4. Core Components

### 4.1 Backend API (Axum)
**File:** `src/main.rs`

**Endpoints:**
```
POST   /api/strategies          - Register new strategy
GET    /api/strategies          - List all strategies
GET    /api/strategies/{id}     - Get strategy details
PUT    /api/strategies/{id}     - Update strategy config
DELETE /api/strategies/{id}     - Archive strategy

GET    /api/accounts            - List all accounts (real + sim)
GET    /api/accounts/{id}       - Get account state
GET    /api/accounts/{id}/history - Historical equity curve

GET    /api/trades              - List all trades (filtered)
GET    /api/trades/{id}         - Trade details

GET    /api/performance         - Aggregated stats (all strategies)
GET    /api/performance/{strategy_id} - Strategy-specific stats

GET    /api/alerts              - Strategy alerts (degradation, wins, etc.)
POST   /api/alerts/{id}/acknowledge - Mark alert as read

GET    /api/tax-report/{year}   - Annual tax summary
```

### 4.2 Database Schema (PostgreSQL)
**File:** `trading_saas/db/models.py`

**Tables:**
```sql
-- Strategies (template definitions)
strategies
├── id (UUID)
├── name (str: "gap_reversal", "momentum", etc.)
├── description (str)
├── signal_config (JSON: {min_gap: 2.0, liquidity_filter: ["INEP4", "MGEL4"]})
├── trading_rules (JSON: {position_size_pct: 0.01, max_positions: 10})
├── active (bool)
├── created_at
├── updated_at

-- Accounts (real + simulated per strategy)
accounts
├── id (UUID)
├── strategy_id (FK → strategies)
├── account_type (enum: "real", "simulated")
├── initial_capital (float: 1000 or 100000)
├── current_equity (float)
├── num_trades (int)
├── win_rate (float: 0-100)
├── sharpe_ratio (float)
├── cumulative_return (float: -100 to +inf)
├── created_at
├── updated_at

-- Trades (every buy/sell)
trades
├── id (UUID)
├── account_id (FK → accounts)
├── strategy_id (FK → strategies)
├── trade_date (date)
├── ticker (str)
├── entry_price (float)
├── exit_price (float)
├── gap_pct (float)
├── signal (enum: "LONG", "SHORT")
├── gross_return_pct (float)
├── net_return_pct (float: after commission & tax)
├── pnl (float: in R$)
├── position_size (float: R$)
├── status (enum: "executed", "pending", "failed")
├── created_at

-- Strategy Performance Cache
performance_cache
├── id (UUID)
├── strategy_id (FK → strategies)
├── date (date)
├── total_trades (int)
├── win_rate (float)
├── avg_return (float)
├── sharpe_ratio (float)
├── max_drawdown (float)
├── cumulative_return (float)
├── created_at

-- Alerts
alerts
├── id (UUID)
├── strategy_id (FK → strategies)
├── alert_type (enum: "win_rate_drop", "sharpe_degradation", "gap_shrinking")
├── severity (enum: "info", "warning", "critical")
├── message (str)
├── acknowledged (bool)
├── created_at
├── acknowledged_at

-- Tax Records
tax_records
├── id (UUID)
├── year (int)
├── total_trades (int)
├── gross_pnl (float)
├── commissions (float)
├── net_pnl (float)
├── tax_owed (float: 20% of net)
├── notes (str)
├── created_at
```

### 4.3 Scheduler (APScheduler)
**File:** `trading_saas/scheduler/jobs.py`

**Daily Jobs:**
```python
# 10:00 AM (before market open)
@scheduled_job('cron', hour=10, minute=0)
def execute_all_strategies():
    """
    For each active strategy:
    1. Load latest market data from /data/b3_lake/
    2. Generate signals
    3. Execute trades on both real & simulated accounts
    4. Log results
    """

# 5:15 PM (after market close)
@scheduled_job('cron', hour=17, minute=15)
def close_and_log_daily():
    """
    1. Close all open positions
    2. Calculate daily P&L
    3. Update account equity
    4. Log trades to database
    5. Check for alerts (win rate drop, sharpe degradation)
    6. Update performance cache
    """

# 12:00 AM (midnight)
@scheduled_job('cron', hour=0, minute=0)
def generate_daily_reports():
    """
    1. Aggregate all strategy performance
    2. Generate individual strategy reports
    3. Check auto-scaling rules
    4. Create tax records for the day
    5. Notify user of alerts
    """
```

### 4.4 Strategy Registry
**File:** `trading_saas/strategies/registry.py`

**Each strategy must implement:**
```python
class TradingStrategy(ABC):
    name: str
    description: str
    config: dict  # min_gap, liquidity_filters, etc.
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        """Load market data, return list of {ticker, signal, gap_pct}"""
        pass
    
    @abstractmethod
    def validate_config(self, config: dict) -> bool:
        """Check config is valid"""
        pass

class GapReversalStrategy(TradingStrategy):
    # Short gaps > 2%, long gaps < -2%
    
class MomentumStrategy(TradingStrategy):
    # Long stocks that moved +2%, short that moved -2%
    
class VolatilityStrategy(TradingStrategy):
    # Trade vol mean reversion
```

### 4.5 Account Management
**File:** `trading_saas/accounts/manager.py`

**Auto-scaling Rules:**
```python
def check_auto_scaling(real_account: Account, simulated_account: Account) -> bool:
    """
    Scale up if:
      ✓ sharpe_ratio > 1.0 AND
      ✓ win_rate > 55% AND
      ✓ total_trades >= 20
    
    Scale multiplier: 2x (double the real capital)
    """
```

### 4.6 Dashboard (React/Vue)
**File:** `trading_saas/frontend/dashboard.html`

**Pages:**
```
1. Home / Overview
   ├── Total capital: R$1,000 real + R$100,000 simulated
   ├── Total P&L: +R$500 (50%)
   ├── Active strategies: 3
   ├── Today's trades: 7
   └── Alerts: 1 (gap frequency declining)

2. Strategies
   ├── List all strategies
   │  └── Gap Reversal
   │      ├── Status: ACTIVE
   │      ├── Real account: R$1,100 (+10%)
   │      ├── Simulated: R$110,000 (+10%)
   │      ├── Win rate: 58%
   │      ├── Sharpe: 1.2
   │      └── Last trade: INEP4 2h ago
   │
   └── Add new strategy (form)

3. Accounts
   ├── Real Account
   │  ├── Capital: R$1,000
   │  ├── Equity: R$1,100
   │  ├── Trades: 20
   │  ├── Return: +10%
   │  └── Auto-scale status: Ready (Sharpe>1, Win%>55%)
   │
   └── Simulated Account
      ├── Capital: R$100,000
      ├── Equity: R$110,000
      ├── Trades: 20
      ├── Return: +10%
      └── Equity curve chart

4. Trades
   ├── Filter by strategy, date, status
   ├── Recent trades table
   │  ├── Date | Ticker | Strategy | Entry | Exit | P&L | Status
   │  ├── 2026-06-09 | INEP4 | Gap Rev. | 5.50 | 5.65 | +2.7% | ✓
   │  └── ...
   └── Export trades (CSV)

5. Performance
   ├── Strategy comparison table
   │  ├── Strategy | Trades | Win% | Sharpe | Return
   │  ├── Gap Reversal | 20 | 58% | 1.2 | +10%
   │  └── ...
   ├── Equity curve (all strategies)
   ├── Monthly returns chart
   └── Drawdown analysis

6. Tax Reports
   ├── 2024 Tax Summary
   │  ├── Total trades: 150
   │  ├── Gross P&L: R$15,000
   │  ├── Commissions: -R$500
   │  ├── Net P&L: R$14,500
   │  ├── Tax owed: R$2,900 (20%)
   │  └── Download IRPF form (prefilled)
   └── Export tax records (CSV)

7. Settings
   ├── Auto-scaling rules (Sharpe threshold, win rate threshold)
   ├── Notification preferences
   ├── Data export
   └── Database backup
```

---

## 5. Data Flow

### Daily Execution Flow
```
10:00 AM: Scheduler triggers execute_all_strategies()
    ↓
Load market data from /data/b3_lake/ (via collector)
    ↓
For each active strategy:
    ├─ Generate signals (e.g., gaps > 2%)
    ├─ For each signal:
    │   ├─ Execute on REAL account (1% position size, R$10 at R$1k)
    │   ├─ Execute on SIMULATED account (1% position size, R$1k at R$100k)
    │   └─ Log trade to database
    └─ Update account metrics (win rate, sharpe, cumulative return)
    ↓
5:15 PM: Close all open positions
    ├─ Calculate daily P&L
    ├─ Update account equity
    ├─ Check for alerts (win rate drop, etc.)
    └─ Create database records
    ↓
12:00 AM: Generate daily reports
    ├─ Aggregate performance across all strategies
    ├─ Check auto-scaling conditions
    ├─ Create tax records
    └─ Send alerts to user
```

---

## 6. Deployment Architecture

### 6.1 Railway Services
```
1. PostgreSQL Database
   ├── Version: 14+
   ├── Storage: 10GB (auto-expand)
   └── Backups: Daily

2. Rust/Axum Backend
   ├── Rust 1.75+
   ├── Port: 8000
   ├── Build: cargo build --release
   └── Restart policy: always

3. APScheduler (background worker - same Rust service)
   ├── Database: PostgreSQL
   ├── Job store: PostgreSQL
   └── Executor: Tokio runtime (async)

4. React Frontend (Static)
   ├── Build: npm run build
   ├── Serve: Railway static service
   ├── Port: 3000
   └── Cache: 1 hour
```

### 6.2 Docker Setup
```dockerfile
# Dockerfile
FROM rust:1.75-slim as builder

WORKDIR /app

# Copy manifest
COPY Cargo.toml Cargo.lock ./

# Copy source
COPY src/ ./src/

# Build release binary
RUN cargo build --release

# Runtime stage
FROM debian:bookworm-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y libpq5

# Copy binary from builder
COPY --from=builder /app/target/release/trading-saas ./

# Expose port
EXPOSE 8000

# Run the app
CMD ["./trading-saas"]
```

### 6.3 Railway Configuration
```yaml
# railway.toml
[build]
builder = "dockerfile"

[deploy]
numReplicas = 1
startCommand = "./trading-saas"

[env]
ENVIRONMENT = "production"
DATABASE_URL = "${{ POSTGRES_URL }}"
B3_DATA_DIR = "/data/b3_lake"
RUST_LOG = "info"
```

---

## 7. File Structure

```
trading-saas/
├── Cargo.toml                 # Rust project manifest
├── Cargo.lock
├── Dockerfile
├── railway.toml
├── .env.example
│
├── src/
│   ├── main.rs                # Axum app entry + route setup
│   │
│   ├── routes/
│   │   ├── strategies.rs      # /api/strategies/*
│   │   ├── accounts.rs        # /api/accounts/*
│   │   ├── trades.rs          # /api/trades/*
│   │   ├── performance.rs     # /api/performance/*
│   │   ├── alerts.rs          # /api/alerts/*
│   │   └── tax.rs             # /api/tax-report/*
│   │
│   ├── db/
│   │   ├── models.rs          # SQLx models
│   │   ├── schema.rs          # Schema definitions
│   │   └── migrations/        # SQL migrations
│   │       ├── 001_create_tables.sql
│   │       └── 002_create_indices.sql
│   │
│   ├── strategies/
│   │   ├── mod.rs             # Strategy trait + registry
│   │   ├── gap_reversal.rs    # Gap reversal implementation
│   │   ├── momentum.rs        # Momentum implementation
│   │   └── volatility.rs      # Volatility implementation
│   │
│   ├── accounts/
│   │   ├── manager.rs         # Account creation, scaling
│   │   └── calculator.rs      # P&L, Sharpe, win rate
│   │
│   ├── scheduler/
│   │   ├── jobs.rs            # Scheduled tasks
│   │   └── runner.rs          # Job executor (Tokio)
│   │
│   ├── market/
│   │   └── loader.rs          # Load B3 data from /data/b3_lake
│   │
│   ├── utils/
│   │   ├── taxes.rs           # Tax calculations
│   │   ├── alerts.rs          # Alert generation
│   │   └── error.rs           # Error handling
│   │
│   ├── config.rs              # Configuration loader
│   └── state.rs               # App state (DB pool, etc.)
│
├── frontend/                   # React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── KPICard.tsx
│   │   │   ├── StrategyCard.tsx
│   │   │   ├── TradesTable.tsx
│   │   │   ├── EquityCurveChart.tsx
│   │   │   ├── StrategyForm.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Panel.tsx
│   │   │
│   │   ├── pages/
│   │   │   ├── Home.tsx
│   │   │   ├── Strategies.tsx
│   │   │   ├── Accounts.tsx
│   │   │   ├── Trades.tsx
│   │   │   ├── Performance.tsx
│   │   │   └── Tax.tsx
│   │   │
│   │   ├── api/
│   │   │   └── client.ts      # API client
│   │   │
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   │
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
└── tests/
    ├── strategies_test.rs
    ├── accounts_test.rs
    └── api_test.rs
```

---

## 8. Implementation Phases

### Phase 1: Core Backend (Week 1)
```
✓ FastAPI setup + routes skeleton
✓ PostgreSQL models
✓ Strategy base class + Gap Reversal implementation
✓ Account manager (creation, scaling logic)
✓ Basic API endpoints (no auth yet)
```

### Phase 2: Scheduler & Automation (Week 1-2)
```
✓ APScheduler integration
✓ Daily job: execute_all_strategies()
✓ Daily job: close_and_log_daily()
✓ Daily job: generate_daily_reports()
✓ Trade logging to database
```

### Phase 3: Dashboard (Week 2)
```
✓ Simple HTML dashboard (no build process)
✓ Real-time API calls via JavaScript
✓ Strategy list + account views
✓ Trade history table
✓ Performance charts
```

### Phase 4: Deployment (Week 2)
```
✓ Docker setup
✓ Railway database provisioning
✓ Railway service deployment
✓ Test live execution
```

### Phase 5: Additional Strategies (Ongoing)
```
✓ Momentum strategy
✓ Volatility strategy
✓ Any custom strategies user defines
```

---

## 9. API Examples

### Register a Strategy
```bash
curl -X POST http://localhost:8000/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gap_reversal",
    "description": "Short gaps > 2%, long gaps < -2%",
    "signal_config": {
      "min_gap_pct": 2.0,
      "liquidity_filter": ["INEP4", "MGEL4", "TELB3"]
    },
    "trading_rules": {
      "position_size_pct": 0.01,
      "max_positions": 10
    }
  }'
```

### Get Strategy Performance
```bash
curl http://localhost:8000/api/performance/gap-reversal-uuid
```

Response:
```json
{
  "strategy_id": "abc-123",
  "real_account": {
    "capital": 1000,
    "equity": 1100,
    "return_pct": 10.0,
    "win_rate": 58.0,
    "sharpe_ratio": 1.2
  },
  "simulated_account": {
    "capital": 100000,
    "equity": 110000,
    "return_pct": 10.0,
    "win_rate": 58.0,
    "sharpe_ratio": 1.2
  }
}
```

---

## 10. Success Metrics

### During Development
- ✅ API fully functional (tested)
- ✅ Scheduler runs jobs on time
- ✅ Database stores all trades correctly
- ✅ Dashboard loads in < 2 seconds

### Post-Launch
- ✅ Gap reversal strategy executes daily (no manual intervention)
- ✅ Real account scales from R$1k → R$100k over 6-12 months
- ✅ Tax reports auto-generated (no manual compilation)
- ✅ Can add new strategies via API (no code changes)
- ✅ Support 10+ strategies running in parallel

---

## 11. Known Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Market data delay | Cache in database, 15min refresh |
| Strategy fails to execute | Retry logic, alerts on failure |
| Database connection lost | Reconnect with exponential backoff |
| Auto-scale at wrong time | Require manual approval (can be automated later) |
| Data loss | Daily PostgreSQL backups on Railway |
| Broker integration missing | Manual trading initially, API ready for later |

---

## 12. Future Enhancements (Not MVP)

```
Phase 2 (Month 2-3):
  ☐ User authentication (login)
  ☐ Multi-user support
  ☐ Broker API integration (automated order placement)
  ☐ Email notifications
  ☐ Mobile app

Phase 3 (Month 4+):
  ☐ ML-based strategy optimization
  ☐ Backtesting UI
  ☐ Live trading simulator (paper trading)
  ☐ Portfolio optimization
  ☐ Risk management (stops, hedging)
```

---

## 13. Approval & Sign-Off

**Build Decision:** Go/No-go?

- [ ] Approved: Build full SaaS on Railway
- [ ] Approved: Build MVP backend only (manual dashboard)
- [ ] Approved: Different approach (specify)

**Estimated Effort:** 40-60 hours (4-6 business days)

**Ready to begin:** Y/N

---

**End of RFC**

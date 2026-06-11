# Trading SaaS Platform

A complete SaaS platform for automated trading strategy management on B3 (Brazilian stock exchange).

## Features

- **Multi-Strategy Support**: Register and run multiple trading strategies in parallel
- **Dual-Account System**: Track both real (R$1k) and simulated (R$100k) accounts per strategy
- **Auto-Scaling**: Automatically double real capital when Sharpe > 1.0 AND win rate > 55%
- **Performance Monitoring**: Real-time dashboard with equity curves, metrics, and analytics
- **Tax Reporting**: Integrated tax calculation and Brazilian compliance tracking
- **Scheduler**: Automated 3-job daily cycle (10am execute, 5:15pm close, midnight report)

## Tech Stack

- **Backend**: Rust + Axum + SQLx (Tokio async)
- **Frontend**: React 18 + TypeScript + Tailwind CSS + Recharts
- **Database**: PostgreSQL
- **Deployment**: Docker + Railway

## Quick Start

### Prerequisites

- Rust 1.75+
- Node.js 20+
- PostgreSQL 16+
- Docker & Docker Compose (optional)

### Development

#### Using Docker Compose

```bash
docker-compose up
```

Backend: http://localhost:8000
Frontend: http://localhost:3000

#### Manual Setup

1. **Backend**
   ```bash
   export DATABASE_URL="postgres://localhost/trading_saas"
   cargo build
   cargo run
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Production

1. **Build Docker Image**
   ```bash
   docker build -t trading-saas .
   docker run -e DATABASE_URL=postgres://... -p 8000:8000 trading-saas
   ```

2. **Deploy to Railway**
   ```bash
   railway login
   railway init
   railway up
   ```

## API Endpoints

### Strategies
- `POST /api/strategies` - Create new strategy
- `GET /api/strategies` - List all strategies
- `GET /api/strategies/:id` - Get strategy details
- `PUT /api/strategies/:id` - Update strategy
- `DELETE /api/strategies/:id` - Delete strategy

### Accounts
- `GET /api/accounts` - List accounts
- `GET /api/accounts/:id` - Get account details

### Trades
- `GET /api/trades` - List all trades
- `GET /api/trades/:id` - Get trade details

### Performance
- `GET /api/performance` - Get overall performance metrics
- `GET /api/performance/:strategy_id` - Get strategy-specific metrics

### Alerts
- `GET /api/alerts` - List alerts
- `POST /api/alerts/:id/acknowledge` - Acknowledge alert

### Tax
- `GET /api/tax-report/:year` - Get tax report for year

## Database Schema

### Strategies
```
id, name, description, signal_config (JSON), trading_rules (JSON), active, created_at, updated_at
```

### Accounts
```
id, strategy_id, account_type (real/simulated), initial_capital, current_equity, 
num_trades, win_rate, sharpe_ratio, cumulative_return, created_at, updated_at
```

### Trades
```
id, account_id, strategy_id, trade_date, ticker, entry_price, exit_price, 
gap_pct, signal, gross_return_pct, net_return_pct, pnl, position_size, status, created_at
```

### Alerts
```
id, strategy_id, alert_type, severity, message, acknowledged, created_at, acknowledged_at
```

### Tax Records
```
id, strategy_id, year, total_trades, gross_pnl, commissions, net_pnl, tax_owed, created_at
```

## Configuration

### Environment Variables

```bash
# Backend
DATABASE_URL=postgres://user:password@localhost/trading_saas
RUST_LOG=info

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

## Architecture

### Scheduler Jobs
- **10:00 AM**: Execute trades based on gap reversal signals
- **5:15 PM**: Close all positions before market close
- **12:00 AM**: Generate performance report and update tax records

### Strategy System
Pluggable strategy trait allows easy implementation of new trading theories:
- Gap Reversal (default)
- Momentum
- Volatility
- Custom strategies

## Tax & Compliance

- **Day Trading Tax**: 20% on net profits
- **Reporting**: IRPF (Federal Income Tax Return) annual filing
- **Record Keeping**: Maintain all trade confirmations for 5+ years
- **Brokers**: Works with Clear, Agora, XP (0.02-0.05% commissions)

## Performance Notes

- Gap reversal frequency: 7.6% of trading days (down from 25% historically)
- Best performers: INEP4, MGEL4, TELB3, MULT3 (2%+ gaps)
- Real account target: 0.15-0.25% daily edge
- Auto-scale at Sharpe > 1.0 & win rate > 55%

## Development

### Code Style
- Rust: `cargo fmt`
- TypeScript/React: `npm run lint && npm run type-check`

### Testing
```bash
cargo test
cd frontend && npm test
```

## Deployment

See `railway.toml` for Railway configuration. App exposes:
- API on port 8000
- Health check at `/api/health`
- Frontend served from `/public`

## License

Proprietary - Trading Strategy Platform

## Support

Contact: paulo@railway.com

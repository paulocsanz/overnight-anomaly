# Trading SaaS - Quick Start Guide

## 🚀 Deploy to Railway in 2 Minutes

### Option 1: GitHub Integration (Recommended)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial trading-saas commit"
   git remote add origin https://github.com/yourusername/trading-saas
   git push -u origin main
   ```

2. **Create Railway Project**
   - Go to https://railway.app
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `trading-saas` repository
   - Click "Deploy"

3. **Configure Environment**
   - Railway will auto-detect `railway.toml`
   - In Project Settings → Variables
   - Add PostgreSQL plugin (Railway will auto-setup)
   - Set `DATABASE_URL` to the PostgreSQL connection string

4. **Deploy**
   - Push to main branch → Auto-deploys
   - Your app is live at `https://your-project.railway.app`

### Option 2: Direct Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login to Railway
railway login

# Create new project
railway init

# Link PostgreSQL
railway add -d postgresql

# Deploy
railway up
```

## 💻 Local Development

### Prerequisites
- Rust 1.75+ (`rustup update`)
- Node.js 20+ (`brew install node`)
- PostgreSQL 16+ (`brew install postgresql`)

### Quick Setup

```bash
# 1. Start PostgreSQL
brew services start postgresql

# 2. Create database
createdb trading_saas

# 3. Set environment
export DATABASE_URL="postgres://localhost/trading_saas"

# 4. Run backend
cargo run

# 5. In another terminal, run frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:3000 and http://localhost:8000 in browser.

### Or with Docker Compose

```bash
docker-compose up
```

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Database: localhost:5432

## 📊 Testing the Platform

### Create a Strategy
```bash
curl -X POST http://localhost:8000/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gap Reversal",
    "description": "Short gaps > 2%, long gaps < -2%",
    "signal_config": {"type": "gap_reversal"},
    "trading_rules": {"risk_per_trade": 1.0}
  }'
```

### Check Health
```bash
curl http://localhost:8000/api/health
```

### View Dashboard
Visit http://localhost:3000 to see:
- Real-time equity curves
- Performance metrics
- Trade history
- Tax compliance tracking

## 🔧 Troubleshooting

### PostgreSQL Connection Error
```bash
# Check if PostgreSQL is running
psql postgres -c "SELECT version();"

# Or start it
brew services start postgresql
```

### Port Already in Use
```bash
# Backend uses 8000
lsof -i :8000

# Frontend uses 3000
lsof -i :3000
```

### Dependencies Installation Failed
```bash
# Clean and rebuild
cargo clean
npm install --legacy-peer-deps
```

### TypeScript Errors
```bash
cd frontend
npm run type-check
```

## 📝 Environment Variables

Create a `.env` file in the root:
```bash
DATABASE_URL=postgres://user:password@localhost/trading_saas
RUST_LOG=info
```

For development:
```bash
export DATABASE_URL="postgres://localhost/trading_saas"
export RUST_LOG=info
```

## 🚀 Deployment Checklist

- [ ] Database migrations applied
- [ ] Backend builds without warnings (`cargo build --release`)
- [ ] Frontend passes type-check (`npm run type-check`)
- [ ] Frontend passes lint (`npm run lint`)
- [ ] Docker image builds successfully
- [ ] PostgreSQL connection configured
- [ ] Environment variables set in Railway
- [ ] Health check endpoint responding

## 📊 API Overview

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/strategies` | GET/POST | List/create strategies |
| `/api/accounts` | GET | List accounts |
| `/api/trades` | GET | List trades |
| `/api/performance` | GET | Overall metrics |
| `/api/alerts` | GET | List alerts |
| `/api/tax-report/:year` | GET | Tax compliance |

## 🎨 Frontend Pages

- **Home**: Dashboard with equity curves and key metrics
- **Strategies**: Create, edit, manage trading strategies
- **Trades**: View all executed trades and history
- **Performance**: Charts and detailed performance analytics
- **Tax Reports**: Annual compliance and tax calculations

## 🔐 Security Notes

- Keep `.env` out of Git (included in `.gitignore`)
- Use environment variables for secrets
- Database passwords should be strong
- CORS is configured for all origins (change in production)
- No authentication implemented yet (add before production)

## 📚 Documentation

- `README.md` - Full documentation
- `IMPLEMENTATION_SUMMARY.md` - Architecture overview
- `RFC-TRADING-SAAS.md` - Backend specification
- `RFC-FRONTEND.md` - Frontend specification

## 🆘 Getting Help

1. Check logs: `railway logs`
2. View metrics: Railway dashboard
3. Database admin: `psql trading_saas`
4. Backend debug: `RUST_LOG=debug cargo run`

## ✨ Success! 

Your Trading SaaS platform is now running. Visit the frontend dashboard to:
- View real-time equity curves
- Monitor strategy performance
- Check tax compliance
- Manage trading strategies

**Happy trading! 🚀**

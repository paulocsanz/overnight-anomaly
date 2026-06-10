# B3 Account Setup & Day Trading Registration (Brazil)

## Account Types & Options

### Option 1: Traditional Broker (Easiest)
```
Brokers: Clear, XP, Itaú, Bradesco, BTG, etc.
  ✓ Easy onboarding (online, 2-3 days)
  ✓ Support & customer service
  ✓ Mobile apps
  ✗ Higher commissions (0.05-0.10%)
  ✗ More fees
  
How to open: Website → fill form → video ID → done
Time: 1-2 days
Minimum: R$1,000
Commission: 0.05-0.10% per trade
```

### Option 2: B3 Direct (Cheapest - Recommended for you)
```
Direct access to B3 (no broker middleman)
  ✓ Lower commissions (0.02-0.03%)
  ✓ Direct order execution
  ✓ Lower fees overall
  ✗ Less customer support
  ✗ More complex setup
  ✗ Requires more technical knowledge
  
How to open: B3 website → register → pass tests → approved
Time: 3-5 days
Minimum: R$5,000 (or lower with some partners)
Commission: 0.02% per trade
```

### Option 3: Corretora Partner of B3
```
Partners of B3 offering direct access at lower costs
Examples: Agora Investimentos, Genial, Passfolio
  ✓ Lower commissions (0.02-0.05%)
  ✓ Easier than direct B3
  ✓ Good support
  ✗ Still more complex than retail brokers
  
Time: 2-4 days
Minimum: R$1,000-2,000
Commission: 0.02-0.05%
```

## Step-by-Step: B3 Direct Access (Best Option)

### Step 1: Prepare Documents
```
You'll need:
  ✓ CPF (Brazilian tax ID)
  ✓ Valid ID (RG/passport)
  ✓ Proof of address (utility bill, <3 months old)
  ✓ Bank account (for deposits/withdrawals)
  ✓ Income documentation (last 2 months pay stubs OR tax return)
  
If self-employed (you):
  ✓ CNPJ registration OR
  ✓ Last 2 years tax returns (IRPF)
  ✓ Business registration proof
```

### Step 2: Choose a B3 Partner
```
Easiest B3 direct partners:
1. Agora Investimentos
   - Website: agora.com.br
   - Commission: 0.02-0.03%
   - Minimum: R$1,000
   - Onboarding: 2-3 days
   - Support: Good, Portuguese/English

2. Genial Investimentos
   - Website: genial.com.br
   - Commission: 0.02-0.04%
   - Minimum: R$2,000
   - Onboarding: 3-4 days
   - Support: Excellent

3. Clear Corretora (Itaú)
   - Website: clear.com.br
   - Commission: 0.02% (cheapest)
   - Minimum: R$1,000
   - Onboarding: 1-2 days
   - Support: Excellent (Itaú backing)

4. XP Investimentos
   - Website: xp.com.br
   - Commission: 0.02-0.03%
   - Minimum: R$1,000
   - Onboarding: 2-3 days
   - Support: Very good

Recommendation for you: Clear or Agora (cheapest, fast)
```

### Step 3: Online Registration
```
1. Go to broker website (e.g., clear.com.br)
2. Click "Abrir conta" or "Investidor"
3. Fill personal info:
   - Name, CPF, email, phone
   - Address
   - Income/profession
   - Investment experience
4. Upload documents:
   - ID photo (RG/passport)
   - Proof of address
   - Income documentation
5. Video call verification:
   - 5-10 minutes
   - Show ID to camera
   - Answer questions (in Portuguese)
6. Bank account linking:
   - Connect your bank account (for deposits)
   - Takes 1-2 days to verify

Time: 2-3 business days total
```

### Step 4: Register for Day Trading
```
CRITICAL: This is DIFFERENT from opening the account

In Brazil, "day trading" is a special tax classification:
  - Triggers 20% income tax (instead of 15% capital gains)
  - BUT: allows unlimited day trades
  - Requires explicit registration

How to register:
1. Log into your broker account
2. Go to "Configurações" / "Settings"
3. Find "Operações Intradiárias" or "Day Trading"
4. Click "Registrar" or "Ativar"
5. Agree to terms (20% tax on profits)
6. Takes effect next trading day

Result: You get a "trader account" designation
  - Can day trade unlimited times
  - All profits taxed at 20%
  - Tax filing easier (automatic)
```

## Tax Registration & Reporting

### What Needs Tax Registration

**CPF-Based Account (Individual):**
```
If you're self-employed or freelancer:
  - CPF automatically registers as "independent"
  - Income from trading = additional income
  - File annually in IRPF (tax return)
  
If you're employed (W-2/salary):
  - Trading income = "other income" on your annual IRPF
  - Still file once per year in April
  - Can file online for free (via Receita Federal)
```

**CNPJ-Based Account (Business):**
```
If you have a business registered:
  - Open account under your CNPJ
  - Tax treatment depends on business type
  - Simpler bookkeeping (centralized)
  - Still file annual IRPF personally + company taxes

Recommendation: Use CPF for trading (simpler)
```

### Day Trading Tax Registration

**Format:** The trading system needs to know you're registered as day trader

```
Broker registration checklist:
  ☐ Account opened with broker/B3
  ☐ Day trading option activated (20% income tax)
  ☐ Confirmation email received
  ☐ "Trader" status visible in account

Your responsibility:
  ☐ Keep this proof (screenshot/email)
  ☐ Save all trade confirmations (broker provides)
  ☐ File annual tax return (IRPF)
```

## What to Report to Taxes (Annual)

### Annual IRPF Filing (April)

**Brazil requires:**
```
Every year in April, file IRPF (individual income tax return):
  1. All sources of income (salary, trading, other)
  2. All gains/losses from trading
  3. Deductible expenses (internet, software, etc.)
  4. Assets over R$300k (property, investments)

For trading specifically:
  - Total P&L for the year: sum of all trade results
  - Commission paid: deductible
  - Internet/computer: can be deducted
  - Trading education: can be deducted (courses, books)
  
Tax rate: 20% on NET profits (after commissions)

Example:
  Gross trading profit: R$10,000
  Commissions paid: -R$500
  Internet (deductible): -R$200
  Taxable income: R$9,300
  Taxes owed: 20% × R$9,300 = R$1,860
```

### Daily Records to Keep

Your `live_trader.py` system already records everything:

```
Automatic record-keeping:
  ✓ Trade date
  ✓ Ticker traded
  ✓ Entry/exit prices
  ✓ P&L (profit/loss)
  ✓ Commission paid
  ✓ Taxes due

You should also keep:
  ✓ Screenshots of broker statements (monthly)
  ✓ Email confirmations from broker
  ✓ Account statements (2-3 per year)
  
Export monthly:
  - Go to broker → statements/reports
  - Download PDF for that month
  - Save in: data/trading/tax_records/[YYYY-MM].pdf
```

## Reporting Timeline

### Monthly (During Year)
```
Activities:
  - Run live_trader.py daily
  - System tracks all trades
  - No action needed (just monitor)
```

### Quarterly (Optional)
```
Recommended:
  - Export broker statement
  - Check: YTD profit/loss
  - Verify system calculations match broker
  
Time: 15 minutes
```

### Annually (April - MANDATORY)
```
Tax filing deadline: April 30th

Process:
  1. Export full year statement from broker
  2. Run summary report from live_trader.py:
     - Total trades
     - Total P&L
     - Total commissions
  3. Gather deductible expenses:
     - Internet bills
     - Computer/equipment
     - Course/book purchases
  4. File IRPF (online, via Receita Federal):
     - Website: imposto de renda
     - Free to file online
     - Takes 30-45 minutes
     - Can hire accountant (costs ~R$500-1000)

Documents to have ready:
  - CPF
  - Trading system P&L report
  - Broker year-end statement
  - Bank statements (deposits/withdrawals)
  - Expense receipts
```

## Sample Tax Report from Your System

Create a simple annual report:

```python
# In live_trader.py, add:
def generate_tax_report(year: int):
    """Generate annual tax report for IRPF filing."""
    trades = load_all_trades(year)
    
    report = {
        "year": year,
        "total_trades": len(trades),
        "gross_pnl": sum(t["pnl"] for t in trades),
        "commissions_paid": sum(t["commission"] for t in trades),
        "net_pnl": gross_pnl - commissions_paid,
        "tax_owed_20pct": net_pnl * 0.20,
        "trades_by_month": {...},
        "top_winners": [...],
        "top_losers": [...],
    }
    
    # Save to tax_records/
    save_json(f"data/trading/tax_records/{year}_tax_report.json", report)
    return report

# Usage: python -c "from live_trader import generate_tax_report; generate_tax_report(2024)"
```

## Your 30-Day Setup Checklist

### Week 1: Account Setup
```
☐ Day 1-2: Gather documents (ID, proof of address, income)
☐ Day 3: Choose broker (recommend: Clear or Agora)
☐ Day 4-5: Register online, pass video verification
☐ Day 6: Account approved, link bank account
☐ Day 7: Fund account with R$1,000
```

### Week 2: Day Trading Registration
```
☐ Day 8: Log into account
☐ Day 9: Register for "Day Trading" (20% tax option)
☐ Day 10: Confirmation received
☐ Day 11-14: Test with small trades (manual, R$10-50)
```

### Week 3-4: Live Trading Begins
```
☐ Day 15-21: Run live_trader.py daily, accumulate trades
☐ Day 22-28: Monitor dashboard, build confidence
☐ Day 29-30: First scaling decision (R$1k → R$2k?)
```

### Ongoing: Tax Prep
```
☐ Every month: Save broker statement
☐ Every quarter: Verify system vs broker match
☐ April: File annual IRPF (takes 30-45 min online)
```

## Important Notes

### Regulatory
```
✓ Day trading in Brazil is legal and regulated
✓ B3 oversight means your account is protected
✓ Brokers are insured (up to R$250k CPDC coverage)
✓ Tax evasion is illegal (20% tax must be paid)
```

### Practical
```
✓ Minimum to start: R$1,000
✓ Recommended: R$2,000-5,000 (easier position sizing)
✓ Opening account: 2-5 business days
✓ First trade possible: Same day after approval
✓ Tax filing: 30-45 minutes online in April
```

### Costs Summary
```
One-time:
  - Account opening: FREE
  - ID verification: FREE
  - First deposit: FREE (varies by bank)
  
Per trade (on R$1,000 at 0.02% commission):
  - Entry commission: R$0.20
  - Exit commission: R$0.20
  - Total per trade: R$0.40
  
Annual (if R$50k trading volume):
  - Commissions: ~R$200
  - Taxes (assuming R$5k profit): ~R$1,000
  - Total cost: ~R$1,200 (or 2.4% of trading volume)
```

---

## Quick Links

**Account Opening:**
- Clear: clear.com.br (Recommended - cheapest, fastest)
- Agora: agora.com.br (Good support)
- Genial: genial.com.br (Excellent support)
- XP: xp.com.br (Very good all-around)

**Tax Filing:**
- Receita Federal (Free online): irpf.receita.fazenda.gov.br
- Video tutorials: YouTube "como preencher IRPF 2024"
- Accountant help: ~R$500-1,000 (optional)

**B3 Rules:**
- Official rules: b3.com.br (search "day trading")
- Trading regulations: ANBIMA guidelines

---

You're ready. **Next action: Go to Clear.com.br or Agora.com.br and click "Abrir conta"** 🚀

Have questions about the account setup? Ask in this chat before you start.

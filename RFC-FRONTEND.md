# RFC: Frontend Specification - Trading SaaS Dashboard

---

## 1. Frontend Technology Choice

## CHOSEN: React + TypeScript + Vite

**Why React:**
- ✅ Industry standard (largest ecosystem)
- ✅ Best library support (UI, charts, forms)
- ✅ Strong TypeScript support
- ✅ Excellent for dashboards
- ✅ Large developer community

**Tech Stack:**
```
Frontend Framework: React 18 + TypeScript
Build Tool: Vite (blazing fast)
CSS Framework: Tailwind CSS (utility-first)
Charts: Recharts (React-native charts)
Tables: React-Table + TanStack
State Management: Zustand (lightweight)
HTTP Client: TanStack Query (React Query)
Form Handling: React Hook Form
UI Components: Headless UI + Radix UI
Date handling: date-fns
Notifications: Sonner (toast)
Deployment: Railway static service or Vercel
```

**Why Vite over Create React App:**
- ✅ 10x faster builds
- ✅ Instant HMR (hot module replacement)
- ✅ Smaller bundle
- ✅ Better DX (developer experience)
- ✅ ESM native
```

---

## 3. Dashboard Pages & Components

### 3.1 Home / Overview Page
```vue
<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="sticky top-0 bg-white border-b">
      <div class="flex justify-between items-center p-4">
        <h1>📊 Trading SaaS Dashboard</h1>
        <div class="flex gap-4">
          <span>Last updated: {{ lastUpdate }}</span>
          <button @click="refresh">🔄 Refresh</button>
        </div>
      </div>
    </header>

    <!-- KPI Cards -->
    <div class="grid grid-cols-4 gap-4 p-4">
      <KPICard 
        title="Total Capital (Real)"
        value="R$1,000"
        change="+10%"
        color="green"
      />
      <KPICard 
        title="Total P&L (Real)"
        value="R$100"
        change="+10%"
        color="green"
      />
      <KPICard 
        title="Active Strategies"
        value="3"
        change="All profitable"
        color="blue"
      />
      <KPICard 
        title="Alerts"
        value="1"
        change="Gap shrinking"
        color="yellow"
      />
    </div>

    <!-- Tabs: Overview / Detailed -->
    <div class="tabs p-4">
      <tab name="Overview">
        <!-- Today's Summary -->
        <div class="grid grid-cols-2 gap-4">
          <Panel title="Today's Trades">
            <TradesTodayChart :trades="todaysTrades" />
            <TradeSummary :count="7" :pnl="150" :winRate="57" />
          </Panel>

          <Panel title="Strategy Performance">
            <StrategyComparison :strategies="strategies" />
          </Panel>
        </div>

        <!-- Alerts -->
        <Panel title="Recent Alerts" class="mt-4">
          <AlertsList :alerts="recentAlerts" />
        </Panel>
      </tab>

      <tab name="Detailed">
        <!-- Equity Curves -->
        <Panel title="Equity Growth (All Strategies)">
          <EquityCurveChart 
            :real-data="realEquityCurve"
            :simulated-data="simulatedEquityCurve"
          />
        </Panel>

        <!-- Monthly Returns -->
        <Panel title="Monthly Returns">
          <MonthlyReturnsChart :monthly-returns="monthlyReturns" />
        </Panel>
      </tab>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchDashboard, fetchAlerts } from '@/api'

const lastUpdate = ref(new Date())
const strategies = ref([])
const todaysTrades = ref([])
const recentAlerts = ref([])

onMounted(async () => {
  const data = await fetchDashboard()
  strategies.value = data.strategies
  todaysTrades.value = data.trades_today
  recentAlerts.value = await fetchAlerts()
})

const refresh = async () => {
  // Trigger manual refresh
}
</script>
```

---

### 3.2 Strategies Page
```vue
<template>
  <div class="strategies-page">
    <!-- Strategy List -->
    <div class="mb-4">
      <h2>Active Strategies</h2>
      <button class="btn-primary" @click="showAddForm = true">
        + Add Strategy
      </button>
    </div>

    <!-- Strategy Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <StrategyCard 
        v-for="strategy in strategies"
        :key="strategy.id"
        :strategy="strategy"
        @edit="editStrategy"
        @delete="deleteStrategy"
      />
    </div>

    <!-- Add/Edit Strategy Modal -->
    <Modal v-if="showAddForm" @close="showAddForm = false">
      <StrategyForm @submit="saveStrategy" :initial="editingStrategy" />
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchStrategies, createStrategy, updateStrategy } from '@/api'

const strategies = ref([])
const showAddForm = ref(false)
const editingStrategy = ref(null)

onMounted(async () => {
  strategies.value = await fetchStrategies()
})

const editStrategy = (strategy) => {
  editingStrategy.value = strategy
  showAddForm.value = true
}

const saveStrategy = async (formData) => {
  if (editingStrategy.value) {
    await updateStrategy(editingStrategy.value.id, formData)
  } else {
    await createStrategy(formData)
  }
  strategies.value = await fetchStrategies()
  showAddForm.value = false
}
</script>
```

**StrategyCard Component:**
```vue
<template>
  <div class="card p-4 border rounded-lg hover:shadow-lg">
    <!-- Header -->
    <div class="flex justify-between items-center mb-3">
      <h3 class="text-lg font-bold">{{ strategy.name }}</h3>
      <div class="flex gap-2">
        <button @click="$emit('edit')" class="btn-sm">✏️</button>
        <button @click="$emit('delete')" class="btn-sm text-red">🗑️</button>
      </div>
    </div>

    <!-- Description -->
    <p class="text-gray-600 text-sm mb-3">{{ strategy.description }}</p>

    <!-- Real Account -->
    <div class="border-t pt-3 mb-3">
      <h4 class="text-sm font-bold text-blue-600">Real Account</h4>
      <div class="grid grid-cols-2 text-sm gap-2">
        <span>Capital: <strong>R${{ strategy.real_account.capital }}</strong></span>
        <span>Equity: <strong>R${{ strategy.real_account.equity }}</strong></span>
        <span>Return: <strong class="text-green-600">{{ strategy.real_account.return }}%</strong></span>
        <span>Win Rate: <strong>{{ strategy.real_account.win_rate }}%</strong></span>
      </div>
    </div>

    <!-- Simulated Account -->
    <div class="border-t pt-3 mb-3">
      <h4 class="text-sm font-bold text-purple-600">Simulated Account</h4>
      <div class="grid grid-cols-2 text-sm gap-2">
        <span>Capital: <strong>R${{ strategy.sim_account.capital }}</strong></span>
        <span>Equity: <strong>R${{ strategy.sim_account.equity }}</strong></span>
        <span>Return: <strong class="text-green-600">{{ strategy.sim_account.return }}%</strong></span>
        <span>Sharpe: <strong>{{ strategy.sim_account.sharpe }}</strong></span>
      </div>
    </div>

    <!-- Auto-Scaling Status -->
    <div v-if="strategy.ready_to_scale" class="bg-green-50 p-2 rounded text-sm">
      ✅ Ready to scale (Sharpe > 1.0, Win% > 55%)
    </div>
  </div>
</template>
```

---

### 3.3 Trades Page
```vue
<template>
  <div class="trades-page">
    <!-- Filters -->
    <div class="mb-4 p-4 bg-gray-50 rounded-lg">
      <div class="grid grid-cols-4 gap-4">
        <input v-model="filters.ticker" placeholder="Ticker" class="input" />
        <select v-model="filters.strategy" class="input">
          <option value="">All Strategies</option>
          <option v-for="s in strategies" :value="s.id">{{ s.name }}</option>
        </select>
        <input v-model="filters.dateFrom" type="date" class="input" />
        <button @click="applyFilters" class="btn-primary">Filter</button>
      </div>
    </div>

    <!-- Trades Table -->
    <table class="w-full border-collapse">
      <thead class="bg-gray-100">
        <tr>
          <th class="border p-2 text-left cursor-pointer" @click="sortBy('date')">
            Date {{ sortColumn === 'date' ? (sortAsc ? '↓' : '↑') : '' }}
          </th>
          <th class="border p-2 text-left">Ticker</th>
          <th class="border p-2 text-left">Strategy</th>
          <th class="border p-2 text-right">Entry</th>
          <th class="border p-2 text-right">Exit</th>
          <th class="border p-2 text-right">Gap %</th>
          <th class="border p-2 text-right">Return %</th>
          <th class="border p-2 text-right">P&L</th>
          <th class="border p-2 text-center">Status</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="trade in paginatedTrades" :key="trade.id" class="hover:bg-gray-50">
          <td class="border p-2">{{ formatDate(trade.date) }}</td>
          <td class="border p-2 font-bold">{{ trade.ticker }}</td>
          <td class="border p-2">{{ trade.strategy }}</td>
          <td class="border p-2 text-right">R${{ trade.entry_price }}</td>
          <td class="border p-2 text-right">R${{ trade.exit_price }}</td>
          <td class="border p-2 text-right" :class="trade.gap_pct > 0 ? 'text-red-600' : 'text-green-600'">
            {{ trade.gap_pct }}%
          </td>
          <td class="border p-2 text-right" :class="trade.return_pct > 0 ? 'text-green-600' : 'text-red-600'">
            {{ trade.return_pct }}%
          </td>
          <td class="border p-2 text-right font-bold" :class="trade.pnl > 0 ? 'text-green-600' : 'text-red-600'">
            R${{ trade.pnl }}
          </td>
          <td class="border p-2 text-center">
            <span v-if="trade.status === 'executed'" class="badge bg-green-100">✓</span>
            <span v-else-if="trade.status === 'pending'" class="badge bg-yellow-100">⏳</span>
            <span v-else class="badge bg-red-100">✗</span>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Pagination -->
    <div class="mt-4 flex justify-center gap-2">
      <button @click="page--" :disabled="page === 1">← Prev</button>
      <span>Page {{ page }} of {{ totalPages }}</span>
      <button @click="page++" :disabled="page === totalPages">Next →</button>
    </div>

    <!-- Export -->
    <button @click="exportCSV" class="mt-4 btn-secondary">📥 Export CSV</button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchTrades } from '@/api'

const trades = ref([])
const page = ref(1)
const pageSize = 25
const sortColumn = ref('date')
const sortAsc = ref(false)

const filters = ref({
  ticker: '',
  strategy: '',
  dateFrom: '',
})

const paginatedTrades = computed(() => {
  let filtered = trades.value
  
  if (filters.value.ticker) {
    filtered = filtered.filter(t => t.ticker.includes(filters.value.ticker))
  }
  
  filtered.sort((a, b) => {
    const aVal = a[sortColumn.value]
    const bVal = b[sortColumn.value]
    return sortAsc.value ? aVal - bVal : bVal - aVal
  })
  
  const start = (page.value - 1) * pageSize
  return filtered.slice(start, start + pageSize)
})

const totalPages = computed(() => Math.ceil(trades.value.length / pageSize))

onMounted(async () => {
  trades.value = await fetchTrades()
})

const exportCSV = () => {
  // Export trades to CSV
}
</script>
```

---

### 3.4 Performance Page
```vue
<template>
  <div class="performance-page">
    <!-- Strategy Comparison Table -->
    <Panel title="Strategy Comparison">
      <table class="w-full">
        <thead>
          <tr class="bg-gray-100">
            <th class="p-2 text-left">Strategy</th>
            <th class="p-2 text-right">Trades</th>
            <th class="p-2 text-right">Win %</th>
            <th class="p-2 text-right">Avg Return</th>
            <th class="p-2 text-right">Sharpe</th>
            <th class="p-2 text-right">Real Return</th>
            <th class="p-2 text-right">Sim Return</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in strategies" :key="s.id" class="border-b hover:bg-gray-50">
            <td class="p-2 font-bold">{{ s.name }}</td>
            <td class="p-2 text-right">{{ s.total_trades }}</td>
            <td class="p-2 text-right">{{ s.win_rate }}%</td>
            <td class="p-2 text-right">{{ s.avg_return }}%</td>
            <td class="p-2 text-right">{{ s.sharpe }}</td>
            <td class="p-2 text-right text-green-600">+{{ s.real_return }}%</td>
            <td class="p-2 text-right text-green-600">+{{ s.sim_return }}%</td>
          </tr>
        </tbody>
      </table>
    </Panel>

    <!-- Equity Curve (Multi-Strategy) -->
    <Panel title="Equity Growth Over Time" class="mt-4">
      <canvas id="equityChart"></canvas>
    </Panel>

    <!-- Monthly Returns -->
    <Panel title="Monthly Returns" class="mt-4">
      <BarChart :data="monthlyData" />
    </Panel>

    <!-- Drawdown Analysis -->
    <Panel title="Max Drawdown by Strategy" class="mt-4">
      <div class="grid grid-cols-3 gap-4">
        <div v-for="s in strategies" :key="s.id" class="p-4 border rounded">
          <h4>{{ s.name }}</h4>
          <p class="text-2xl font-bold text-red-600">{{ s.max_drawdown }}%</p>
          <p class="text-sm text-gray-600">Max drawdown</p>
        </div>
      </div>
    </Panel>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Chart as ChartJS, Line, BarController } from 'chart.js'
import { fetchPerformance } from '@/api'

const strategies = ref([])
const monthlyData = ref(null)

onMounted(async () => {
  const data = await fetchPerformance()
  strategies.value = data.strategies
  monthlyData.value = data.monthly_returns
})
</script>
```

---

### 3.5 Tax Reports Page
```vue
<template>
  <div class="tax-page">
    <!-- Year Selector -->
    <div class="mb-4">
      <select v-model="selectedYear" @change="loadTaxData" class="input">
        <option value="2024">2024</option>
        <option value="2025">2025</option>
        <option value="2026">2026</option>
      </select>
    </div>

    <!-- Tax Summary -->
    <div class="grid grid-cols-2 gap-4 mb-4">
      <SummaryCard title="Total Trades" :value="taxData.total_trades" />
      <SummaryCard title="Gross P&L" :value="`R$${taxData.gross_pnl}`" color="blue" />
      <SummaryCard title="Commissions" :value="`-R$${taxData.commissions}`" color="red" />
      <SummaryCard title="Net P&L" :value="`R$${taxData.net_pnl}`" color="green" />
      <SummaryCard title="Tax Owed (20%)" :value="`R$${taxData.tax_owed}`" color="orange" />
    </div>

    <!-- Strategy Breakdown -->
    <Panel title="P&L by Strategy">
      <table class="w-full">
        <thead>
          <tr class="bg-gray-100">
            <th class="p-2 text-left">Strategy</th>
            <th class="p-2 text-right">Trades</th>
            <th class="p-2 text-right">Gross P&L</th>
            <th class="p-2 text-right">Commissions</th>
            <th class="p-2 text-right">Net P&L</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in taxData.by_strategy" :key="s.strategy">
            <td class="p-2">{{ s.strategy }}</td>
            <td class="p-2 text-right">{{ s.trades }}</td>
            <td class="p-2 text-right">R${{ s.gross_pnl }}</td>
            <td class="p-2 text-right">-R${{ s.commissions }}</td>
            <td class="p-2 text-right font-bold">R${{ s.net_pnl }}</td>
          </tr>
        </tbody>
      </table>
    </Panel>

    <!-- Monthly Breakdown -->
    <Panel title="P&L by Month" class="mt-4">
      <BarChart :data="taxData.by_month" />
    </Panel>

    <!-- Export & Filing -->
    <div class="mt-4 flex gap-4">
      <button @click="exportForIRPF" class="btn-primary">
        📄 Export for IRPF Filing
      </button>
      <button @click="exportDetailedCSV" class="btn-secondary">
        📥 Export Detailed CSV
      </button>
    </div>

    <!-- Instructions -->
    <Panel title="How to File Taxes" class="mt-4">
      <ol class="list-decimal list-inside">
        <li>Download the exported file above</li>
        <li>Go to: irpf.receita.fazenda.gov.br</li>
        <li>Download IRPF software (free)</li>
        <li>Enter trading income: R${{ taxData.net_pnl }}</li>
        <li>Enter tax due: R${{ taxData.tax_owed }}</li>
        <li>File online by April 30</li>
      </ol>
    </Panel>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchTaxReport } from '@/api'

const selectedYear = ref('2026')
const taxData = ref({})

onMounted(async () => {
  taxData.value = await fetchTaxReport(selectedYear.value)
})

const loadTaxData = async () => {
  taxData.value = await fetchTaxReport(selectedYear.value)
}

const exportForIRPF = () => {
  // Generate IRPF-compatible format
}

const exportDetailedCSV = () => {
  // Export all trades as CSV
}
</script>
```

---

## 4. Frontend File Structure

```
frontend/
├── public/
│   ├── index.html          # Main entry
│   └── favicon.ico
│
├── src/
│   ├── components/
│   │   ├── KPICard.tsx
│   │   ├── StrategyCard.tsx
│   │   ├── TradesTable.tsx
│   │   ├── EquityCurveChart.tsx
│   │   ├── StrategyForm.tsx
│   │   ├── Modal.tsx
│   │   ├── Panel.tsx
│   │   └── Alert.tsx
│   │
│   ├── pages/
│   │   ├── Home.tsx         # Dashboard overview
│   │   ├── Strategies.tsx   # Strategy management
│   │   ├── Accounts.tsx     # Account details
│   │   ├── Trades.tsx       # Trade history
│   │   ├── Performance.tsx  # Charts & metrics
│   │   └── Tax.tsx          # Tax reports
│   │
│   ├── api/
│   │   └── client.ts        # API calls (TanStack Query)
│   │
│   ├── hooks/
│   │   ├── useFetchStrategies.ts
│   │   ├── useFetchTrades.ts
│   │   └── useFetchPerformance.ts
│   │
│   ├── utils/
│   │   ├── format.ts        # Number/date formatting
│   │   └── types.ts         # TypeScript types
│   │
│   ├── store/
│   │   └── useStore.ts      # Zustand store
│   │
│   ├── App.tsx              # Root component
│   ├── main.tsx             # Entry point
│   └── index.css            # Global styles (Tailwind)
│
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── .env.example
```

---

## 5. Real-Time Updates

### Option A: Polling (Simple)
```javascript
// Refresh every 30 seconds
setInterval(async () => {
  const data = await api.fetchDashboard()
  updateUI(data)
}, 30000)
```

### Option B: WebSocket (Advanced, Optional)
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/dashboard')
ws.onmessage = (event) => {
  const update = JSON.parse(event.data)
  updateUI(update)  // Real-time update
}
```

**Recommendation:** Start with polling (simpler), add WebSocket later if needed.

---

## 6. Authentication (Optional for MVP)

**For MVP: Skip authentication** (dashboard is internal/local-only)

**For Production:**
```javascript
// Login flow
const login = async (username, password) => {
  const response = await api.post('/auth/login', { username, password })
  localStorage.setItem('token', response.token)
  // Include token in all API calls
}

// Protected routes
<Route path="/dashboard" component={ProtectedRoute} />
```

---

## 7. Mobile Responsiveness

**Tailwind Grid Breakpoints:**
```html
<!-- Mobile first -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
  <!-- 1 col on mobile, 2 on tablet (md), 4 on desktop (lg) -->
</div>
```

All pages responsive by default with Tailwind.

---

## 8. Deployment

### Build & Deploy
```bash
# Build
npm run build          # Creates /dist folder

# Deploy to Railway
railway up            # Uploads dist/ as static service

# Or deploy to Vercel (one-command)
npm install -g vercel
vercel deploy
```

### Railway Static Service
```yaml
# railway.toml
[[services]]
name = "dashboard"
builder = "npm"
startCommand = "npm run build && npm run preview"
```

---

## 9. API Integration (Frontend → Backend)

### Example API Call
```javascript
// src/api/client.js
import axios from 'axios'

const API_BASE = process.env.VUE_APP_API_URL || 'http://localhost:8000/api'

export const fetchDashboard = async () => {
  const response = await axios.get(`${API_BASE}/performance`)
  return response.data
}

export const createStrategy = async (config) => {
  const response = await axios.post(`${API_BASE}/strategies`, config)
  return response.data
}
```

---

## 10. Summary: Frontend Tech Stack

| Aspect | Choice |
|--------|--------|
| **Framework** | React 18 + TypeScript |
| **Build Tool** | Vite (10x faster than webpack) |
| **CSS** | Tailwind CSS |
| **Charts** | Recharts (React-native) |
| **Tables** | React-Table (headless) |
| **State** | Zustand (lightweight) |
| **Data Fetching** | TanStack Query (React Query) |
| **HTTP** | axios (via React Query) |
| **Deployment** | Railway static |
| **Real-time** | Polling (30s) or WebSocket (future) |
| **Authentication** | Skip for MVP |
| **Mobile** | Responsive (Tailwind) |

---

## 11. Build Time Estimate

- **Setup & project scaffolding:** 30 min
- **Pages (Home, Strategies, Trades, Performance, Tax):** 2-2.5 hours
- **Components (Cards, Tables, Charts using Recharts):** 2-2.5 hours
- **API integration (React Query) & styling:** 1-1.5 hours
- **Testing & polish:** 1 hour
- **Total:** ~7-8 hours

---

## 12. What You'll Have

✅ **Professional dashboard** (no external hosting needed)  
✅ **Real-time strategy monitoring**  
✅ **Beautiful charts & tables**  
✅ **Mobile-responsive design**  
✅ **Export to CSV/IRPF**  
✅ **One-click deployment**  

---

**Ready to build the frontend?** (Y/N)

If yes, I'll create:
1. Vue 3 project with Vite
2. All 5 pages + components
3. API integration
4. Styling with Tailwind
5. Deploy config

import { useState, useMemo, useEffect, useRef, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { api } from '../api'

// ── Types ─────────────────────────────────────────────────────────────────────

type StrategySummary = {
  strategy_id: string; strategy_name: string; total_trades: number
  win_rate: number; avg_return_pct: number; total_return_pct: number
  best_trade_pct: number; worst_trade_pct: number; total_pnl: number
  sharpe_ratio: number; first_trade_date: string | null; last_trade_date: string | null
}
type BacktestTrade = {
  id: string; strategy_id: string; strategy_name: string; trade_date: string
  ticker: string; signal_type: string; gap_pct: number; entry_price: number
  exit_price: number; net_return_pct: number; pnl: number; position_size: number
  intended_position_size: number; liquidity_cap_brl: number; capacity_used_pct: number
  backtest_run_id: string | null
}
type TradesResponse = { trades: BacktestTrade[]; total: number; page: number; per_page: number }
type EquityPoint = { date: string; equity: number }
type StrategyCurve = { strategy_id: string; strategy_name: string; initial_capital: number; curve: EquityPoint[] }
type RunSummary = {
  id: string; name: string; params: Record<string, unknown>
  created_at: string; total_trades: number; win_rate: number
  avg_return_pct: number; total_pnl: number
}
type Scenario = { id: string; strategyId: string; leverage: number }
type Combo = {
  id: string; strategyId: string; strategyName: string; leverage: number
  color: string; dash: string | undefined; initialCapital: number; baseCurve: EquityPoint[]
}
type Window = { label: string; start: string; end: string }
type Stats = { totalReturn: number; annReturn: number; maxDrawdown: number; sharpe: number; calmar: number; lowestEquity: number }

// ── Constants ─────────────────────────────────────────────────────────────────

const STRATEGY_PALETTE = ['#3b82f6', '#a855f7', '#f59e0b', '#10b981', '#ef4444', '#06b6d4']
const LEVERAGE_DASH: Record<number, string | undefined> = {
  1: undefined, 2: '10 4', 3: '4 4', 4: '14 4 4 4', 5: '12 4 4 4 4 4', 10: '3 3',
}
const LEVERAGE_OPTIONS = [1, 2, 3, 4, 5, 10]

// ── Pure helpers ──────────────────────────────────────────────────────────────

function applyLeverage(curve: EquityPoint[], cap: number, lev: number): EquityPoint[] {
  if (lev === 1) return curve
  const out: EquityPoint[] = []
  let prev = cap, levEq = cap
  for (const pt of curve) {
    levEq = Math.max(levEq + (pt.equity - prev) * lev, 0)
    out.push({ date: pt.date, equity: levEq })
    prev = pt.equity
  }
  return out
}

function toReturnPct(curve: EquityPoint[], cap: number): EquityPoint[] {
  return curve.map(p => ({ date: p.date, equity: cap > 0 ? (p.equity - cap) / cap * 100 : 0 }))
}

function computeStats(curve: EquityPoint[], cap: number): Stats {
  if (!curve.length) return { totalReturn: 0, annReturn: 0, maxDrawdown: 0, sharpe: 0, calmar: 0, lowestEquity: cap }
  const final = curve[curve.length - 1].equity
  const lowestEquity = Math.min(...curve.map(p => p.equity))
  const totalReturn = ((final - cap) / cap) * 100
  const prevs = [cap, ...curve.slice(0, -1).map(p => p.equity)]
  const daily = curve.map((p, i) => prevs[i] > 0 ? (p.equity - prevs[i]) / prevs[i] * 100 : 0)
  const n = daily.length
  const mean = daily.reduce((s, r) => s + r, 0) / n
  const std = Math.sqrt(daily.reduce((s, r) => s + (r - mean) ** 2, 0) / Math.max(n - 1, 1))
  const sharpe = std > 0 ? (mean / std) * Math.sqrt(252) : 0
  let peak = cap, maxDD = 0
  for (const e of [cap, ...curve.map(p => p.equity)]) {
    if (e > peak) peak = e
    const dd = peak > 0 ? (peak - e) / peak * 100 : 0
    if (dd > maxDD) maxDD = dd
  }
  const years = n / 252
  const annReturn = years > 0 ? ((final / Math.max(cap, 0.01)) ** (1 / years) - 1) * 100 : totalReturn
  return { totalReturn, annReturn, maxDrawdown: maxDD, sharpe, calmar: maxDD > 0 ? annReturn / maxDD : 0, lowestEquity }
}

function buildWindows(curves: StrategyCurve[]): Window[] {
  const dates = curves.flatMap(c => c.curve.map(p => p.date)).sort()
  if (!dates.length) return []
  const minDate = dates[0], maxDate = dates[dates.length - 1]
  const minY = parseInt(minDate.slice(0, 4)), maxY = parseInt(maxDate.slice(0, 4))
  const qs = [['01-01', '03-31'], ['04-01', '06-30'], ['07-01', '09-30'], ['10-01', '12-31']]
  const all: Window[] = []
  for (let y = minY; y <= maxY; y++) {
    qs.forEach(([s, e], qi) => {
      const start = `${y}-${s}`, end = `${y}-${e}`
      if (end >= minDate && start <= maxDate)
        all.push({ label: `Q${qi + 1} ${y}`, start, end })
    })
  }
  return all.slice(-6)
}

const fmtPct = (n: number, d = 1) => `${n >= 0 ? '+' : ''}${n.toFixed(d)}%`
const fmtBrl = (n: number) => `R$${n.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`

// ── Sub-components ────────────────────────────────────────────────────────────

function DashLine({ dash, color, width = 28 }: { dash?: string; color: string; width?: number }) {
  return (
    <svg width={width} height={12} className="flex-shrink-0">
      <line x1="0" y1="6" x2={width} y2="6" stroke={color} strokeWidth="2.5" strokeDasharray={dash} />
    </svg>
  )
}

function PeriodMiniChart({ win, data, combos, finalReturns }: {
  win: Window
  data: Record<string, unknown>[]
  combos: Combo[]
  finalReturns: Record<string, number | null>
}) {
  const hasData = data.length > 0
  const best = hasData
    ? combos.reduce<{ id: string; val: number } | null>((acc, c) => {
        const v = finalReturns[c.id]
        return (v != null && (!acc || v > acc.val)) ? { id: c.id, val: v } : acc
      }, null)
    : null

  return (
    <div className="bg-slate-800/70 rounded-lg overflow-hidden border border-slate-700/50">
      <div className="px-3 py-2 bg-slate-700/30 flex items-center justify-between">
        <span className="text-sm font-semibold">{win.label}</span>
        <span className="text-xs text-slate-500">{win.start.slice(0, 7)} → {win.end.slice(0, 7)}</span>
      </div>
      {hasData ? (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid strokeDasharray="2 3" stroke="#1e293b" />
            <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#475569' }} interval="preserveStartEnd" tickLine={false} />
            <YAxis tickFormatter={v => `${(v as number).toFixed(0)}%`} tick={{ fontSize: 9, fill: '#475569' }} tickLine={false} axisLine={false} width={36} />
            <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
            <Tooltip
              contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 6, fontSize: 11, padding: '4px 8px' }}
              formatter={(v: number, key: string) => {
                const c = combos.find(x => x.id === key)
                return [`${v.toFixed(2)}%`, c ? `${c.strategyName}${c.leverage > 1 ? ` ${c.leverage}x` : ''}` : key]
              }}
              labelStyle={{ color: '#64748b', fontSize: 10 }}
            />
            {combos.map(c => (
              <Line key={c.id} type="monotone" dataKey={c.id} stroke={c.color}
                strokeWidth={1.5} dot={false} connectNulls strokeDasharray={c.dash} name={c.id} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex items-center justify-center h-[180px] text-slate-600 text-xs">No data for this period</div>
      )}
      <div className="px-3 pb-3 pt-1 grid grid-cols-2 gap-x-3 gap-y-0.5">
        {combos.map(c => {
          const ret = finalReturns[c.id]
          return (
            <div key={c.id} className={`flex items-center justify-between text-xs rounded px-1 ${best?.id === c.id ? 'bg-slate-700/50' : ''}`}>
              <div className="flex items-center gap-1 min-w-0 overflow-hidden">
                <DashLine dash={c.dash} color={c.color} width={20} />
                <span className="text-slate-400 truncate text-[10px]">
                  {c.strategyName.split(' ')[0]}{c.leverage > 1 ? ` ${c.leverage}x` : ''}
                </span>
              </div>
              <span className={`font-mono font-semibold text-[11px] flex-shrink-0 ${ret == null ? 'text-slate-600' : ret >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {ret != null ? fmtPct(ret) : '—'}
                {best?.id === c.id && ret != null && <span className="ml-0.5 text-yellow-400">★</span>}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Backtest() {
  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: summary = [] } = useQuery<StrategySummary[]>({
    queryKey: ['backtest-summary'],
    queryFn: () => api.get('/api/backtest/summary').then(r => r.data),
  })
  const { data: equityCurves = [], isSuccess: curvesLoaded } = useQuery<StrategyCurve[]>({
    queryKey: ['backtest-equity-curves'],
    queryFn: () => api.get('/api/backtest/equity-curves').then(r => r.data),
  })
  const { data: runs = [] } = useQuery<RunSummary[]>({
    queryKey: ['backtest-runs'],
    queryFn: () => api.get('/api/backtest/runs').then(r => r.data),
  })

  // ── Backtest job status ───────────────────────────────────────────────────

  type JobStatus = {
    id: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    total_trades: number | null
    started_at: string | null
    completed_at: string | null
    error_message: string | null
    created_at: string
  }
  type JobStatusResponse = { job: JobStatus | null; total_backtest_trades: number }

  const queryClient = useQueryClient()
  const [triggering, setTriggering] = useState(false)

  const jobActive = (j: JobStatus | null) => j?.status === 'pending' || j?.status === 'running'

  const { data: jobStatusData } = useQuery<JobStatusResponse>({
    queryKey: ['backtest-job-status'],
    queryFn: () => api.get('/api/backtest/job-status').then(r => r.data),
    refetchInterval: (query) => {
      const data = query.state.data as JobStatusResponse | undefined
      return jobActive(data?.job ?? null) ? 3000 : 30000
    },
  })

  const triggerBacktest = useCallback(async () => {
    if (triggering) return
    setTriggering(true)
    try {
      await api.post('/api/backtest/trigger', {})
      await queryClient.invalidateQueries({ queryKey: ['backtest-job-status'] })
    } finally {
      setTriggering(false)
    }
  }, [triggering, queryClient])

  // Invalidate equity/summary when job completes
  useEffect(() => {
    if (jobStatusData?.job?.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['backtest-summary'] })
      queryClient.invalidateQueries({ queryKey: ['backtest-equity-curves'] })
      queryClient.invalidateQueries({ queryKey: ['backtest-runs'] })
    }
  }, [jobStatusData?.job?.status, queryClient])

  // ── Scenario state ────────────────────────────────────────────────────────

  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [yMode, setYMode] = useState<'equity' | 'return'>('return')
  const [scaleMode, setScaleMode] = useState<'linear' | 'log'>('linear')
  const initialized = useRef(false)

  useEffect(() => {
    if (curvesLoaded && equityCurves.length > 0 && !initialized.current) {
      initialized.current = true
      setScenarios(equityCurves.map(sc => ({
        id: crypto.randomUUID(),
        strategyId: sc.strategy_id,
        leverage: 1,
      })))
    }
  }, [curvesLoaded, equityCurves])

  const addScenario = () => {
    const first = equityCurves[0]
    if (!first) return
    setScenarios(prev => [...prev, { id: crypto.randomUUID(), strategyId: first.strategy_id, leverage: 1 }])
  }
  const removeScenario = (id: string) =>
    setScenarios(prev => prev.length > 1 ? prev.filter(s => s.id !== id) : prev)
  const updateScenario = (id: string, patch: Partial<Omit<Scenario, 'id'>>) =>
    setScenarios(prev => prev.map(s => s.id === id ? { ...s, ...patch } : s))

  // ── Trade inspector state ─────────────────────────────────────────────────

  const [activeStrategyId, setActiveStrategyId] = useState<string | null>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [tickerInput, setTickerInput] = useState('')
  const [tickerFilter, setTickerFilter] = useState('')
  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const PER_PAGE = 50

  const { data: tradesData, isLoading: tradesLoading } = useQuery<TradesResponse>({
    queryKey: ['backtest-trades', activeStrategyId, activeRunId, tickerFilter, page],
    queryFn: () =>
      api.get('/api/backtest/trades', {
        params: { strategy_id: activeStrategyId || undefined, run_id: activeRunId || undefined, ticker: tickerFilter || undefined, page, per_page: PER_PAGE },
      }).then(r => r.data),
  })

  // ── Derived ───────────────────────────────────────────────────────────────

  const activeCombos = useMemo((): Combo[] => {
    return scenarios.map(s => {
      const sc = equityCurves.find(c => c.strategy_id === s.strategyId)
      if (!sc) return null
      const colorIdx = equityCurves.findIndex(c => c.strategy_id === s.strategyId)
      return {
        id: s.id,
        strategyId: s.strategyId,
        strategyName: sc.strategy_name,
        leverage: s.leverage,
        color: STRATEGY_PALETTE[colorIdx % STRATEGY_PALETTE.length],
        dash: LEVERAGE_DASH[s.leverage],
        initialCapital: sc.initial_capital,
        baseCurve: sc.curve,
      }
    }).filter((c): c is Combo => c !== null)
  }, [scenarios, equityCurves])

  const leveragedCurves = useMemo((): Record<string, EquityPoint[]> => {
    const map: Record<string, EquityPoint[]> = {}
    for (const c of activeCombos)
      map[c.id] = applyLeverage(c.baseCurve, c.initialCapital, c.leverage)
    return map
  }, [activeCombos])

  const comboStats = useMemo(() =>
    activeCombos.map(c => ({ ...c, stats: computeStats(leveragedCurves[c.id] || [], c.initialCapital) })),
    [activeCombos, leveragedCurves],
  )

  const canLog = useMemo(() =>
    yMode === 'equity' && activeCombos.every(c => (leveragedCurves[c.id] || []).every(p => p.equity > 0)),
    [yMode, activeCombos, leveragedCurves],
  )
  const useLog = scaleMode === 'log' && canLog

  // Main full-period chart data (all scenarios in one chart)
  const mainChartData = useMemo(() => {
    const dateMap = new Map<string, Record<string, unknown>>()
    for (const combo of activeCombos) {
      const raw = leveragedCurves[combo.id] || []
      const curve = yMode === 'return' ? toReturnPct(raw, combo.initialCapital) : raw
      for (const pt of curve) {
        if (!dateMap.has(pt.date)) dateMap.set(pt.date, { date: pt.date })
        dateMap.get(pt.date)![combo.id] = pt.equity
      }
    }
    return Array.from(dateMap.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)))
  }, [activeCombos, leveragedCurves, yMode])

  // 6 timeline mini-charts (same scenarios, each period normalized to 0%)
  const windows = useMemo(() => buildWindows(equityCurves), [equityCurves])

  const periodData = useMemo(() => {
    return windows.map(w => {
      const dateMap = new Map<string, Record<string, unknown>>()
      const finalReturns: Record<string, number | null> = {}
      for (const combo of activeCombos) {
        const full = leveragedCurves[combo.id] || []
        const before = full.filter(p => p.date < w.start)
        const base = before.length > 0 ? before[before.length - 1].equity : combo.initialCapital
        const inRange = full.filter(p => p.date >= w.start && p.date <= w.end)
        for (const pt of inRange) {
          const key = pt.date.slice(5)
          if (!dateMap.has(key)) dateMap.set(key, { date: key })
          dateMap.get(key)![combo.id] = base > 0 ? (pt.equity - base) / base * 100 : 0
        }
        finalReturns[combo.id] = inRange.length > 0 && base > 0
          ? (inRange[inRange.length - 1].equity - base) / base * 100 : null
      }
      const data = Array.from(dateMap.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)))
      return { ...w, data, finalReturns }
    })
  }, [windows, activeCombos, leveragedCurves])

  const trades = tradesData?.trades || []
  const totalTrades = tradesData?.total || 0
  const totalPages = Math.ceil(totalTrades / PER_PAGE)

  const mainYTickFmt = yMode === 'equity'
    ? (v: number) => `R$${(v / 1000).toFixed(0)}k`
    : (v: number) => `${v.toFixed(0)}%`

  // ── Render ────────────────────────────────────────────────────────────────

  const job = jobStatusData?.job ?? null
  const isJobActive = jobActive(job)

  return (
    <div className="space-y-6">

      {/* ── Backtest job status banner ────────────────────────────────── */}
      <div className="bg-slate-800 rounded-lg px-6 py-4 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          {isJobActive ? (
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse" />
          ) : job?.status === 'completed' ? (
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-green-500" />
          ) : job?.status === 'failed' ? (
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-red-500" />
          ) : (
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-slate-600" />
          )}
          <div>
            {isJobActive && (
              <p className="text-sm text-yellow-400 font-medium">
                {job?.status === 'pending' ? 'Backtest queued…' : 'Running backtest…'}
              </p>
            )}
            {!isJobActive && job?.status === 'completed' && (
              <p className="text-sm text-green-400 font-medium">
                Backtest complete — {(job.total_trades ?? 0).toLocaleString()} trades
              </p>
            )}
            {!isJobActive && job?.status === 'failed' && (
              <p className="text-sm text-red-400 font-medium">
                Backtest failed: {job.error_message ?? 'unknown error'}
              </p>
            )}
            {!job && (
              <p className="text-sm text-slate-400">No backtest job found</p>
            )}
            <p className="text-xs text-slate-500">
              {(jobStatusData?.total_backtest_trades ?? 0).toLocaleString()} total backtest trades in DB
              {job?.completed_at && ` · last run ${new Date(job.completed_at).toLocaleDateString()}`}
            </p>
          </div>
        </div>
        <button
          onClick={triggerBacktest}
          disabled={triggering || isJobActive}
          className="px-4 py-2 text-sm rounded bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 disabled:cursor-not-allowed transition font-medium"
        >
          {isJobActive ? 'Running…' : triggering ? 'Starting…' : 'Re-run Backtest'}
        </button>
      </div>

      {/* ── Scenario Analysis + main chart ───────────────────────────── */}
      <div className="bg-slate-800 rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-lg font-semibold">Scenario Analysis</h2>
            <p className="text-slate-400 text-sm">All scenarios together — full period</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex rounded overflow-hidden border border-slate-600">
              {(['equity', 'return'] as const).map(m => (
                <button key={m} onClick={() => setYMode(m)}
                  className={`px-3 py-1.5 text-xs transition ${yMode === m ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-700'}`}>
                  {m === 'equity' ? 'Equity (R$)' : 'Return (%)'}
                </button>
              ))}
            </div>
            <div className="flex rounded overflow-hidden border border-slate-600">
              {(['linear', 'log'] as const).map(m => (
                <button key={m}
                  onClick={() => (canLog || m === 'linear') ? setScaleMode(m) : undefined}
                  className={`px-3 py-1.5 text-xs transition ${scaleMode === m ? 'bg-blue-600 text-white' : !canLog && m === 'log' ? 'text-slate-600 cursor-not-allowed' : 'text-slate-300 hover:bg-slate-700'}`}>
                  {m.charAt(0).toUpperCase() + m.slice(1)}
                </button>
              ))}
            </div>
            <button onClick={() => { setYMode('return'); setScaleMode('linear') }}
              className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 rounded border border-slate-600 text-slate-300 transition">
              Reset
            </button>
          </div>
        </div>

        {/* Scenario rows */}
        <div className="px-6 pt-4 space-y-2">
          {scenarios.map(scenario => {
            const cs = comboStats.find(c => c.id === scenario.id)
            const colorIdx = equityCurves.findIndex(e => e.strategy_id === scenario.strategyId)
            const color = STRATEGY_PALETTE[colorIdx % STRATEGY_PALETTE.length]
            return (
              <div key={scenario.id} className="flex items-center gap-3 flex-wrap">
                <DashLine dash={LEVERAGE_DASH[scenario.leverage]} color={color} width={32} />
                <select value={scenario.strategyId}
                  onChange={e => updateScenario(scenario.id, { strategyId: e.target.value })}
                  className="bg-slate-700 border border-slate-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-blue-500">
                  {equityCurves.map(sc => (
                    <option key={sc.strategy_id} value={sc.strategy_id}>{sc.strategy_name}</option>
                  ))}
                </select>
                <div className="flex gap-1">
                  {LEVERAGE_OPTIONS.map(lev => (
                    <button key={lev} onClick={() => updateScenario(scenario.id, { leverage: lev })}
                      className={`px-2 py-1 rounded text-xs transition ${scenario.leverage === lev ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`}>
                      {lev}x
                    </button>
                  ))}
                </div>
                {cs && (
                  <div className="flex items-center gap-4 text-xs flex-wrap">
                    <span>Return: <span className={cs.stats.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}>{fmtPct(cs.stats.totalReturn)}</span></span>
                    <span>Max DD: <span className="text-red-400">{fmtPct(-cs.stats.maxDrawdown)}</span></span>
                    <span>Sharpe: <span className={cs.stats.sharpe >= 1 ? 'text-blue-400' : 'text-slate-300'}>{cs.stats.sharpe.toFixed(2)}</span></span>
                    <span>Final: <span className={cs.stats.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}>{fmtBrl(cs.initialCapital * (1 + cs.stats.totalReturn / 100))}</span></span>
                    {cs.stats.lowestEquity <= 0 && <span className="text-red-500">⚠ margin call</span>}
                  </div>
                )}
                <button onClick={() => removeScenario(scenario.id)} className="ml-auto text-slate-500 hover:text-red-400 transition text-lg leading-none">×</button>
              </div>
            )
          })}
          <button onClick={addScenario} className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 transition py-1">
            <span className="text-lg leading-none">+</span> Add Scenario
          </button>
        </div>

        {/* Main combined chart */}
        <div className="px-2 pt-4 pb-2">
          {mainChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={380}>
              <LineChart data={mainChartData} margin={{ top: 8, right: 24, bottom: 8, left: 12 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#475569' }} tickLine={false}
                  interval={Math.floor(mainChartData.length / 12)} />
                <YAxis scale={useLog ? 'log' : 'linear'} domain={useLog ? ['auto', 'auto'] : undefined}
                  tickFormatter={mainYTickFmt} tick={{ fontSize: 10, fill: '#475569' }} tickLine={false} axisLine={false} width={52} />
                {yMode === 'return' && <ReferenceLine y={0} stroke="#334155" strokeDasharray="4 4" />}
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                  formatter={(v: number, key: string) => {
                    const c = activeCombos.find(x => x.id === key)
                    const lbl = c ? `${c.strategyName}${c.leverage > 1 ? ` ${c.leverage}x` : ''}` : key
                    return [yMode === 'equity' ? fmtBrl(v) : `${v.toFixed(2)}%`, lbl]
                  }}
                  labelStyle={{ color: '#64748b', fontSize: 11 }}
                />
                {activeCombos.map(c => (
                  <Line key={c.id} type="monotone" dataKey={c.id} stroke={c.color}
                    strokeWidth={2} dot={false} connectNulls strokeDasharray={c.dash} name={c.id} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-64 text-slate-500">
              {equityCurves.length === 0 ? 'Run a backtest first to see results' : 'No data available'}
            </div>
          )}
        </div>

        {activeCombos.length > 0 && (
          <div className="px-6 pb-4 flex flex-wrap gap-4 justify-center">
            {activeCombos.map(c => (
              <div key={c.id} className="flex items-center gap-1.5 text-xs text-slate-400">
                <DashLine dash={c.dash} color={c.color} width={20} />
                {c.strategyName}{c.leverage > 1 ? ` ${c.leverage}x` : ''}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── 6 timeline mini-charts ────────────────────────────────────── */}
      {windows.length > 0 && activeCombos.length > 0 && (
        <div>
          <div className="mb-3">
            <h2 className="text-lg font-semibold">Timeline Breakdown</h2>
            <p className="text-slate-400 text-sm">Same scenarios — % return from start of each period (for correlation analysis)</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {periodData.map(pd => (
              <PeriodMiniChart key={pd.label} win={pd} data={pd.data} combos={activeCombos} finalReturns={pd.finalReturns} />
            ))}
          </div>
        </div>
      )}

      {/* ── Full-period metrics table ─────────────────────────────────── */}
      {comboStats.length > 0 && (
        <div className="bg-slate-800 rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-700">
            <h2 className="text-lg font-semibold">Full-Period Metrics</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-left text-xs uppercase tracking-wide">
                  <th className="px-4 py-3">Scenario</th>
                  <th className="px-4 py-3 text-right">Signals</th>
                  <th className="px-4 py-3 text-right">Win Rate</th>
                  <th className="px-4 py-3 text-right">Total Return</th>
                  <th className="px-4 py-3 text-right">Ann. Return</th>
                  <th className="px-4 py-3 text-right">Max Drawdown</th>
                  <th className="px-4 py-3 text-right">Sharpe</th>
                  <th className="px-4 py-3 text-right">Calmar</th>
                  <th className="px-4 py-3 text-right">Final PnL</th>
                </tr>
              </thead>
              <tbody>
                {comboStats.map(c => {
                  const base = summary.find(s => s.strategy_id === c.strategyId)
                  return (
                    <tr key={c.id} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <DashLine dash={c.dash} color={c.color} width={24} />
                          <span className="font-medium">{c.strategyName}</span>
                          {c.leverage > 1 && (
                            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${c.leverage <= 2 ? 'bg-yellow-900/60 text-yellow-300' : c.leverage <= 3 ? 'bg-orange-900/60 text-orange-300' : 'bg-red-900/60 text-red-300'}`}>
                              {c.leverage}x
                            </span>
                          )}
                          {c.stats.lowestEquity <= 0 && <span className="text-xs text-red-500">⚠</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-300">{base?.total_trades ?? '—'}</td>
                      <td className={`px-4 py-3 text-right ${base && base.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>{base ? `${base.win_rate.toFixed(1)}%` : '—'}</td>
                      <td className={`px-4 py-3 text-right font-mono ${c.stats.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtPct(c.stats.totalReturn)}</td>
                      <td className={`px-4 py-3 text-right font-mono ${c.stats.annReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtPct(c.stats.annReturn)}</td>
                      <td className="px-4 py-3 text-right font-mono text-red-400">-{c.stats.maxDrawdown.toFixed(1)}%</td>
                      <td className={`px-4 py-3 text-right ${c.stats.sharpe >= 1 ? 'text-blue-400' : c.stats.sharpe >= 0 ? 'text-slate-300' : 'text-red-400'}`}>{c.stats.sharpe.toFixed(2)}</td>
                      <td className={`px-4 py-3 text-right ${c.stats.calmar >= 1 ? 'text-blue-400' : c.stats.calmar >= 0 ? 'text-slate-300' : 'text-red-400'}`}>{c.stats.calmar.toFixed(2)}</td>
                      <td className={`px-4 py-3 text-right font-mono ${c.stats.totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtBrl(c.initialCapital * c.stats.totalReturn / 100)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Parameter sweep runs ──────────────────────────────────────── */}
      {runs.length > 0 && (
        <div className="bg-slate-800 rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Parameter Sweep Runs</h2>
            <span className="text-slate-400 text-xs">{runs.length} runs — click to filter trades</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-slate-400 text-left text-xs uppercase tracking-wide">
                  <th className="px-6 py-3">Run</th><th className="px-4 py-3">Parameters</th>
                  <th className="px-4 py-3 text-right">Signals</th><th className="px-4 py-3 text-right">Win Rate</th>
                  <th className="px-4 py-3 text-right">Avg Return</th><th className="px-4 py-3 text-right">PnL (sim)</th>
                  <th className="px-4 py-3">Date</th>
                </tr>
              </thead>
              <tbody>
                {runs.map(r => (
                  <tr key={r.id} onClick={() => { setActiveRunId(activeRunId === r.id ? null : r.id); setPage(1) }}
                    className={`border-b border-slate-700/50 cursor-pointer transition ${activeRunId === r.id ? 'bg-blue-900/30' : 'hover:bg-slate-700/20'}`}>
                    <td className="px-6 py-3 font-medium">{r.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">{Object.entries(r.params).map(([k, v]) => `${k}=${v}`).join(', ')}</td>
                    <td className="px-4 py-3 text-right">{r.total_trades.toLocaleString()}</td>
                    <td className={`px-4 py-3 text-right ${r.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>{r.win_rate.toFixed(1)}%</td>
                    <td className={`px-4 py-3 text-right font-mono ${r.avg_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtPct(r.avg_return_pct, 3)}</td>
                    <td className={`px-4 py-3 text-right font-mono ${r.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtBrl(r.total_pnl)}</td>
                    <td className="px-4 py-3 text-slate-400 text-xs">{new Date(r.created_at).toLocaleDateString('pt-BR')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Trade Inspector ───────────────────────────────────────────── */}
      <div className="bg-slate-800 rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-lg font-semibold">Trade Inspector</h2>
            <div className="flex gap-1 flex-wrap">
              <button onClick={() => { setActiveStrategyId(null); setPage(1) }}
                className={`px-3 py-1 rounded text-xs transition ${!activeStrategyId ? 'bg-blue-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}>All</button>
              {summary.map((s, i) => (
                <button key={s.strategy_id} onClick={() => { setActiveStrategyId(activeStrategyId === s.strategy_id ? null : s.strategy_id); setPage(1) }}
                  className={`px-3 py-1 rounded text-xs transition ${activeStrategyId === s.strategy_id ? 'text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'}`}
                  style={activeStrategyId === s.strategy_id ? { backgroundColor: STRATEGY_PALETTE[i % STRATEGY_PALETTE.length] } : {}}>
                  {s.strategy_name}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 ml-auto flex-wrap">
              <input type="text" placeholder="Ticker…" value={tickerInput} onChange={e => setTickerInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { setTickerFilter(tickerInput); setPage(1) } }}
                className="px-3 py-1.5 bg-slate-700 rounded text-sm w-28 border border-slate-600 focus:outline-none focus:border-blue-500" />
              <button onClick={() => { setTickerFilter(tickerInput); setPage(1) }} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-xs transition">Search</button>
              {(tickerFilter || activeRunId) && (
                <button onClick={() => { setTickerFilter(''); setTickerInput(''); setActiveRunId(null); setPage(1) }} className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-xs text-slate-400 transition">Clear</button>
              )}
              <span className="text-slate-400 text-xs">{totalTrades.toLocaleString()} total</span>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-left text-xs uppercase tracking-wide">
                <th className="px-4 py-3">Date</th>
                {!activeStrategyId && <th className="px-4 py-3">Strategy</th>}
                <th className="px-4 py-3">Ticker</th><th className="px-4 py-3">Signal</th>
                <th className="px-4 py-3 text-right">Gap%</th><th className="px-4 py-3 text-right">Entry</th>
                <th className="px-4 py-3 text-right">Exit</th><th className="px-4 py-3 text-right">Return%</th>
                <th className="px-4 py-3 text-right">PnL</th>
              </tr>
            </thead>
            <tbody>
              {tradesLoading && <tr><td colSpan={!activeStrategyId ? 9 : 8} className="text-center py-8 text-slate-400">Loading…</td></tr>}
              {!tradesLoading && trades.length === 0 && <tr><td colSpan={!activeStrategyId ? 9 : 8} className="text-center py-8 text-slate-400">No trades found</td></tr>}
              {trades.map(trade => (
                <>
                  <tr key={trade.id} onClick={() => setExpandedId(expandedId === trade.id ? null : trade.id)}
                    className={`border-b border-slate-700/40 cursor-pointer transition ${expandedId === trade.id ? 'bg-slate-700/50' : 'hover:bg-slate-700/25'}`}>
                    <td className="px-4 py-2.5 text-slate-300">{trade.trade_date}</td>
                    {!activeStrategyId && <td className="px-4 py-2.5"><span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">{trade.strategy_name}</span></td>}
                    <td className="px-4 py-2.5 font-mono font-bold">{trade.ticker}</td>
                    <td className="px-4 py-2.5"><span className={`text-xs font-semibold px-2 py-0.5 rounded ${trade.signal_type === 'LONG' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'}`}>{trade.signal_type}</span></td>
                    <td className={`px-4 py-2.5 text-right font-mono ${trade.gap_pct > 0 ? 'text-orange-400' : 'text-blue-400'}`}>{trade.gap_pct > 0 ? '+' : ''}{trade.gap_pct.toFixed(2)}%</td>
                    <td className="px-4 py-2.5 text-right font-mono text-slate-300">R${trade.entry_price.toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-slate-300">R${trade.exit_price.toFixed(2)}</td>
                    <td className={`px-4 py-2.5 text-right font-mono font-semibold ${trade.net_return_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>{trade.net_return_pct > 0 ? '+' : ''}{trade.net_return_pct.toFixed(3)}%</td>
                    <td className={`px-4 py-2.5 text-right font-mono ${trade.pnl > 0 ? 'text-green-400' : 'text-red-400'}`}>{fmtBrl(trade.pnl)}</td>
                  </tr>
                  {expandedId === trade.id && (
                    <tr key={`${trade.id}-exp`} className="bg-slate-700/30">
                      <td colSpan={!activeStrategyId ? 9 : 8} className="px-6 py-3">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                          <div><span className="text-slate-400">Strategy</span><div className="text-white font-medium">{trade.strategy_name}</div></div>
                          <div><span className="text-slate-400">Position Size (sim)</span><div className="text-white font-mono">{fmtBrl(trade.position_size)}</div></div>
                          <div><span className="text-slate-400">Intended Size</span><div className="text-white font-mono">{fmtBrl(trade.intended_position_size || trade.position_size)}</div></div>
                          <div><span className="text-slate-400">Liquidity Cap</span><div className="text-white font-mono">{trade.liquidity_cap_brl ? fmtBrl(trade.liquidity_cap_brl) : '—'}</div></div>
                          <div><span className="text-slate-400">Cap Used</span><div className="text-white font-mono">{trade.capacity_used_pct ? `${trade.capacity_used_pct.toFixed(1)}%` : '—'}</div></div>
                          <div><span className="text-slate-400">Gap</span><div className={`font-mono font-semibold ${trade.gap_pct > 0 ? 'text-orange-400' : 'text-blue-400'}`}>{trade.gap_pct > 0 ? '+' : ''}{trade.gap_pct.toFixed(4)}%</div></div>
                          <div><span className="text-slate-400">Run</span><div className="text-white">{trade.backtest_run_id ? (runs.find(r => r.id === trade.backtest_run_id)?.name || trade.backtest_run_id.slice(0, 8) + '…') : 'Default'}</div></div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="px-6 py-4 border-t border-slate-700 flex items-center justify-between text-sm">
            <span className="text-slate-400">{((page - 1) * PER_PAGE) + 1}–{Math.min(page * PER_PAGE, totalTrades)} of {totalTrades.toLocaleString()}</span>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1.5 bg-slate-700 rounded disabled:opacity-40 hover:bg-slate-600 transition text-xs">← Prev</button>
              <span className="text-slate-400 text-xs px-1">{page} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="px-3 py-1.5 bg-slate-700 rounded disabled:opacity-40 hover:bg-slate-600 transition text-xs">Next →</button>
            </div>
          </div>
        )}
      </div>

    </div>
  )
}

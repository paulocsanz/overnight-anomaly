import { useQuery } from '@tanstack/react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { api } from '../api'

export default function Home() {
  const { data: performance, isLoading } = useQuery({
    queryKey: ['performance'],
    queryFn: () => api.get('/api/performance').then(r => r.data),
  })

  const { data: equityCurve = [] } = useQuery({
    queryKey: ['equity-curve'],
    queryFn: () => api.get('/api/equity-curve').then(r => r.data),
    refetchInterval: 60_000,
  })

  if (isLoading) return <div className="text-center py-8">Loading...</div>

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Total Trades</div>
          <div className="text-3xl font-bold text-white">{performance?.total_trades || 0}</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Win Rate</div>
          <div className="text-3xl font-bold text-green-400">{(performance?.win_rate || 0).toFixed(1)}%</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Sharpe Ratio</div>
          <div className="text-3xl font-bold text-blue-400">{(performance?.sharpe_ratio || 0).toFixed(2)}</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Cumulative Return</div>
          <div className="text-3xl font-bold text-purple-400">{(performance?.cumulative_return || 0).toFixed(2)}%</div>
        </div>
      </div>

      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Equity Curve</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={equityCurve}>
            <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
            <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 11 }} />
            <YAxis stroke="#94a3b8" tickFormatter={(v) => `R$${(v/1000).toFixed(0)}k`} />
            <Tooltip
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
              formatter={(v: number, name: string) => [`R$${v.toFixed(2)}`, name === 'simulated' ? 'Simulated' : 'Real']}
            />
            <Legend />
            <Line type="monotone" dataKey="simulated" stroke="#3b82f6" strokeWidth={2} dot={false} name="Simulated" />
            <Line type="monotone" dataKey="real" stroke="#10b981" strokeWidth={2} dot={false} name="Real" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'
import { api } from '../api'

export default function Performance() {
  const { data: performance } = useQuery({
    queryKey: ['performance'],
    queryFn: () => api.get('/api/performance').then(r => r.data),
  })

  const mockMonthlyData = [
    { month: 'Jan', return: 5.2, trades: 12 },
    { month: 'Feb', return: 3.8, trades: 10 },
    { month: 'Mar', return: 4.1, trades: 11 },
    { month: 'Apr', return: 1.5, trades: 8 },
    { month: 'May', return: 2.9, trades: 9 },
    { month: 'Jun', return: 1.8, trades: 7 },
  ]

  const mockDrawdown = [
    { date: '2026-01-01', equity: 100000 },
    { date: '2026-01-15', equity: 98000 },
    { date: '2026-02-01', equity: 105000 },
    { date: '2026-03-01', equity: 110500 },
    { date: '2026-04-01', equity: 112000 },
    { date: '2026-05-01', equity: 115200 },
    { date: '2026-06-09', equity: 119800 },
  ]

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Avg Monthly Return</div>
          <div className="text-3xl font-bold text-blue-400">{(performance?.avg_return || 0).toFixed(2)}%</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Best Trade</div>
          <div className="text-3xl font-bold text-green-400">+12.5%</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Max Drawdown</div>
          <div className="text-3xl font-bold text-red-400">-3.2%</div>
        </div>
      </div>

      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Monthly Returns</h2>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={mockMonthlyData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
            <XAxis dataKey="month" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }} />
            <Legend />
            <Bar dataKey="return" fill="#3b82f6" name="Return %" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Equity Curve with Drawdown</h2>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={mockDrawdown}>
            <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
            <XAxis dataKey="date" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }} />
            <Legend />
            <Line type="monotone" dataKey="equity" stroke="#10b981" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

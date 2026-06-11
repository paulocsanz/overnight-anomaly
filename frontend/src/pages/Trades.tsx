import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

export default function Trades() {
  const { data: trades = [] } = useQuery({
    queryKey: ['trades'],
    queryFn: () => api.get('/api/trades').then(r => r.data),
  })

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Recent Trades</h2>

      <div className="overflow-x-auto">
        <table className="w-full bg-slate-800 rounded-lg overflow-hidden">
          <thead className="bg-slate-700">
            <tr>
              <th className="px-6 py-3 text-left text-sm font-semibold">Date</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Ticker</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Signal</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Gap %</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Return %</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">P&L</th>
              <th className="px-6 py-3 text-left text-sm font-semibold">Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade: { id: string; trade_date: string; ticker: string; signal: string; gap_pct: number; net_return_pct: number | null; pnl: number | null; status: string }) => (
              <tr key={trade.id} className="border-t border-slate-700 hover:bg-slate-700 transition">
                <td className="px-6 py-4">{trade.trade_date}</td>
                <td className="px-6 py-4 font-semibold">{trade.ticker}</td>
                <td className="px-6 py-4">
                  <span className={trade.signal === 'SHORT' ? 'text-red-400' : 'text-green-400'}>
                    {trade.signal}
                  </span>
                </td>
                <td className="px-6 py-4">{trade.gap_pct.toFixed(2)}%</td>
                <td className="px-6 py-4">{(trade.net_return_pct ?? 0).toFixed(2)}%</td>
                <td className={`px-6 py-4 ${(trade.pnl ?? 0) > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  R${(trade.pnl ?? 0).toFixed(2)}
                </td>
                <td className="px-6 py-4">{trade.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

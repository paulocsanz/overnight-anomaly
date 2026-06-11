import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'

export default function TaxReports() {
  const [selectedYear, setSelectedYear] = useState(2026)
  const { data: taxReport } = useQuery({
    queryKey: ['tax-report', selectedYear],
    queryFn: () => api.get(`/api/tax-report/${selectedYear}`).then(r => r.data),
  })

  return (
    <div className="space-y-6">
      <div className="flex gap-4 mb-6">
        <label className="text-slate-300">Select Year:</label>
        <select
          value={selectedYear}
          onChange={e => setSelectedYear(parseInt(e.target.value))}
          className="bg-slate-700 border border-slate-600 rounded px-4 py-2 text-white"
        >
          <option value={2024}>2024</option>
          <option value={2025}>2025</option>
          <option value={2026}>2026</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Total Trades</div>
          <div className="text-3xl font-bold text-white">{taxReport?.total_trades || 0}</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Gross P&L</div>
          <div className="text-3xl font-bold text-blue-400">R${(taxReport?.gross_pnl || 0).toFixed(2)}</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Commissions</div>
          <div className="text-3xl font-bold text-red-400">-R${(taxReport?.commissions || 0).toFixed(2)}</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-6">
          <div className="text-slate-400 text-sm">Net P&L</div>
          <div className="text-3xl font-bold text-green-400">R${(taxReport?.net_pnl || 0).toFixed(2)}</div>
        </div>
      </div>

      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Tax Summary</h2>
        <div className="space-y-4">
          <div className="flex justify-between items-center pb-4 border-b border-slate-700">
            <span className="text-slate-300">Tax Owed (20% on profits)</span>
            <span className="text-xl font-bold text-red-400">R${(taxReport?.tax_owed || 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between items-center pb-4 border-b border-slate-700">
            <span className="text-slate-300">Filing Deadline</span>
            <span className="font-semibold">Last business day of April {selectedYear + 1}</span>
          </div>
          <div className="text-sm text-slate-400 mt-4">
            <p>Brazilian day trading tax: 20% on net profits</p>
            <p>Report to IRPF (Federal Income Tax Return)</p>
            <p>Keep all trade confirmations for 5 years</p>
          </div>
        </div>
      </div>

      <div className="bg-blue-900 border border-blue-700 rounded-lg p-4 text-blue-100">
        <p className="text-sm">
          ℹ️ This is a summary for reference. Always consult with a tax professional (contador) for accurate Brazilian tax filing.
        </p>
      </div>
    </div>
  )
}

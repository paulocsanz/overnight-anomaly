import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'

export default function Strategies() {
  const [newStrategy, setNewStrategy] = useState({ name: '', description: '' })
  const { data: strategies = [], refetch } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.get('/api/strategies').then(r => r.data),
  })

  const handleCreate = async () => {
    if (newStrategy.name && newStrategy.description) {
      await api.post('/api/strategies', {
        ...newStrategy,
        signal_config: {},
        trading_rules: {},
      })
      refetch()
      setNewStrategy({ name: '', description: '' })
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-bold mb-4">Create New Strategy</h2>
        <div className="space-y-4">
          <input
            type="text"
            placeholder="Strategy Name"
            value={newStrategy.name}
            onChange={e => setNewStrategy({ ...newStrategy, name: e.target.value })}
            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400"
          />
          <textarea
            placeholder="Description"
            value={newStrategy.description}
            onChange={e => setNewStrategy({ ...newStrategy, description: e.target.value })}
            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400"
          />
          <button
            onClick={handleCreate}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded transition"
          >
            Create Strategy
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {strategies.map((strategy: { id: string; name: string; description?: string }) => (
          <div key={strategy.id} className="bg-slate-800 rounded-lg p-6">
            <h3 className="text-lg font-bold">{strategy.name}</h3>
            <p className="text-slate-400 mt-2">{strategy.description}</p>
            <div className="mt-4 flex gap-2">
              <button className="text-blue-400 hover:text-blue-300">Edit</button>
              <button className="text-red-400 hover:text-red-300">Delete</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

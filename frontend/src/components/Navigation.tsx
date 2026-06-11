interface NavigationProps {
  currentPage: string
  setCurrentPage: (page: string) => void
  onLogout?: () => void
}

export default function Navigation({ currentPage, setCurrentPage, onLogout }: NavigationProps) {
  const links = [
    { id: 'home', label: 'Home' },
    { id: 'strategies', label: 'Strategies' },
    { id: 'backtest', label: 'Backtest' },
    { id: 'trades', label: 'Trades' },
    { id: 'performance', label: 'Performance' },
    { id: 'tax', label: 'Tax Reports' },
  ]

  return (
    <nav className="bg-slate-800 border-b border-slate-700">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <div className="font-bold text-xl text-blue-400">Trading SaaS</div>
            <div className="flex gap-1">
              {links.map(link => (
                <button
                  key={link.id}
                  onClick={() => setCurrentPage(link.id)}
                  className={`px-4 py-2 rounded transition ${
                    currentPage === link.id
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  {link.label}
                </button>
              ))}
            </div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className="px-4 py-2 text-slate-300 hover:text-white hover:bg-slate-700 rounded transition"
            >
              Logout
            </button>
          )}
        </div>
      </div>
    </nav>
  )
}

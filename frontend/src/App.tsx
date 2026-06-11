import { useState, useEffect } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Navigation from './components/Navigation'
import Login from './pages/Login'
import Home from './pages/Home'
import Strategies from './pages/Strategies'
import Trades from './pages/Trades'
import Performance from './pages/Performance'
import TaxReports from './pages/TaxReports'
import Backtest from './pages/Backtest'

const queryClient = new QueryClient()

export default function App() {
  const [currentPage, setCurrentPage] = useState('home')
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))

  useEffect(() => {
    // Initialization complete
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setCurrentPage('home')
  }

  if (!token) {
    return <Login onLoginSuccess={setToken} />
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'home':
        return <Home />
      case 'strategies':
        return <Strategies />
      case 'trades':
        return <Trades />
      case 'performance':
        return <Performance />
      case 'tax':
        return <TaxReports />
      case 'backtest':
        return <Backtest />
      default:
        return <Home />
    }
  }

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-900 text-slate-100">
        <Navigation currentPage={currentPage} setCurrentPage={setCurrentPage} onLogout={handleLogout} />
        <main className="container mx-auto px-4 py-8">
          {renderPage()}
        </main>
      </div>
    </QueryClientProvider>
  )
}

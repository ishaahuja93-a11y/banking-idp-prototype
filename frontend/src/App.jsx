import { Routes, Route, NavLink } from 'react-router-dom'
import { FileText, LayoutDashboard, Upload, CheckSquare } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import UploadPage from './pages/UploadPage'
import ReviewPage from './pages/ReviewPage'
import DocumentDetail from './pages/DocumentDetail'

const NAV = [
  { to: '/',       icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: Upload,          label: 'Upload'    },
  { to: '/review', icon: CheckSquare,     label: 'Review'    },
]

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-blue-900 text-white px-6 py-3 flex items-center gap-3 shadow-lg">
        <FileText className="w-6 h-6 text-yellow-400" />
        <span className="font-bold text-lg">IDP Banking</span>
        <span className="text-blue-300 text-sm hidden sm:inline">Intelligent Document Processing</span>
        <nav className="ml-auto flex gap-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  isActive ? 'bg-white/20 text-white' : 'text-blue-200 hover:bg-white/10'
                }`
              }>
              <Icon className="w-4 h-4" />{label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1 px-4 md:px-6 py-6 max-w-7xl mx-auto w-full">
        <Routes>
          <Route path="/"              element={<Dashboard />}      />
          <Route path="/upload"        element={<UploadPage />}     />
          <Route path="/review"        element={<ReviewPage />}     />
          <Route path="/documents/:id" element={<DocumentDetail />} />
        </Routes>
      </main>
    </div>
  )
}

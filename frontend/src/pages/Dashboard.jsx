import { useEffect, useState } from 'react'
import { getDashboardStats } from '../api'
import { Link } from 'react-router-dom'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { FileText, CheckCircle, TrendingUp, AlertTriangle } from 'lucide-react'

const COLORS = ['#22c55e','#f59e0b','#ef4444','#3b82f6','#8b5cf6']

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  useEffect(() => {
    const load = () => getDashboardStats().then(r => setStats(r.data)).catch(() => {})
    load()
    const id = setInterval(load, 10000)
    return () => clearInterval(id)
  }, [])

  if (!stats) return <div className="flex items-center justify-center h-64 text-gray-400">Loading dashboard…</div>

  const typeData   = Object.entries(stats.by_type).map(([name, value]) => ({ name, value }))
  const statusData = Object.entries(stats.by_status).map(([name, value]) => ({ name, value }))
  const confData   = [
    { name: 'High ≥85%',   value: stats.confidence_buckets.high,   fill: '#22c55e' },
    { name: 'Med 60-84%',  value: stats.confidence_buckets.medium, fill: '#f59e0b' },
    { name: 'Low <60%',    value: stats.confidence_buckets.low,    fill: '#ef4444' },
  ]

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Document Processing Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Documents',    value: stats.total_documents,                      icon: FileText,     color: 'blue'   },
          { label: 'Auto-Accepted',      value: `${stats.auto_acceptance_rate}%`,            icon: CheckCircle,  color: 'green'  },
          { label: 'Avg Confidence',     value: `${Math.round(stats.average_confidence*100)}%`, icon: TrendingUp,color: 'purple' },
          { label: 'Human Corrections',  value: stats.total_corrections,                    icon: AlertTriangle,color: 'amber'  },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card flex items-center gap-4">
            <div className={`p-3 rounded-xl bg-${color}-100`}><Icon className={`w-6 h-6 text-${color}-600`} /></div>
            <div><div className="text-2xl font-bold">{value}</div><div className="text-xs text-gray-500">{label}</div></div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card"><h3 className="font-semibold text-gray-700 mb-3">Confidence Distribution</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart><Pie data={confData} dataKey="value" cx="50%" cy="50%" outerRadius={65} label={({percent}) => `${Math.round(percent*100)}%`}>
              {confData.map((e,i) => <Cell key={i} fill={e.fill} />)}
            </Pie><Tooltip /></PieChart>
          </ResponsiveContainer>
        </div>
        <div className="card"><h3 className="font-semibold text-gray-700 mb-3">Documents by Type</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={typeData}><XAxis dataKey="name" tick={{fontSize:10}} /><YAxis /><Tooltip />
              <Bar dataKey="value" fill="#1e3a5f" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card"><h3 className="font-semibold text-gray-700 mb-3">Status Breakdown</h3>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart><Pie data={statusData} dataKey="value" cx="50%" cy="50%" outerRadius={65} label>
              {statusData.map((_,i) => <Cell key={i} fill={COLORS[i%COLORS.length]} />)}
            </Pie><Tooltip /><Legend /></PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="card">
        <h3 className="font-semibold text-gray-700 mb-3">Recent Documents</h3>
        {stats.recent.length === 0
          ? <p className="text-gray-400 text-sm">No documents yet — upload one to get started.</p>
          : <table className="w-full text-sm"><thead><tr className="text-left text-gray-500 border-b">
              {['Filename','Type','Confidence','Status','Action'].map(h => <th key={h} className="pb-2 pr-4">{h}</th>)}
            </tr></thead><tbody>
              {stats.recent.map(d => (
                <tr key={d.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="py-2 pr-4 font-medium truncate max-w-[160px]">{d.filename}</td>
                  <td className="py-2 pr-4 capitalize">{d.doc_type}</td>
                  <td className="py-2 pr-4">{Math.round(d.overall_confidence*100)}%</td>
                  <td className="py-2 pr-4">
                    <span className={d.status==='auto_accepted'?'badge-green':d.status==='approved'?'badge-blue':d.status==='rejected'?'badge-red':'badge-amber'}>
                      {d.status.replace('_',' ')}
                    </span>
                  </td>
                  <td className="py-2"><Link to={`/documents/${d.id}`} className="text-blue-600 hover:underline text-xs">View →</Link></td>
                </tr>
              ))}
            </tbody></table>
        }
      </div>
    </div>
  )
}

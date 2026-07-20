import { useEffect, useState } from 'react'
import { listDocuments } from '../api'
import { Link } from 'react-router-dom'

export default function ReviewPage() {
  const [docs, setDocs] = useState([])
  const [filter, setFilter] = useState('')

  useEffect(() => {
    const load = () => listDocuments(filter ? { status: filter } : {}).then(r => setDocs(r.data.documents)).catch(()=>{})
    load()
    const id = setInterval(load, 8000)
    return () => clearInterval(id)
  }, [filter])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">Review Queue</h1>
        <select value={filter} onChange={e => setFilter(e.target.value)} className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
          <option value="">All statuses</option>
          <option value="pending_review">Pending Review</option>
          <option value="auto_accepted">Auto Accepted</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>
      <div className="card overflow-hidden p-0">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b"><tr className="text-left text-gray-500">
            {['Filename','Type','Confidence','Status','Action'].map(h => <th key={h} className="px-4 py-3 font-medium">{h}</th>)}
          </tr></thead>
          <tbody>
            {docs.length === 0
              ? <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No documents yet. Upload one to get started.</td></tr>
              : docs.map(d => (
                <tr key={d.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium truncate max-w-[180px]">{d.filename}</td>
                  <td className="px-4 py-3 capitalize">{d.doc_type?.replace('_',' ')}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 bg-gray-200 rounded-full">
                        <div className="h-1.5 rounded-full" style={{width:`${Math.round(d.overall_confidence*100)}%`,background:d.overall_confidence>=0.85?'#22c55e':d.overall_confidence>=0.6?'#f59e0b':'#ef4444'}} />
                      </div>
                      <span>{Math.round(d.overall_confidence*100)}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3"><span className={d.status==='auto_accepted'?'badge-green':d.status==='approved'?'badge-blue':d.status==='rejected'?'badge-red':'badge-amber'}>{d.status.replace('_',' ')}</span></td>
                  <td className="px-4 py-3"><Link to={`/documents/${d.id}`} className="btn-primary text-xs py-1 px-3">{d.status==='pending_review'?'Review':'View'}</Link></td>
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>
    </div>
  )
}

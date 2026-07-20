import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getDocument, submitCorrection, submitReview, chatWithDocument } from '../api'
import toast from 'react-hot-toast'
import { MessageCircle, Edit3, CheckCircle, XCircle, ArrowUpRight, Send } from 'lucide-react'

function ConfBadge({ c, status }) {
  const pct = Math.round((c||0)*100)
  const s = status || (c>=0.85?'auto_accept':c>=0.6?'review_amber':'review_red')
  const cfg = {auto_accept:{cls:'badge-green',dot:'🟢'},review_amber:{cls:'badge-amber',dot:'🟡'},review_red:{cls:'badge-red',dot:'🔴'},human_verified:{cls:'badge-blue',dot:'🔵'}}[s]||{cls:'badge-amber',dot:'⚪'}
  return <span className={cfg.cls}>{cfg.dot} {pct}%</span>
}

export default function DocumentDetail() {
  const { id } = useParams(); const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [editing, setEditing] = useState({})
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState([])
  const [chatLoading, setChatLoading] = useState(false)

  const reload = () => getDocument(id).then(r => setDoc(r.data)).catch(() => navigate('/review'))
  useEffect(() => { reload() }, [id])

  const handleCorrect = async (name, orig, conf, newVal) => {
    if (!newVal || newVal === orig) { setEditing(p=>({...p,[name]:false})); return }
    try {
      await submitCorrection({doc_id:id,field_name:name,corrected_value:newVal,original_value:orig,original_confidence:conf})
      toast.success(`"${name}" updated`); setEditing(p=>({...p,[name]:false})); reload()
    } catch { toast.error('Correction failed') }
  }

  const handleReview = async (decision) => {
    try { await submitReview({doc_id:id,decision}); toast.success(`Document ${decision}`); reload() }
    catch { toast.error('Review failed') }
  }

  const sendChat = async () => {
    if (!chatInput.trim()) return
    const q = chatInput; setChatHistory(h=>[...h,{role:'user',text:q}]); setChatInput(''); setChatLoading(true)
    try { const r = await chatWithDocument(id,q); setChatHistory(h=>[...h,{role:'agent',text:r.data.answer}]) }
    catch { setChatHistory(h=>[...h,{role:'agent',text:'Error reaching agent.'}]) }
    finally { setChatLoading(false) }
  }

  if (!doc) return <div className="flex items-center justify-center h-64 text-gray-400">Loading…</div>
  const fields = doc.fields || {}
  const flagged  = Object.entries(fields).filter(([,v])=>v?.status==='review_amber'||v?.status==='review_red')
  const accepted = Object.entries(fields).filter(([,v])=>v?.status==='auto_accept'||v?.status==='human_verified')

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-gray-800">{doc.filename}</h1>
          <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
            <span className="capitalize font-medium text-gray-700">{doc.doc_type?.replace('_',' ')}</span>
            <span>•</span>
            <ConfBadge c={doc.overall_confidence} />
            <span>•</span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${doc.status==='auto_accepted'?'badge-green':doc.status==='approved'?'badge-blue':doc.status==='rejected'?'badge-red':'badge-amber'}`}>{doc.status.replace('_',' ')}</span>
          </div>
        </div>
        {doc.status === 'pending_review' && (
          <div className="flex gap-2">
            <button onClick={()=>handleReview('approved')} className="flex items-center gap-1 bg-green-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-green-700"><CheckCircle className="w-4 h-4"/>Approve</button>
            <button onClick={()=>handleReview('rejected')} className="flex items-center gap-1 bg-red-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-red-700"><XCircle className="w-4 h-4"/>Reject</button>
            <button onClick={()=>handleReview('escalated')} className="flex items-center gap-1 bg-amber-500 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-amber-600"><ArrowUpRight className="w-4 h-4"/>Escalate</button>
          </div>
        )}
      </div>

      {doc.summary && <div className="card bg-blue-50 border border-blue-100"><div className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">AI Summary</div><p className="text-gray-700 text-sm">{doc.summary}</p></div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {flagged.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-amber-700 mb-3">⚠ Needs Attention ({flagged.length} fields)</h3>
              <div className="divide-y">{flagged.map(([name,field]) => <FieldRow key={name} name={name} field={field} editMode={editing[name]} onEdit={()=>setEditing(p=>({...p,[name]:true}))} onSave={v=>handleCorrect(name,field.value,field.confidence,v)} onCancel={()=>setEditing(p=>({...p,[name]:false}))} />)}</div>
            </div>
          )}
          {accepted.length > 0 && (
            <div className="card">
              <h3 className="font-semibold text-green-700 mb-3">✓ Auto-Accepted ({accepted.length} fields)</h3>
              <div className="divide-y">{accepted.map(([name,field]) => <FieldRow key={name} name={name} field={field} editMode={editing[name]} onEdit={()=>setEditing(p=>({...p,[name]:true}))} onSave={v=>handleCorrect(name,field.value,field.confidence,v)} onCancel={()=>setEditing(p=>({...p,[name]:false}))} />)}</div>
            </div>
          )}
        </div>

        <div className="card flex flex-col" style={{height:'480px'}}>
          <h3 className="font-semibold text-gray-700 mb-3 flex items-center gap-2"><MessageCircle className="w-4 h-4 text-blue-500"/>Ask the Agent</h3>
          <div className="flex-1 overflow-y-auto space-y-2 mb-3 text-sm">
            {chatHistory.length===0 && <div className="text-gray-400 text-xs space-y-1"><p>Try asking:</p><p>• "What is the total amount?"</p><p>• "Who are the parties?"</p><p>• "What are the payment terms?"</p></div>}
            {chatHistory.map((m,i)=>(
              <div key={i} className={`rounded-lg px-3 py-2 ${m.role==='user'?'ml-4 bg-blue-50 border border-blue-100':'mr-4 bg-gray-50 border border-gray-200'}`}>
                <div className="text-xs font-semibold text-gray-400 mb-0.5">{m.role==='user'?'You':'🤖 Agent'}</div>
                <div className="text-gray-700">{m.text}</div>
              </div>
            ))}
            {chatLoading && <div className="text-gray-400 text-xs animate-pulse">Thinking…</div>}
          </div>
          <div className="flex gap-2">
            <input value={chatInput} onChange={e=>setChatInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendChat()} placeholder="Ask about this document…" className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300" />
            <button onClick={sendChat} disabled={chatLoading||!chatInput.trim()} className="btn-primary p-2"><Send className="w-4 h-4"/></button>
          </div>
        </div>
      </div>

      {doc.corrections?.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-gray-700 mb-3">Correction History</h3>
          <div className="divide-y text-sm">{doc.corrections.map((c,i)=>(
            <div key={i} className="py-2 flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-gray-400 flex-shrink-0"/>
              <span className="font-medium">{c.field_name}:</span>
              <span className="line-through text-gray-400">{c.original_value||'(empty)'}</span>
              <span className="text-green-700">→ {c.corrected_value}</span>
              <span className="text-gray-400 text-xs">({Math.round(c.original_confidence*100)}% → 100%)</span>
            </div>
          ))}</div>
        </div>
      )}
    </div>
  )
}

function FieldRow({ name, field, editMode, onEdit, onSave, onCancel }) {
  const [val, setVal] = useState(field?.value || '')
  return (
    <div className="py-2.5 flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium text-gray-500 capitalize">{name.replace(/_/g,' ')}</span>
          <ConfBadge c={field?.confidence} status={field?.status} />
        </div>
        {editMode
          ? <input autoFocus value={val} onChange={e=>setVal(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')onSave(val);if(e.key==='Escape')onCancel()}} className="w-full border border-blue-400 rounded px-2 py-1 text-sm focus:outline-none" />
          : <div className="text-sm text-gray-800 font-medium truncate">
              {field?.value!=null ? String(field.value) : <span className="text-gray-300 italic">Not found in document</span>}
              {field?.ambiguity_reason && <span className="ml-2 text-xs text-amber-600">⚠ {field.ambiguity_reason}</span>}
            </div>
        }
      </div>
      {editMode
        ? <div className="flex gap-1 flex-shrink-0">
            <button onClick={()=>onSave(val)} className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded hover:bg-green-200">Save</button>
            <button onClick={onCancel} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded hover:bg-gray-200">Cancel</button>
          </div>
        : <button onClick={onEdit} className="flex-shrink-0 text-gray-400 hover:text-blue-500 p-1"><Edit3 className="w-3.5 h-3.5"/></button>
      }
    </div>
  )
}

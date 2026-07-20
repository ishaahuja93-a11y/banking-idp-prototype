import axios from 'axios'
const api = axios.create({ baseURL: '/api' })
export const uploadDocument    = file => { const fd = new FormData(); fd.append('file', file); return api.post('/documents/upload', fd) }
export const listDocuments     = params => api.get('/documents', { params })
export const getDocument       = id => api.get(`/documents/${id}`)
export const submitCorrection  = p => api.post('/documents/correct', p)
export const submitReview      = p => api.post('/documents/review', p)
export const chatWithDocument  = (doc_id, message) => api.post('/documents/chat', { doc_id, message })
export const getDashboardStats = () => api.get('/dashboard/stats')

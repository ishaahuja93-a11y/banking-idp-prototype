import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import { uploadDocument } from '../api'
import toast from 'react-hot-toast'
import { Upload, FileText, CheckCircle, Loader } from 'lucide-react'

const SAMPLES = [
  { label: 'Invoice', type: 'invoice', content: `INVOICE\nInvoice #: INV-2024-001\nDate: 15 January 2024\nDue Date: 14 February 2024\n\nFrom: TechCorp Solutions Pvt Ltd\n42, Bandra Kurla Complex, Mumbai 400051\n\nTo: National Banking Corp\n\nLine Items:\n1. Cloud Infrastructure Services    INR 1,20,000\n2. Security Audit & Compliance      INR 45,000\n3. API Integration Support          INR 35,000\n\nSubtotal: INR 2,00,000\nGST (18%): INR 36,000\nTotal Amount Due: INR 2,36,000\n\nPayment Terms: Net 30 days\nBank: HDFC Bank | Account: 12345678901 | IFSC: HDFC0001234\nPO Reference: PO-BANK-2024-78` },
  { label: 'KYC Form', type: 'kyc', content: `KYC APPLICATION FORM\n\nFull Name: Priya Sharma\nDate of Birth: 12/03/1985\nGender: Female\nNationality: Indian\nOccupation: Senior Software Engineer\n\nPAN Card: ABCPS1234D\nAadhaar Number: 9876 5432 1098\n\nAddress: Flat 4B, Sunshine Apartments, Koramangala, Bengaluru - 560034\n\nPhone: +91 98765 43210\nEmail: priya.sharma@email.com\nAnnual Income: INR 18,00,000\nSource of Income: Salary\n\nRisk Classification: Low Risk\nPolitically Exposed Person: No` },
  { label: 'Contract', type: 'contract', content: `SERVICE AGREEMENT\n\nThis Agreement is entered into as of 1st February 2024\n\nBETWEEN: National Banking Corp ("Client")\nAND: FinTech Solutions Ltd ("Service Provider")\n\n1. SERVICES: Core banking API integration and 24x7 support.\n\n2. TERM: 1 February 2024 to 31 January 2026 (24 months).\n\n3. PAYMENT TERMS: INR 5,00,000 per month within 15 days of invoice.\n\n4. LIABILITY CAP: Maximum liability capped at INR 60,00,000.\n\n5. GOVERNING LAW: Laws of India, jurisdiction of courts in Mumbai.\n\n6. TERMINATION: 90 days written notice by either party.\n\n7. INDEMNITY: Each party indemnifies the other against third-party claims from their negligence.` },
]

export default function UploadPage() {
  const [uploading, setUploading] = useState(false)
  const [uploaded, setUploaded]   = useState(null)
  const navigate = useNavigate()

  const process = useCallback(async (file) => {
    setUploading(true); setUploaded(null)
    const tid = toast.loading('Extracting document fields…')
    try {
      const res = await api.post('/documents/upload', fd);
      const res = await uploadDocument(file)
      setUploaded(res.data)
      toast.success(`Extracted ${Object.keys(res.data.fields).length} fields from ${res.data.doc_type}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed')
    } finally { setUploading(false) }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: files => files[0] && process(files[0]),
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'] },
    multiple: false,
  })

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Upload Document</h1>
      <div {...getRootProps()} className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-colors ${isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'}`}>
        <input {...getInputProps()} />
        <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
        <p className="text-gray-600 font-medium">{isDragActive ? 'Drop file here…' : 'Drag & drop a document, or click to browse'}</p>
        <p className="text-gray-400 text-sm mt-1">PDF or TXT</p>
      </div>
    <div className="card">
        <h3 className="font-semibold text-gray-700 mb-3">Or load a sample document:</h3>
        <div className="grid grid-cols-3 gap-3">
          {SAMPLES.map(s => (
            <button key={s.type} onClick={() => { const blob = new Blob([s.content],{type:'text/plain'}); process(new File([blob],`sample-${s.type}.txt`,{type:'text/plain'})) }} disabled={uploading}
              className="border border-gray-200 rounded-lg p-3 text-left hover:bg-blue-50 hover:border-blue-300 transition-colors disabled:opacity-50">
              <FileText className="w-5 h-5 text-blue-600 mb-1" />
              <div className="font-medium text-sm">{s.label}</div>
            </button>
          ))}
        </div>
      </div>
      {uploading && <div className="card flex items-center gap-3"><Loader className="w-5 h-5 text-blue-500 animate-spin" /><div><div className="font-medium">Processing document…</div><div className="text-sm text-gray-500">AI extraction in progress</div></div></div>}
      {uploaded && (
        <div className="card border-l-4 border-l-green-500">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-500 flex-shrink-0" />
            <div>
              <div className="font-semibold">Extraction Complete</div>
              <div className="text-sm text-gray-600 mt-1">{uploaded.summary}</div>
              <div className="flex gap-4 mt-2 text-sm">
                <span><b>{Object.keys(uploaded.fields).length}</b> fields</span>
                <span><b>{Math.round(uploaded.overall_confidence*100)}%</b> confidence</span>
                <span className="capitalize"><b>{uploaded.doc_type}</b></span>
              </div>
              <button onClick={() => navigate(`/documents/${uploaded.id}`)} className="btn-primary mt-3 text-sm">Review Document →</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

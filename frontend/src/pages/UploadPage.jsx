import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import { Upload, FileText, CheckCircle, Loader2 } from 'lucide-react'

// API instance — works locally via Vite proxy and in production via VITE_API_URL
const BASE = import.meta.env.PROD
  ? (import.meta.env.VITE_API_URL || '')
  : '/api'

const api = axios.create({ baseURL: BASE })

const SAMPLES = [
  {
    label: 'Invoice',
    type: 'invoice',
    content: `INVOICE
Invoice #: INV-2026-001
Date: 01 July 2026
Due Date: 31 July 2026

From: TechCorp Solutions Pvt Ltd
      42, Bandra Kurla Complex, Mumbai 400051
      GSTIN: 27AAACT1234A1Z5

To: National Banking Corp, Mumbai

Line Items:
1. Cloud Infrastructure Services    INR 1,20,000
2. Security Audit and Compliance    INR  45,000
3. API Integration Support          INR  35,000
4. Monthly SLA Management           INR  15,000

Subtotal:      INR 2,15,000
GST (18%):     INR  38,700
Total Due:     INR 2,53,700

Payment Terms: Net 30 days
SWIFT Code: HDFCINBB
Bank: HDFC Bank
Account: 12345678901
IFSC: HDFC0001234
PO Reference: PO-BANK-2026-78`
  },
  {
    label: 'KYC Form',
    type: 'kyc',
    content: `KYC APPLICATION FORM

Full Name:      Priya Sharma
Date of Birth:  12/03/1985
Gender:         Female
Nationality:    Indian
Occupation:     Senior Software Engineer

PAN:     ABCPS1234D
Aadhaar: 9876 5432 1098
Passport: P1234567 (Expiry: 30-Nov-2029)

Address: Flat 4B, Sunshine Apts, Koramangala, Bengaluru 560034

Phone:   +91 98765 43210
Email:   priya.sharma@email.com
Annual Income: INR 18,00,000
Risk Category: Low Risk
Date: 20/07/2026`
  },
  {
    label: 'Contract',
    type: 'contract',
    content: `SERVICE AGREEMENT

Entered into as of 1st July 2026

PARTIES:
  Client:   National Banking Corp
  Provider: FinTech Solutions Ltd

1. SERVICES: Core banking API integration and 24x7 support.
2. TERM: 1 July 2026 to 30 June 2028 (24 months).
3. PAYMENT: INR 5,00,000 per month within 15 days of invoice.
4. LIABILITY CAP: INR 60,00,000.
5. GOVERNING LAW: Laws of India, courts in Mumbai.
6. TERMINATION: 90 days written notice.

Signed: _____________________ Date: 01/07/2026`
  },
  {
    label: 'Bank Statement',
    type: 'bank_statement',
    content: `BANK STATEMENT

Bank:           HDFC Bank Ltd
Account Holder: Rohan Mehta
Account Number: 50100123456789
Statement Period: 01 June 2026 to 30 June 2026

Opening Balance: INR 1,25,430.50
Closing Balance: INR 98,750.00

Transactions:
05-Jun-26  Salary Credit              +1,50,000.00
08-Jun-26  NEFT to Sharma Priya         -50,000.00
12-Jun-26  EMI Auto-debit               -38,500.00
22-Jun-26  UPI Amazon                    -2,300.00

Total Debits:  INR 96,680.50
Total Credits: INR 1,50,000.00`
  },
]

export default function UploadPage() {
  const [uploading, setUploading]       = useState(false)
  const [uploaded, setUploaded]         = useState(null)
  const [customKeywords, setCustomKeywords] = useState('')
  const [uploadError, setUploadError]   = useState(null)
  const navigate = useNavigate()

  const process = useCallback(async (file) => {
    setUploading(true)
    setUploaded(null)
    setUploadError(null)

    const tid = toast.loading('Extracting document fields...')

    try {
      const fd = new FormData()
      fd.append('file', file)

      if (customKeywords && customKeywords.trim() !== '') {
        fd.append('custom_keywords', customKeywords.trim())
      }

      const res = await api.post('/documents/upload', fd)
      const data = res.data

      setUploaded(data)

      const fieldCount = Object.keys(data.fields || {}).length
      toast.success(
        'Extracted ' + fieldCount + ' fields from ' + (data.doc_type || 'document'),
        { id: tid }
      )
    } catch (err) {
      const message = (err.response && err.response.data && err.response.data.detail)
        ? err.response.data.detail
        : (err.message || 'Upload failed')

      setUploadError(message)
      toast.error(message, { id: tid })
    } finally {
      setUploading(false)
    }
  }, [customKeywords])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: function(files) {
      if (files && files[0]) {
        process(files[0])
      }
    },
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'] },
    multiple: false,
  })

  const loadSample = function(sample) {
    const blob = new Blob([sample.content], { type: 'text/plain' })
    const file = new File([blob], 'sample-' + sample.type + '.txt', { type: 'text/plain' })
    process(file)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">

      <div>
        <h1 className="text-2xl font-bold text-gray-800">Upload Document</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload a document for AI extraction. Optionally add custom fields below.
        </p>
      </div>

      {/* Custom Keywords Input */}
      <div className="card">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Custom Fields to Extract (comma-separated, optional)
        </label>
        <input
          type="text"
          value={customKeywords}
          onChange={function(e) { setCustomKeywords(e.target.value) }}
          placeholder="e.g., SWIFT Code, Vendor Email, Delivery SLA"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
        />
        <p className="text-xs text-gray-400 mt-1">
          These fields will be extracted in addition to the standard fields for the document type.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={
          'border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all ' +
          (isDragActive
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50')
        }
      >
        <input {...getInputProps()} />
        <Upload className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-600 font-medium">
          {isDragActive ? 'Drop file here...' : 'Drag & drop a document, or click to browse'}
        </p>
        <p className="text-gray-400 text-sm mt-1">PDF or TXT</p>
      </div>

      {/* Sample Documents */}
      <div className="card">
        <h3 className="font-semibold text-gray-700 mb-3 text-sm">Or load a sample document:</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {SAMPLES.map(function(s) {
            return (
              <button
                key={s.type}
                disabled={uploading}
                onClick={function() { loadSample(s) }}
                className="border border-gray-200 rounded-lg p-3 text-left hover:bg-blue-50 hover:border-blue-300 transition-colors disabled:opacity-50"
              >
                <FileText className="w-5 h-5 text-blue-500 mb-1.5" />
                <div className="font-medium text-sm text-gray-700">{s.label}</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Processing indicator */}
      {uploading && (
        <div className="card flex items-center gap-3 border-l-4 border-l-blue-400">
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin flex-shrink-0" />
          <div>
            <div className="font-medium text-gray-800">Processing document...</div>
            <div className="text-sm text-gray-500">Azure Document Intelligence + AI extraction in progress</div>
          </div>
        </div>
      )}

      {/* Error display */}
      {uploadError && !uploading && (
        <div className="card border-l-4 border-l-red-500 bg-red-50">
          <div className="font-semibold text-red-700">Upload failed</div>
          <p className="text-sm text-red-600 mt-1">{uploadError}</p>
          <p className="text-xs text-gray-500 mt-2">
            Make sure the backend is running and your API keys are configured.
          </p>
        </div>
      )}

      {/* Success result */}
      {uploaded && !uploading && (
        <div className="card border-l-4 border-l-green-500">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-6 h-6 text-green-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-gray-800">Extraction Complete</div>

              {uploaded.summary && (
                <p className="text-sm text-gray-600 mt-1">{uploaded.summary}</p>
              )}

              <div className="flex flex-wrap gap-4 mt-2 text-sm">
                <span>
                  <b>{Object.keys(uploaded.fields || {}).length}</b> fields extracted
                </span>
                <span>
                  <b>{Math.round((uploaded.overall_confidence || 0) * 100)}%</b> confidence
                </span>
                <span className="capitalize">
                  <b>{(uploaded.doc_type || '').replace(/_/g, ' ')}</b>
                </span>
                {uploaded.llm_used && (
                  <span className="text-gray-400 text-xs">{uploaded.llm_used}</span>
                )}
              </div>

              <div className="flex items-center gap-2 mt-2">
                <span className={uploaded.status === 'auto_accepted' ? 'badge-green' : 'badge-amber'}>
                  {uploaded.status === 'auto_accepted' ? 'Auto-accepted' : 'Needs review'}
                </span>
              </div>

              <button
                onClick={function() { navigate('/documents/' + uploaded.id) }}
                className="btn-primary mt-3 text-sm"
              >
                Review Document
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}

import { useState, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export default function App() {
  const [file, setFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [mode, setMode] = useState('compare') // 'compare' | 'extract-invoice' | 'extract-text'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [dbHealth, setDbHealth] = useState({ checking: true, connected: false, database: null })
  const [showRaw, setShowRaw] = useState(false)

  const inputRef = useRef(null)

  // Check backend & DB connectivity on mount
  useEffect(() => {
    checkHealth()
  }, [])

  const checkHealth = async () => {
    try {
      setDbHealth({ checking: true, connected: false, database: null })
      const res = await fetch(`${API_BASE}/api/db/health`)
      if (!res.ok) throw new Error('Health check failed')
      const data = await res.json()
      setDbHealth({ checking: false, connected: data.connected, database: data.database })
    } catch {
      setDbHealth({ checking: false, connected: false, database: null })
    }
  }

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0]
    if (selected) {
      if (selected.type !== 'application/pdf') {
        setError('Please select a valid PDF file.')
        return
      }
      setFile(selected)
      setError(null)
      setResult(null)
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    const dropped = e.dataTransfer.files?.[0]
    if (dropped) {
      if (dropped.type !== 'application/pdf') {
        setError('Please drop a valid PDF file.')
        return
      }
      setFile(dropped)
      setError(null)
      setResult(null)
    }
  }

  const removeFile = () => {
    setFile(null)
    setResult(null)
    setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const handleSubmit = async () => {
    if (!file) return

    setLoading(true)
    setError(null)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)

    let endpoint = '/api/documents/compare-invoice'
    if (mode === 'extract-invoice') {
      endpoint = '/api/documents/extract-invoice'
    } else if (mode === 'extract-text') {
      endpoint = '/api/documents/extract'
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `Server error: ${response.status}`)
      }

      setResult(data)
    } catch (err) {
      setError(err.message || 'Failed to process document.')
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (amount, currency = '') => {
    if (amount === null || amount === undefined) return '—'
    const formatted = Number(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    return currency ? `${currency} ${formatted}` : formatted
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon">
            <svg viewBox="0 0 24 24">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM14 3.5L18.5 8H14V3.5zM8 12h8v1.5H8V12zm0 3h8v1.5H8V15zm0 3h5v1.5H8V18z"/>
            </svg>
          </div>
          <div>
            <h1 className="brand-title">AI Business Assistant</h1>
            <p className="brand-subtitle">Automated PDF Invoice Extraction & Database Audit</p>
          </div>
        </div>

        {/* Database Health Status */}
        <div className="health-badge" onClick={checkHealth} style={{ cursor: 'pointer' }} title="Click to refresh connection">
          <div className={`pulse-dot ${dbHealth.checking ? 'checking' : dbHealth.connected ? 'online' : 'offline'}`} />
          <span>
            {dbHealth.checking
              ? 'Checking backend...'
              : dbHealth.connected
              ? `DB: ${dbHealth.database || 'Connected'}`
              : 'Backend / DB Offline'}
          </span>
        </div>
      </header>

      {/* Upload Section */}
      <section className="upload-card">
        <input
          ref={inputRef}
          type="file"
          id="pdf-upload-input"
          accept="application/pdf"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />

        {!file ? (
          <div
            className={`dropzone ${dragActive ? 'drag-active' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            id="pdf-dropzone"
          >
            <div className="dropzone-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <div className="dropzone-title">Upload an Invoice PDF</div>
            <div className="dropzone-desc">Drag & drop your file here, or click to browse (Max 10 MB)</div>
          </div>
        ) : (
          <div className="file-preview">
            <div className="file-info">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <div>
                <div className="file-name">{file.name}</div>
                <div className="file-size">{(file.size / 1024).toFixed(1)} KB</div>
              </div>
            </div>
            <button className="btn-remove" onClick={removeFile} title="Remove file" id="remove-file-button">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        )}

        {/* Action Controls */}
        <div className="action-bar">
          <div className="mode-selector">
            <button
              type="button"
              className={`mode-pill ${mode === 'compare' ? 'active' : ''}`}
              onClick={() => setMode('compare')}
              id="mode-compare"
            >
              Compare with DB
            </button>
            <button
              type="button"
              className={`mode-pill ${mode === 'extract-invoice' ? 'active' : ''}`}
              onClick={() => setMode('extract-invoice')}
              id="mode-extract-invoice"
            >
              Extract & Validate
            </button>
            <button
              type="button"
              className={`mode-pill ${mode === 'extract-text' ? 'active' : ''}`}
              onClick={() => setMode('extract-text')}
              id="mode-extract-text"
            >
              Raw PDF Text
            </button>
          </div>

          <button
            className="btn-submit"
            onClick={handleSubmit}
            disabled={!file || loading}
            id="process-document-button"
          >
            {loading && <div className="spinner" />}
            <span>{loading ? 'Processing with Ollama...' : 'Process Document'}</span>
          </button>
        </div>
      </section>

      {/* Error Alert */}
      {error && (
        <div className="error-banner" id="error-banner">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: 2 }}>
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div>
            <strong>Processing Error:</strong> {error}
          </div>
        </div>
      )}

      {/* Loading Indicator */}
      {loading && (
        <div className="loading-card">
          <div className="loading-pulse">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          </div>
          <div className="loading-title">Extracting & Analyzing Document</div>
          <div className="loading-desc">
            {mode === 'compare'
              ? 'Running Ollama LLM extraction, schema validation, and PostgreSQL matching...'
              : mode === 'extract-invoice'
              ? 'Parsing PDF structure and prompting local Llama model for structured data...'
              : 'Extracting clean text and page tokens...'}
          </div>
        </div>
      )}

      {/* Results Display */}
      {result && !loading && (
        <div className="results-container">
          {/* Decision Status Banner (for compare mode or extract-invoice) */}
          {result.overall_status && (
            <div className={`status-banner ${result.overall_status}`}>
              <div className="status-title">
                {result.overall_status === 'accepted' ? (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                ) : (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                )}
                <span>
                  {result.overall_status === 'accepted'
                    ? 'Invoice Accepted & Database Matched'
                    : 'Invoice Requires Manual Review'}
                </span>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                {result.validation_status && (
                  <span className={`badge-pill ${result.validation_status}`}>
                    Validation: {result.validation_status}
                  </span>
                )}
                {result.comparison_status && (
                  <span className={`badge-pill ${result.comparison_status}`}>
                    DB: {result.comparison_status}
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Fallback status for extract-invoice mode */}
          {!result.overall_status && result.validation && (
            <div className={`status-banner ${result.validation.status}`}>
              <div className="status-title">
                <span>Validation Status: {result.validation.status === 'accepted' ? 'Passed' : 'Needs Review'}</span>
              </div>
              <span className={`badge-pill ${result.validation.status}`}>
                {result.validation.status}
              </span>
            </div>
          )}

          {/* Invoice Structured Content */}
          {result.invoice && (
            <>
              <div className="grid-2">
                {/* Invoice Metadata Card */}
                <div className="card">
                  <div className="card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2">
                      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                      <line x1="16" y1="2" x2="16" y2="6" />
                      <line x1="8" y1="2" x2="8" y2="6" />
                      <line x1="3" y1="10" x2="21" y2="10" />
                    </svg>
                    General Information
                  </div>
                  <div className="info-list">
                    <div className="info-item">
                      <span className="info-label">Invoice Number</span>
                      <span className="info-value">{result.invoice.invoice_number || '—'}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Invoice Date</span>
                      <span className="info-value">{result.invoice.invoice_date || '—'}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Supplier</span>
                      <span className="info-value">{result.invoice.supplier_name || '—'}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Customer</span>
                      <span className="info-value">{result.invoice.customer_name || '—'}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Pages</span>
                      <span className="info-value">{result.page_count} page(s)</span>
                    </div>
                  </div>
                </div>

                {/* Financial Summary Card */}
                <div className="card">
                  <div className="card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2">
                      <line x1="12" y1="1" x2="12" y2="23" />
                      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                    </svg>
                    Financial Summary
                  </div>
                  <div className="info-list">
                    <div className="info-item">
                      <span className="info-label">Currency</span>
                      <span className="info-value">{result.invoice.currency || 'USD'}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Subtotal</span>
                      <span className="info-value">
                        {formatCurrency(result.invoice.subtotal, result.invoice.currency)}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Tax / GST</span>
                      <span className="info-value">
                        {formatCurrency(result.invoice.tax, result.invoice.currency)}
                      </span>
                    </div>
                    <div className="info-item" style={{ marginTop: 8, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                      <span className="info-label" style={{ fontWeight: 600 }}>Total Amount</span>
                      <span className="amount-highlight">
                        {formatCurrency(result.invoice.total, result.invoice.currency)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Line Items Table */}
              {result.invoice.items && result.invoice.items.length > 0 && (
                <div className="card">
                  <div className="card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2">
                      <line x1="8" y1="6" x2="21" y2="6" />
                      <line x1="8" y1="12" x2="21" y2="12" />
                      <line x1="8" y1="18" x2="21" y2="18" />
                      <line x1="3" y1="6" x2="3.01" y2="6" />
                      <line x1="3" y1="12" x2="3.01" y2="12" />
                      <line x1="3" y1="18" x2="3.01" y2="18" />
                    </svg>
                    Line Items ({result.invoice.items.length})
                  </div>
                  <div className="table-wrapper">
                    <table className="items-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Description</th>
                          <th>Qty</th>
                          <th>Unit Price</th>
                          <th style={{ textAlign: 'right' }}>Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.invoice.items.map((item, idx) => (
                          <tr key={idx}>
                            <td>{idx + 1}</td>
                            <td style={{ fontWeight: 500 }}>{item.description}</td>
                            <td>{item.quantity ?? '—'}</td>
                            <td>{formatCurrency(item.unit_price)}</td>
                            <td style={{ textAlign: 'right', fontWeight: 600 }}>
                              {formatCurrency(item.amount)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Validation & DB Comparison Audits */}
              {(result.validation?.errors?.length > 0 ||
                result.validation?.warnings?.length > 0 ||
                result.comparison?.errors?.length > 0 ||
                result.comparison?.warnings?.length > 0) && (
                <div className="card">
                  <div className="card-title">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" strokeWidth="2">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                      <line x1="12" y1="9" x2="12" y2="13" />
                      <line x1="12" y1="17" x2="12.01" y2="17" />
                    </svg>
                    Audits & Discrepancies
                  </div>
                  <div className="audit-list">
                    {/* Comparison Errors */}
                    {result.comparison?.errors?.map((err, idx) => (
                      <div key={`comp-err-${idx}`} className="audit-item error">
                        <strong>DB Mismatch:</strong> {err}
                      </div>
                    ))}
                    {/* Validation Errors */}
                    {result.validation?.errors?.map((err, idx) => (
                      <div key={`val-err-${idx}`} className="audit-item error">
                        <strong>Validation Error:</strong> {err}
                      </div>
                    ))}
                    {/* Comparison Warnings */}
                    {result.comparison?.warnings?.map((warn, idx) => (
                      <div key={`comp-warn-${idx}`} className="audit-item warning">
                        <strong>DB Notice:</strong> {warn}
                      </div>
                    ))}
                    {/* Validation Warnings */}
                    {result.validation?.warnings?.map((warn, idx) => (
                      <div key={`val-warn-${idx}`} className="audit-item warning">
                        <strong>Validation Notice:</strong> {warn}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Raw Text Output if text extraction mode was used */}
          {result.full_text && (
            <div className="card">
              <div className="card-title">Extracted Text ({result.page_count} pages)</div>
              <pre className="code-block">{result.full_text}</pre>
            </div>
          )}

          {/* Raw JSON Inspector Accordion */}
          <div>
            <button className="accordion-toggle" onClick={() => setShowRaw(!showRaw)}>
              <span>{showRaw ? '▲ Hide Raw Response JSON' : '▼ Inspect Raw Response JSON'}</span>
              <span>{JSON.stringify(result).length} bytes</span>
            </button>
            {showRaw && (
              <pre className="code-block">{JSON.stringify(result, null, 2)}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

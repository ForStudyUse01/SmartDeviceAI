import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ScanResultCard } from '../components/ScanResultCard'
import { getDeviceById, getDeviceHistory } from '../lib/deviceHistory'

export function DevicesPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [, bump] = useState(0)

  const items = getDeviceHistory()
  const detail = id ? getDeviceById(id) : null

  if (id && detail) {
    return (
      <div className="dashboard-layout">
        <div className="page-hero-saas">
          <button type="button" className="secondary-button" style={{ marginBottom: 16 }} onClick={() => navigate('/devices')}>
            ← Back to list
          </button>
          <h1 className="dashboard-title">Device detail</h1>
          <p className="dashboard-subtitle">Saved estimate from local history.</p>
        </div>
        <div className="glass-panel panel-hover saas-card">
          <ScanResultCard scan={detail} />
        </div>
      </div>
    )
  }

  if (id && !detail) {
    return (
      <div className="dashboard-layout">
        <p className="muted-text">Record not found.</p>
        <Link to="/devices" className="primary-button">
          Back
        </Link>
      </div>
    )
  }

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas">
        <span className="eyebrow eyebrow-indigo">History</span>
        <h1 className="dashboard-title">My devices</h1>
        <p className="dashboard-subtitle">Estimates saved in this browser (localStorage). Click a card for details.</p>
        <button type="button" className="secondary-button" onClick={() => bump((n) => n + 1)}>
          Refresh
        </button>
      </section>

      <div className="device-card-grid">
        {items.length === 0 ? (
          <div className="empty-state saas-card">
            No saved devices yet. Run an estimate on <Link to="/scan">Scan Device</Link>.
          </div>
        ) : (
          items.map((item) => (
            <Link key={item.id} to={`/devices/${item.id}`} className="device-history-card saas-card">
              <div className="device-history-card-title">{item.brand ? `${item.brand} ${item.model}` : item.deviceName}</div>
              <div className="device-history-card-meta">
                <span>Value ₹{Number(item.value || 0).toLocaleString('en-IN')}</span>
                <span className="device-history-decision">{item.decision}</span>
              </div>
              <div className="device-history-card-date">{new Date(item.date).toLocaleString()}</div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}

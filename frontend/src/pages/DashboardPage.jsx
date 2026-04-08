import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MetricCard } from '../components/MetricCard'
import { ScanHistoryList } from '../components/ScanHistoryList'
import { useAuth } from '../context/AuthContext'
import { fetchRecentScans } from '../lib/api'
import { getDeviceHistory } from '../lib/deviceHistory'

export function DashboardPage() {
  const { token, user } = useAuth()
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const localCount = getDeviceHistory().length

  useEffect(() => {
    let active = true
    async function loadScans() {
      try {
        const recent = await fetchRecentScans(token)
        if (active) setHistory(recent.scans)
      } catch (loadError) {
        if (active) setError(loadError.message)
      }
    }
    loadScans()
    return () => {
      active = false
    }
  }, [token])

  const latest = history[0]

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas dashboard-hero">
        <div className="dashboard-hero-grid">
          <div className="dashboard-hero-copy">
            <span className="eyebrow eyebrow-indigo">Workspace overview</span>
            <h1 className="dashboard-title">Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}</h1>
            <p className="dashboard-subtitle">
              Run a structured estimate on <Link to="/scan">Scan Device</Link>, track saved runs in{' '}
              <Link to="/my-devices">My Devices</Link>, or open <Link to="/assistant">AI Assistant</Link> for guided
              steps.
            </p>
            <div className="hero-actions">
              <Link to="/scan" className="primary-button hero-cta">
                New device scan
              </Link>
              <Link to="/my-devices" className="secondary-button hero-cta">
                View history ({localCount})
              </Link>
            </div>
          </div>

          <div className="hero-summary-card">
            <div className="hero-summary-item">
              <span className="hero-summary-label">Latest resale</span>
              <span className="hero-summary-value">
                {latest?.resaleValue ? `₹${Number(latest.resaleValue).toLocaleString('en-IN')}` : 'No scan yet'}
              </span>
            </div>
            <div className="hero-summary-item">
              <span className="hero-summary-label">Saved devices</span>
              <span className="hero-summary-value">{localCount}</span>
            </div>
            <div className="hero-summary-item">
              <span className="hero-summary-label">Server history</span>
              <span className="hero-summary-value">{history.length}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="content-grid content-grid-triple">
        <div className="glass-panel panel-hover saas-card premium-panel">
          <h2 className="panel-title">Snapshot</h2>
          <p className="panel-subtitle">Latest server-side image scan (if any).</p>
          <div className="metrics-grid metrics-grid-1">
            <MetricCard label="Latest component" value={latest?.component || '—'} hint="From last classifier run" />
            <MetricCard label="Latest resale (INR)" value={latest?.resaleValue ?? '—'} hint="From last scan" />
            <MetricCard label="CO₂ saved (kg)" value={latest?.co2Saved ?? '—'} hint="Environmental estimate" />
          </div>
          {error ? <div className="error-banner panel-status-banner">{error}</div> : null}
        </div>

        <div className="glass-panel panel-hover saas-card premium-panel">
          <h2 className="panel-title">Quick stats</h2>
          <p className="panel-subtitle">Saved analyses on server + local estimates.</p>
          <div className="metrics-grid metrics-grid-1">
            <MetricCard label="Server history" value={`${history.length}`} hint="Mongo-backed scans" />
            <MetricCard label="Local devices" value={`${localCount}`} hint="Browser saved estimates" />
            <MetricCard label="Platform" value="SmartDeviceAI" hint="Multi-feature workspace" />
          </div>
        </div>

        <div className="glass-panel panel-hover saas-card premium-panel">
          <h2 className="panel-title">Recent server scans</h2>
          <p className="panel-subtitle">Existing API flow unchanged.</p>
          <ScanHistoryList scans={history} />
        </div>
      </section>
    </div>
  )
}

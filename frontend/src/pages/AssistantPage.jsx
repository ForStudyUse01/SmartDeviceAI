import { Link } from 'react-router-dom'

export function AssistantPage() {
  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas premium-hero-section">
        <span className="eyebrow eyebrow-indigo">AI support</span>
        <h1 className="dashboard-title">Chatling Support Agent</h1>
        <p className="dashboard-subtitle">
          Chat with Support Agent directly from this page.
        </p>
        <div className="hero-actions">
          <Link to="/dashboard" className="secondary-button hero-cta">
            Back to Dashboard
          </Link>
        </div>
      </section>

      <div className="glass-panel panel-hover saas-card assistant-card premium-panel">
        <div className="assistant-messages" style={{ minHeight: 520, marginBottom: 12, padding: 0, overflow: 'hidden' }}>
          <iframe
            src="https://share.chatling.ai/s/t6x88KM1i4E1SpB"
            title="Chatling Support Agent"
            style={{ width: '100%', height: '520px', border: 0, borderRadius: '18px' }}
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      </div>
    </div>
  )
}

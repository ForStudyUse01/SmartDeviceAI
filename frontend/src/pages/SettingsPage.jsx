import { useState } from 'react'

export function SettingsPage() {
  const [themeNote, setThemeNote] = useState('Slate + indigo accent (default)')
  const [notify, setNotify] = useState(true)

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas">
        <span className="eyebrow eyebrow-indigo">Preferences</span>
        <h1 className="dashboard-title">Settings</h1>
        <p className="dashboard-subtitle">Workspace preferences for SmartDeviceAI.</p>
      </section>

      <div className="content-grid">
        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">Appearance</h2>
          <p className="panel-subtitle">Theme is fixed for this build: dark slate background, indigo accent.</p>
          <div className="field">
            <label htmlFor="theme-note">Notes</label>
            <input id="theme-note" value={themeNote} onChange={(e) => setThemeNote(e.target.value)} />
          </div>
        </div>

        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">Notifications</h2>
          <p className="panel-subtitle">Local preference only (not persisted to server).</p>
          <label className="settings-check">
            <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
            Show in-app tips on scan page
          </label>
        </div>
      </div>
    </div>
  )
}

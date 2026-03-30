import { useMemo, useState } from 'react'
import { getDeviceHistory } from '../lib/deviceHistory'
import { getRepairReply } from '../lib/repairChat'

export function RepairMasterPage() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Ask how to fix a screen, battery, water damage, or audio. I’ll suggest safe steps.' },
  ])
  const [input, setInput] = useState('')
  const [selectedId, setSelectedId] = useState(null)

  const history = getDeviceHistory()

  const selected = useMemo(() => {
    const h = history
    if (!h.length) return undefined
    const id = selectedId ?? h[0].id
    return h.find((x) => x.id === id) ?? h[0]
  }, [history, selectedId])

  const contextLabel = selected
    ? `${selected.brand || ''} ${selected.model || ''}`.trim() || selected.deviceName
    : 'Generic device'

  const repairMeta = useMemo(() => {
    const t = String(selected?.snapshot?.deviceType || selected?.deviceName || '').toLowerCase()
    let difficulty = 'Medium'
    let hours = 1.5
    let base = 2500
    if (t.includes('laptop')) {
      difficulty = 'Medium'
      hours = 2
      base = 4500
    }
    if (t.includes('gpu') || t.includes('graphic')) {
      difficulty = 'Hard'
      hours = 2.5
      base = 6000
    }
    if (t.includes('mobile') || t.includes('phone')) {
      difficulty = 'Easy'
      hours = 1
      base = 1800
    }
    const rc = selected?.snapshot?.repairCost
    if (typeof rc === 'number') base = rc
    return { difficulty, hours, base }
  }, [selected])

  function send() {
    const q = input.trim()
    if (!q) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text: q }])
    const reply = getRepairReply(q, { label: contextLabel })
    setTimeout(() => {
      setMessages((m) => [...m, { role: 'assistant', text: reply }])
    }, 200)
  }

  const selectValue = selected?.id ?? ''

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas">
        <span className="eyebrow eyebrow-indigo">Repair</span>
        <h1 className="dashboard-title">Repair Master</h1>
        <p className="dashboard-subtitle">Context from your saved devices + rule-based repair guidance.</p>
      </section>

      <div className="repair-master-grid">
        <div className="glass-panel panel-hover saas-card repair-context">
          <h2 className="panel-title">Device context</h2>
          {selected ? (
            <>
              <p className="panel-subtitle">Selected from My Devices history.</p>
              <div className="field">
                <label htmlFor="repair-pick">Saved device</label>
                <select
                  id="repair-pick"
                  value={selectValue}
                  onChange={(e) => setSelectedId(e.target.value || null)}
                >
                  {history.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.brand} {h.model} — ₹{Number(h.value).toLocaleString('en-IN')}
                    </option>
                  ))}
                </select>
              </div>
              <ul className="device-info-list" style={{ marginTop: 16 }}>
                <li>
                  <span className="result-key">Label</span> {contextLabel}
                </li>
                <li>
                  <span className="result-key">Decision</span> {selected.decision}
                </li>
              </ul>
              <h3 className="panel-title" style={{ fontSize: '1rem', marginTop: 24 }}>
                Base repair estimates
              </h3>
              <ul className="device-info-list">
                <li>
                  <span className="result-key">Difficulty</span> {repairMeta.difficulty}
                </li>
                <li>
                  <span className="result-key">Time</span> ~{repairMeta.hours} h
                </li>
                <li>
                  <span className="result-key">Base cost</span> ₹{repairMeta.base.toLocaleString('en-IN')}
                </li>
              </ul>
            </>
          ) : (
            <p className="muted-text">Save a scan from Scan Device first — it appears in My Devices.</p>
          )}
        </div>

        <div className="glass-panel panel-hover saas-card repair-chat">
          <h2 className="panel-title">AI Repair Technician</h2>
          <p className="panel-subtitle">Mock assistant — pattern-matched steps (not a live LLM).</p>
          <div className="chat-messages">
            {messages.map((m, i) => (
              <div key={`${i}-${m.role}`} className={`chat-bubble ${m.role}`}>
                {m.text}
              </div>
            ))}
          </div>
          <div className="chat-input-row">
            <input
              className="chat-input"
              type="text"
              value={input}
              placeholder='Try: "How to fix screen?"'
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
            />
            <button type="button" className="primary-button" onClick={send}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

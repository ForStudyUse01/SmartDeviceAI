import { useRef, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { chatAssistant } from '../lib/api'

export function AssistantPage() {
  const { token } = useAuth()
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Ask me about battery, overheating, slow performance, app crashes, or screen issues.',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  async function sendMessage() {
    const text = input.trim()
    if (!text || loading || !token) return

    setLoading(true)
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text }])
    try {
      const response = await chatAssistant(token, text)
      setMessages((prev) => [...prev, { role: 'assistant', text: response.reply || 'No reply generated.' }])
    } catch (error) {
      setMessages((prev) => [...prev, { role: 'assistant', text: error.message || 'Assistant unavailable.' }])
    } finally {
      setLoading(false)
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    }
  }

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas premium-hero-section">
        <span className="eyebrow eyebrow-indigo">AI support</span>
        <h1 className="dashboard-title">AI Assistant</h1>
        <p className="dashboard-subtitle">Quick troubleshooting help for common device issues.</p>
      </section>

      <div className="glass-panel panel-hover saas-card assistant-card premium-panel">
        <div className="assistant-messages">
          {messages.map((message, idx) => (
            <div key={`${idx}-${message.role}`} className={`chat-bubble ${message.role}`}>
              {message.text}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <div className="assistant-input-row">
          <input
            className="chat-input"
            type="text"
            value={input}
            placeholder="Type your issue..."
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && sendMessage()}
          />
          <button type="button" className="primary-button" disabled={loading} onClick={sendMessage}>
            {loading ? <span className="btn-spinner" aria-hidden="true" /> : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

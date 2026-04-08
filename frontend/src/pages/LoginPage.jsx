import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { AuthForm } from '../components/AuthForm'
import { useAuth } from '../context/AuthContext'

export function LoginPage() {
  const navigate = useNavigate()
  const { isAuthenticated, login } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(credentials) {
    setLoading(true)
    setError('')
    try {
      await login(credentials)
      navigate('/dashboard')
    } catch (submissionError) {
      setError(submissionError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-card auth-card-premium">
        <span className="eyebrow">Login</span>
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true"></span>
          <span className="brand-name">
            SmartDevice<span className="brand-ai">AI</span>
          </span>
        </div>
        <h1 className="auth-title">Welcome back to SmartDeviceAI</h1>
        <p className="auth-subtitle">
          AI-powered Device Lifecycle Intelligence for scans, lifecycle metrics, and recovery value.
        </p>
        <AuthForm mode="login" onSubmit={handleSubmit} loading={loading} error={error} />
        <div className="auth-footer">
          Need an account? <Link className="auth-link" to="/signup">Sign up</Link>
        </div>
      </div>
    </div>
  )
}

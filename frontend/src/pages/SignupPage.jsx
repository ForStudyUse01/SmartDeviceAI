import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { AuthForm } from '../components/AuthForm'
import { useAuth } from '../context/AuthContext'

export function SignupPage() {
  const navigate = useNavigate()
  const { isAuthenticated, signup } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(credentials) {
    setLoading(true)
    setError('')
    try {
      await signup(credentials)
      navigate('/dashboard')
    } catch (submissionError) {
      setError(submissionError.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-layout">
      <div className="auth-card">
        <span className="eyebrow">Signup</span>
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true"></span>
          <span className="brand-name">
            SmartDevice<span className="brand-ai">AI</span>
          </span>
        </div>
        <h1 className="auth-title">Create your SmartDeviceAI account</h1>
        <p className="auth-subtitle">
          AI-powered Device Lifecycle Intelligence for saved scans, lifecycle monitoring, and value estimates.
        </p>
        <AuthForm mode="signup" onSubmit={handleSubmit} loading={loading} error={error} />
        <div className="auth-footer">
          Already have an account? <Link className="auth-link" to="/login">Login</Link>
        </div>
      </div>
    </div>
  )
}

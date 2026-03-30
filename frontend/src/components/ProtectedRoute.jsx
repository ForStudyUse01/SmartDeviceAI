import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute({ children }) {
  const { loading, isAuthenticated } = useAuth()

  if (loading) {
    return (
      <div className="auth-layout">
        <div className="auth-card">
          <span className="eyebrow">Loading</span>
          <h1 className="auth-title">Restoring your workspace</h1>
          <p className="auth-subtitle">Verifying your saved session.</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return children
}

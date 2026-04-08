import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AICursor } from './components/AICursor'
import { ProtectedRoute } from './components/ProtectedRoute'
import { WorkspaceShell } from './components/WorkspaceShell'
import { AuthProvider } from './context/AuthContext'
import { AssistantPage } from './pages/AssistantPage'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { LoginPage } from './pages/LoginPage'
import { ScanPage } from './pages/ScanPage'
import { SettingsPage } from './pages/SettingsPage'
import { SignupPage } from './pages/SignupPage'

function ProtectedWorkspace() {
  return (
    <ProtectedRoute>
      <WorkspaceShell>
        <Outlet />
      </WorkspaceShell>
    </ProtectedRoute>
  )
}

function App() {
  return (
    <AuthProvider>
      <AICursor imagePath="/assets/bot.png" />
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route element={<ProtectedWorkspace />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/my-devices" element={<DevicesPage />} />
          <Route path="/my-devices/:id" element={<DevicesPage />} />
          <Route path="/assistant" element={<AssistantPage />} />
          <Route path="/hybrid" element={<Navigate to="/scan" replace />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/devices" element={<Navigate to="/my-devices" replace />} />
          <Route path="/devices/:id" element={<Navigate to="/my-devices" replace />} />
          <Route path="/repair" element={<Navigate to="/assistant" replace />} />
          <Route path="/repair-master" element={<Navigate to="/assistant" replace />} />
        </Route>
        <Route path="/manual-input" element={<Navigate to="/scan" replace />} />
        <Route path="/device-market" element={<Navigate to="/dashboard" replace />} />
        <Route path="/metal-market" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App

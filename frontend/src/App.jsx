import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/ProtectedRoute'
import { WorkspaceShell } from './components/WorkspaceShell'
import { AuthProvider } from './context/AuthContext'
import { DashboardPage } from './pages/DashboardPage'
import { DevicesPage } from './pages/DevicesPage'
import { LoginPage } from './pages/LoginPage'
import { RepairMasterPage } from './pages/RepairMasterPage'
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
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route element={<ProtectedWorkspace />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/devices" element={<DevicesPage />} />
          <Route path="/devices/:id" element={<DevicesPage />} />
          <Route path="/repair" element={<RepairMasterPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="/manual-input" element={<Navigate to="/scan" replace />} />
        <Route path="/device-market" element={<Navigate to="/dashboard" replace />} />
        <Route path="/metal-market" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App

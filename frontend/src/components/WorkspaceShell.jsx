import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function IconDashboard() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 13h7V4H4v9zm0 7h7v-5H4v5zm9 0h7v-9h-7v9zm0-16v5h7V4h-7z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  )
}

function IconScan() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9.5 6.5v11l8.5-5.5-8.5-5.5zM4 19h2V5H4v14z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  )
}

function IconDevices() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h10v2H4v-2z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  )
}

function IconAssistant() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3C6.49 3 2 6.92 2 11.75c0 2.53 1.23 4.8 3.2 6.37L4 22l4.44-2.42c1.13.31 2.31.47 3.56.47 5.51 0 10-3.92 10-8.75S17.51 3 12 3zm-4 9h8v2H8v-2zm0-4h8v2H8V8z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  )
}

function IconModelComparison() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 19h16v2H4v-2zM6 10h3v7H6v-7zm5-4h3v11h-3V6zm5 2h3v9h-3V8z" fill="currentColor" opacity="0.9" />
    </svg>
  )
}

function IconSettings() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.52-.4-1.08-.73-1.69-.98l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.61.25-1.17.59-1.69.98l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.52.4 1.08.73 1.69.98l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.61-.25 1.17-.59 1.69-.98l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"
        fill="currentColor"
        opacity="0.9"
      />
    </svg>
  )
}

const navItems = [
  { to: '/dashboard', label: 'Dashboard', Icon: IconDashboard },
  { to: '/scan', label: 'Scan Device', Icon: IconScan },
  { to: '/model-comparison', label: 'Model Comparison', Icon: IconModelComparison },
  { to: '/my-devices', label: 'My Devices', Icon: IconDevices },
  { to: '/assistant', label: 'AI Assistant', Icon: IconAssistant },
  { to: '/settings', label: 'Settings', Icon: IconSettings },
]

export function WorkspaceShell({ children }) {
  const { logout, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  function isActivePath(path) {
    if (path === '/dashboard') return location.pathname === '/dashboard'
    if (path === '/my-devices') return location.pathname.startsWith('/my-devices')
    return location.pathname === path
  }

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="saas-workspace">
      <aside className="saas-sidebar" aria-label="Main navigation">
        <div className="saas-sidebar-brand">
          <span className="brand-mark saas-brand-dot" aria-hidden="true"></span>
          <div>
            <div className="saas-brand-title">
              SmartDevice<span className="brand-ai-indigo">AI</span>
            </div>
            <div className="saas-brand-tagline">Device intelligence</div>
          </div>
        </div>

        <nav className="saas-sidebar-nav">
          {navItems.map((item) => {
            const NavIcon = item.Icon
            return (
              <Link
                key={`${item.to}-${item.label}`}
                to={item.to}
                className={`saas-nav-item${isActivePath(item.to) ? ' active' : ''}`}
              >
                <NavIcon />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        <div className="saas-sidebar-footer">
          <div className="saas-sidebar-user" title={user?.email}>
            {user?.email || 'Signed in'}
          </div>
          <button type="button" className="secondary-button saas-logout-btn" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </aside>

      <div className="saas-main-wrap">
        <main className="saas-main">{children}</main>
      </div>
    </div>
  )
}

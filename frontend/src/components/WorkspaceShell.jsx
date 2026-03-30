import { NavLink, useNavigate } from 'react-router-dom'
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

function IconRepair() {
  return (
    <svg className="sidebar-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"
        fill="currentColor"
        opacity="0.9"
      />
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
  { to: '/devices', label: 'My Devices', Icon: IconDevices },
  { to: '/repair', label: 'Repair Master', Icon: IconRepair },
  { to: '/settings', label: 'Settings', Icon: IconSettings },
]

export function WorkspaceShell({ children }) {
  const { logout, user } = useAuth()
  const navigate = useNavigate()

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
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `saas-nav-item${isActive ? ' active' : ''}`}
                end={item.to === '/dashboard'}
              >
                <NavIcon />
                <span>{item.label}</span>
              </NavLink>
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

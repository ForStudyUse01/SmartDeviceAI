/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from 'react'
import { getCurrentUser, loginUser, signupUser } from '../lib/api'
import { clearStoredToken, getStoredToken, storeToken } from '../lib/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getStoredToken())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getStoredToken()))

  useEffect(() => {
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }

    let active = true

    async function hydrateUser() {
      try {
        const currentUser = await getCurrentUser(token)
        if (active) {
          setUser(currentUser)
        }
      } catch {
        clearStoredToken()
        if (active) {
          setToken(null)
          setUser(null)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    hydrateUser()

    return () => {
      active = false
    }
  }, [token])

  async function handleAuth(action, credentials) {
    const response = action === 'login' ? await loginUser(credentials) : await signupUser(credentials)
    storeToken(response.access_token)
    setToken(response.access_token)
    setUser(response.user)
    return response.user
  }

  async function login(credentials) {
    return handleAuth('login', credentials)
  }

  async function signup(credentials) {
    return handleAuth('signup', credentials)
  }

  function logout() {
    clearStoredToken()
    setToken(null)
    setUser(null)
    setLoading(false)
  }

  return (
    <AuthContext.Provider
      value={{
        loading,
        token,
        user,
        isAuthenticated: Boolean(token && user),
        login,
        signup,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }

  return context
}

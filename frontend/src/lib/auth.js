const TOKEN_KEY = 'ai_dashboard_token'

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function storeToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY)
}

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options)
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed')
  }

  return data
}

export function signupUser(credentials) {
  return request('/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}

export function loginUser(credentials) {
  return request('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}

export function getCurrentUser(token) {
  return request('/me', {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function fetchRecentScans(token) {
  return request('/scans/recent', {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function uploadScan(token, file) {
  const formData = new FormData()
  formData.append('file', file)

  return request('/scan', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })
}

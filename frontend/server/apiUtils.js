export function json(res, status, body) {
  res.status(status).setHeader('Content-Type', 'application/json')
  res.send(JSON.stringify(body))
}

export function parseBody(req) {
  if (!req.body) return {}
  if (typeof req.body === 'string') {
    try {
      return JSON.parse(req.body)
    } catch {
      return {}
    }
  }
  return req.body
}

export function createToken(email) {
  const payload = {
    sub: String(email || '').toLowerCase(),
    email: String(email || '').toLowerCase(),
    iat: Date.now(),
  }
  return Buffer.from(JSON.stringify(payload), 'utf8').toString('base64url')
}

export function getUserFromRequest(req) {
  const authHeader = req.headers?.authorization || req.headers?.Authorization || ''
  const value = String(authHeader)
  if (!value.toLowerCase().startsWith('bearer ')) return null
  const token = value.slice(7).trim()
  try {
    const raw = Buffer.from(token, 'base64url').toString('utf8')
    const payload = JSON.parse(raw)
    if (!payload?.email || !payload?.sub) return null
    return { id: payload.sub, email: payload.email }
  } catch {
    return null
  }
}

export function ruleBasedReply(message) {
  const text = String(message || '').toLowerCase().trim()
  if (text.includes('battery')) return 'For battery issues: reduce brightness, disable heavy background sync, and check battery health.'
  if (text.includes('overheat') || text.includes('heating') || text.includes('hot')) return 'For overheating: close heavy background apps, avoid charging during gaming, and keep ventilation clear.'
  if (text.includes('slow') || text.includes('lag') || text.includes('performance')) return 'For slow performance: keep 15%+ storage free, uninstall unused apps, restart weekly, and update OS.'
  if (text.includes('crash') || text.includes('app')) return 'For app crashes: clear app cache, update the app, check permissions, and reinstall if needed.'
  if (text.includes('screen') || text.includes('display')) return 'For screen issues: inspect cracks, test touch response, and back up important data before repair.'
  return 'I can help with battery, overheating, slow performance, app crashes, and screen issues.'
}

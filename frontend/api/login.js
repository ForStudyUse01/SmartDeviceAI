import { createToken, json, parseBody } from '../server/apiUtils.js'

export default async function handler(req, res) {
  if (req.method !== 'POST') return json(res, 405, { detail: 'Method not allowed' })
  const payload = parseBody(req)
  const email = String(payload?.email || '').trim().toLowerCase()
  const password = String(payload?.password || '')
  if (!email || !password) return json(res, 400, { detail: 'Email and password are required' })
  return json(res, 200, { access_token: createToken(email), user: { id: email, email } })
}

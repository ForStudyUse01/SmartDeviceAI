import { getUserFromRequest, json, parseBody, ruleBasedReply } from '../server/apiUtils.js'

export default async function handler(req, res) {
  if (req.method !== 'POST') return json(res, 405, { detail: 'Method not allowed' })
  const user = getUserFromRequest(req)
  if (!user) return json(res, 401, { detail: 'Not authenticated' })
  const payload = parseBody(req)
  const message = String(payload?.message || '').trim()
  if (!message) return json(res, 400, { detail: 'Message is required' })
  return json(res, 200, { reply: ruleBasedReply(message) })
}

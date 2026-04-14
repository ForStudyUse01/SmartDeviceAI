import { getUserFromRequest, json } from '../server/apiUtils.js'

export default async function handler(req, res) {
  if (req.method !== 'POST') return json(res, 405, { detail: 'Method not allowed' })
  const user = getUserFromRequest(req)
  if (!user) return json(res, 401, { detail: 'Not authenticated' })
  return json(res, 503, { detail: 'Live scan API is not configured yet. Please connect a backend inference service.' })
}

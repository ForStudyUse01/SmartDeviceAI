import { getUserFromRequest, json } from '../server/apiUtils.js'

export default async function handler(req, res) {
  if (req.method !== 'GET') return json(res, 405, { detail: 'Method not allowed' })
  const user = getUserFromRequest(req)
  if (!user) return json(res, 401, { detail: 'Not authenticated' })
  return json(res, 200, user)
}

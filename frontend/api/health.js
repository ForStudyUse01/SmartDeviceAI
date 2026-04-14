import { json } from '../server/apiUtils.js'

export default async function handler(req, res) {
  if (req.method !== 'GET') return json(res, 405, { detail: 'Method not allowed' })
  return json(res, 200, { status: 'ok' })
}

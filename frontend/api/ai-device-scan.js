import { getUserFromRequest, json } from '../server/apiUtils.js'

export default async function handler(req, res) {
  if (req.method !== 'POST') return json(res, 405, { detail: 'Method not allowed' })
  const user = getUserFromRequest(req)
  if (!user) return json(res, 401, { detail: 'Not authenticated' })

  const detected = {
    detected_device_type: 'mobile',
    detected_condition: 'average',
    confidence: 0.61,
    confidence_label: 'medium',
    detected_objects: [
      {
        yolo_label: 'mobile',
        yolo_confidence: 0.61,
        condition: 'partially working',
        details:
          'This response is a STATIC Vercel demo stub (not your local BLIP-2). Configure your real API URL or run the app locally.',
        suggestion:
          'For real scans: run the FastAPI dashboard + app.py AI server locally, or set DASHBOARD_API_URL on Vercel to your hosted API.',
      },
    ],
    vlm_condition: 'Average',
    vlm_damage: 'Not Broken',
  }

  return json(res, 200, {
    success: true,
    detected,
    user_input: {},
    match_score: 78,
    reasons: [
      'STATIC_VERCEL_STUB: this route does not call your GPU VLM. Use local dev (VITE_API_URL=http://127.0.0.1:8000) or proxy this handler to your FastAPI /ai-device-scan.',
    ],
    final_analysis: {
      status: 'success',
      image_name: 'uploaded-image',
      detected_objects: detected.detected_objects,
      num_detections: 1,
    },
  })
}

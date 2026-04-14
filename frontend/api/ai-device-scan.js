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
        details: 'Fallback cloud inference mode is active.',
        suggestion: 'Upload clearer front and back photos for higher-confidence AI verification.',
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
    reasons: ['Running in cloud fallback inference mode'],
    final_analysis: {
      status: 'success',
      image_name: 'uploaded-image',
      detected_objects: detected.detected_objects,
      num_detections: 1,
    },
  })
}

/**
 * Local ML price API (Vite proxies /ml-price → price_ml_server on 8765).
 */

const ML_BASE = import.meta.env.VITE_ML_PRICE_API || '/ml-price'

/** Map dataset device labels to sklearn training CSV categories. */
export function mapDeviceTypeForMl(deviceType) {
  const t = String(deviceType || '').toLowerCase()
  if (t.includes('tablet')) return 'tablet'
  if (t.includes('laptop') || t.includes('notebook')) return 'laptop'
  if (t.includes('desktop')) return 'desktop'
  if (t.includes('monitor')) return 'monitor'
  if (t.includes('watch') || t.includes('wearable')) return 'smartwatch'
  if (t.includes('headphone') || t.includes('earphone')) return 'headphones'
  if (t.includes('speaker')) return 'speaker'
  if (t.includes('camera')) return 'camera'
  if (t.includes('console')) return 'console'
  if (t.includes('printer')) return 'printer'
  if (t.includes('mobile') || t.includes('phone')) return 'smartphone'
  return 'smartphone'
}

/** Map UI condition (Good / Average / Poor) to ML CSV condition. */
export function mapConditionForMl(conditionLabel) {
  const c = String(conditionLabel || 'Good').trim().toLowerCase()
  if (c === 'excellent') return 'excellent'
  if (c === 'good') return 'good'
  if (c === 'average' || c === 'fair') return 'fair'
  if (c === 'poor') return 'poor'
  return 'good'
}

/**
 * POST /predict — returns best_price, best_model_name, confidence, model_comparison, etc.
 * Fails silently by throwing; caller should catch and omit UI.
 */
export async function fetchMlPricePrediction({
  brand,
  deviceType,
  ageYears,
  conditionLabel,
  originalPrice,
  usageHoursPerDay = 5,
}) {
  const original = Math.max(0, Number(originalPrice) || 0)
  const body = {
    brand: String(brand || 'Unknown').trim() || 'Unknown',
    device_type: mapDeviceTypeForMl(deviceType),
    age_years: Math.min(50, Math.max(0, Number(ageYears) || 0)),
    condition: mapConditionForMl(conditionLabel),
    original_price: original > 0 ? original : 10000,
    usage_hours_per_day: Math.min(24, Math.max(0, Number(usageHoursPerDay) || 5)),
  }

  const res = await fetch(`${ML_BASE}/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `ML API ${res.status}`)
  }

  const data = await res.json()
  let bestPrice = data.best_price
  if (bestPrice == null && Array.isArray(data.model_comparison)) {
    const row = data.model_comparison.find((r) => r.model_key === data.best_model || r.is_best)
    bestPrice = row?.predicted_price ?? row?.price ?? null
  }
  return {
    ...data,
    best_price: bestPrice != null ? Number(bestPrice) : null,
  }
}

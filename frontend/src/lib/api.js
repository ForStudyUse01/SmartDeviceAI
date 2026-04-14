/** FastAPI dashboard — set `VITE_API_URL` in `frontend/.env` (e.g. http://127.0.0.1:8000). No trailing slash. */
const DASHBOARD_API_BASE = String(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000')
  .trim()
  .replace(/\/$/, '')

/** YOLO/VLM service — `VITE_AI_ANALYZE_URL` (default http://127.0.0.1:5000). */
const AI_API_BASE = String(import.meta.env.VITE_AI_ANALYZE_URL || 'http://127.0.0.1:5000')
  .trim()
  .replace(/\/$/, '')

function dashboardUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${DASHBOARD_API_BASE}${p}`
}

function aiUrl(path) {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${AI_API_BASE}${p}`
}

function logDashboardApiFailure(context, response, data) {
  console.error(`[dashboard API] ${context}`, {
    url: response.url,
    status: response.status,
    body: data,
  })
}
const REQUEST_TIMEOUT_MS = 25000
/** Multipart AI scan can exceed default when images are large or CDN adds latency. */
const AI_DEVICE_SCAN_TIMEOUT_MS = 120000

function validateUrlConfiguration() {
  if (!import.meta.env.DEV) {
    const isValid = (value) => /^https?:\/\//.test(value) || value.startsWith('/')
    if (!isValid(DASHBOARD_API_BASE)) {
      throw new Error(`Invalid VITE_API_URL: "${DASHBOARD_API_BASE}". Use http(s)://… or a path like /api.`)
    }
    if (!isValid(AI_API_BASE)) {
      throw new Error(`Invalid VITE_AI_ANALYZE_URL: "${AI_API_BASE}". Use http(s)://… or a path like /api/ai.`)
    }
  }
}

validateUrlConfiguration()

/**
 * FastAPI may return `detail` as a string, or (422 validation) an array of { loc, msg }.
 * Nginx/CloudFront often return HTML with no JSON body — give actionable hints by status.
 */
function formatFastApiErrorDetail(data, response) {
  const status = response.status
  const detail = data?.detail
  // FastAPI default 404 is { "detail": "Not Found" } — unhelpful when /api was not proxied (e.g. old vite preview).
  if (status === 404) {
    const d = typeof detail === 'string' ? detail.trim() : ''
    if (d === 'Not Found' || d === '') {
      return 'Dashboard API route not found (404). Check VITE_API_URL in frontend/.env matches FastAPI (e.g. http://127.0.0.1:8000) and POST /ai-device-scan exists.'
    }
    if (d) return d
  }
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item.msg === 'string') {
        const loc = Array.isArray(item.loc) ? item.loc.filter(Boolean).join(' → ') : ''
        return loc ? `${loc}: ${item.msg}` : item.msg
      }
      try {
        return JSON.stringify(item)
      } catch {
        return String(item)
      }
    })
    const joined = parts.filter(Boolean).join('; ')
    if (joined) return joined
  }
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    try {
      return JSON.stringify(detail)
    } catch {
      /* fall through */
    }
  }
  const ct = typeof response.headers?.get === 'function' ? response.headers.get('content-type') || '' : ''
  if (status === 413) {
    return 'Upload rejected: body too large (413). Try smaller or fewer images, or raise the server upload limit (e.g. nginx client_max_body_size).'
  }
  if (status === 401) return 'Sign in expired or invalid. Please sign in again.'
  if (status === 403) return 'Access forbidden (403).'
  if (status === 502 || status === 503) {
    return 'Bad gateway (502/503). The API or a proxy upstream may be down — try again shortly.'
  }
  if (status === 504) {
    return 'Gateway timeout (504). Try fewer/smaller images or increase proxy/CloudFront timeouts.'
  }
  if (status >= 500 && ct.includes('text/html')) {
    return `Server error (${status}) — received HTML instead of JSON (often a proxy/nginx error page).`
  }
  return ''
}

function buildNetworkError(serviceName, baseUrl, originalError) {
  const details = originalError?.message ? ` (${originalError.message})` : ''
  return new Error(`Cannot reach ${serviceName} backend at ${baseUrl}${details}`)
}

async function fetchWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS, serviceName = 'backend') {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    })
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(`${serviceName} request timed out. Check server status and retry.`)
    }
    throw buildNetworkError(serviceName, url, error)
  } finally {
    clearTimeout(timeoutId)
  }
}

function toLegacyAiResponse(data) {
  const objects = data?.detected_objects || []
  const primaryObject = objects[0]
  const detectedDevice = primaryObject?.yolo_label || primaryObject?.vlm_object || 'unknown'
  const rawCondition = primaryObject?.condition || 'partially working'
  const normalizedCondition =
    rawCondition === 'working'
      ? 'Excellent'
      : rawCondition === 'partially working'
        ? 'Fair'
        : rawCondition === 'scrap'
          ? 'Poor'
          : 'Poor'

  return {
    detected_device: detectedDevice,
    ai_condition: normalizedCondition,
    confidence: primaryObject?.yolo_confidence || 0,
    suggestion: primaryObject?.suggestion || '',
    eco_score: primaryObject?.eco_score || 0,
    raw: data,
  }
}

async function request(path, options = {}) {
  const url = dashboardUrl(path)
  const response = await fetchWithTimeout(url, options, REQUEST_TIMEOUT_MS, 'dashboard API')
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    logDashboardApiFailure(`${options.method || 'GET'} ${path}`, response, data)
    throw new Error(formatFastApiErrorDetail(data, response) || `Request failed (HTTP ${response.status})`)
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

export async function aiDeviceScan(token, payload) {
  if (!payload?.images?.length) {
    throw new Error('At least one image is required')
  }
  const formData = new FormData()
  payload.images.forEach((image) => formData.append('images', image))
  formData.append('device_type', payload.device_type)
  formData.append('brand', payload.brand)
  formData.append('model', payload.model)
  formData.append('age', String(payload.age))
  formData.append('condition', payload.condition)
  formData.append('screen_damage', String(Boolean(payload.screen_damage)))
  formData.append('body_damage', String(Boolean(payload.body_damage)))
  formData.append('water_damage', String(Boolean(payload.water_damage)))

  const url = dashboardUrl('/ai-device-scan')
  const response = await fetchWithTimeout(
    url,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    },
    AI_DEVICE_SCAN_TIMEOUT_MS,
    'dashboard API'
  )
  let data = {}
  try {
    data = await response.json()
  } catch {
    data = {}
  }
  if (!response.ok) {
    logDashboardApiFailure('POST /ai-device-scan', response, data)
    throw new Error(
      formatFastApiErrorDetail(data, response) || `AI device scan failed (HTTP ${response.status})`,
    )
  }
  if (import.meta.env.DEV) {
    console.info('[ai-device-scan] OK', { match: data?.match_score, success: data?.success })
  }
  return data
}

export async function chatAssistant(token, message) {
  const response = await fetchWithTimeout(
    dashboardUrl('/chat'),
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    },
    REQUEST_TIMEOUT_MS,
    'dashboard API'
  )
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    logDashboardApiFailure('POST /chat', response, data)
    throw new Error(formatFastApiErrorDetail(data, response) || `Assistant request failed (HTTP ${response.status})`)
  }
  return data
}

export async function ensureDashboardApiReady() {
  const response = await fetchWithTimeout(dashboardUrl('/health'), {}, 10000, 'dashboard API')
  if (!response.ok) {
    logDashboardApiFailure('GET /health', response, {})
    throw new Error(`Dashboard API health check failed with status ${response.status}`)
  }
}

export async function ensureAiApiReady() {
  const response = await fetchWithTimeout(aiUrl('/health/full'), {}, 20000, 'AI API')
  if (!response.ok) {
    throw new Error(`AI API health check failed with status ${response.status}`)
  }
}

/**
 * Analyze a single image using YOLO + VLM pipeline
 * @param {File} file - Image file
 * @param {number} confThreshold - YOLO confidence threshold (0.0-1.0)
 * @returns {Promise} Analysis result with detected objects
 */
export async function analyzeHybridImage(file, confThreshold = 0.25) {
  const formData = new FormData()
  formData.append('file', file)
  await ensureAiApiReady()

  // New full-stack path: /explain combines YOLO detection + VLM explanation.
  const explainResponse = await fetchWithTimeout(
    aiUrl(`/explain?conf_threshold=${confThreshold}`),
    {
      method: 'POST',
      body: formData,
    },
    REQUEST_TIMEOUT_MS,
    'AI API'
  )
  const explainData = await explainResponse.json().catch(() => ({}))

  if (!explainResponse.ok) {
    // Backward-compatible fallback for legacy backend deployments.
    const fallbackResponse = await fetchWithTimeout(
      aiUrl(`/analyze?conf_threshold=${confThreshold}`),
      {
        method: 'POST',
        body: formData,
      },
      REQUEST_TIMEOUT_MS,
      'AI API'
    )
    const fallbackData = await fallbackResponse.json().catch(() => ({}))
    if (!fallbackResponse.ok) {
      const merged = { detail: fallbackData.detail ?? explainData.detail }
      throw new Error(formatFastApiErrorDetail(merged, fallbackResponse) || 'Hybrid AI analysis failed')
    }
    return fallbackData
  }

  const mappedObjects = (explainData.detections || []).map((det) => ({
    yolo_label: det.label,
    yolo_confidence: (det.confidence || 0) * 100,
    vlm_object: det.label,
    condition: 'AI analyzed',
    details: explainData.caption || 'No caption generated.',
    suggestion: explainData.description || 'No recommendation generated.',
    eco_score: 70,
    box: det.box || [0, 0, 0, 0],
  }))

  return {
    status: explainData.status || 'success',
    image_name: explainData.image_name || file.name,
    detected_objects: mappedObjects,
    num_detections: mappedObjects.length,
    error_message: null,
  }
}

/**
 * Analyze multiple images using YOLO + VLM pipeline
 * @param {File[]} files - Array of image files
 * @param {number} confThreshold - YOLO confidence threshold
 * @returns {Promise} Batch analysis results
 */
export async function analyzeBatchImages(files, confThreshold = 0.25) {
  const formData = new FormData()
  await ensureAiApiReady()

  for (const file of files) {
    formData.append('files', file)
  }

  const response = await fetchWithTimeout(
    aiUrl(`/analyze-batch?conf_threshold=${confThreshold}`),
    {
      method: 'POST',
      body: formData,
    },
    REQUEST_TIMEOUT_MS,
    'AI API'
  )

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(formatFastApiErrorDetail(data, response) || `Batch analysis failed (HTTP ${response.status})`)
  }

  return data
}

/**
 * Get API health status
 * @returns {Promise} Health status
 */
export async function getApiHealth() {
  const response = await fetchWithTimeout(aiUrl('/health'), {}, 10000, 'AI API')
  const data = await response.json().catch(() => ({}))
  return data
}

/**
 * Train YOLO on custom dataset
 * @param {string} dataYamlPath - Path to data.yaml
 * @param {object} options - Training options (epochs, imgsz, batch_size)
 * @returns {Promise} Training result
 */
export async function trainYolo(dataYamlPath, options = {}) {
  const params = new URLSearchParams({
    data_yaml_path: dataYamlPath,
    epochs: options.epochs || 50,
    imgsz: options.imgsz || 640,
    batch_size: options.batch_size || 8,
  })

  const response = await fetch(aiUrl(`/train-yolo?${params}`), {
    method: 'POST',
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(formatFastApiErrorDetail(data, response) || `Training failed (HTTP ${response.status})`)
  }

  return data
}

/**
 * Load a custom YOLO model
 * @param {string} modelPath - Path to .pt file
 * @returns {Promise} Load result
 */
export async function loadCustomModel(modelPath) {
  const params = new URLSearchParams({ model_path: modelPath })

  const response = await fetch(aiUrl(`/load-model?${params}`), {
    method: 'POST',
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(formatFastApiErrorDetail(data, response) || `Model loading failed (HTTP ${response.status})`)
  }

  return data
}

/**
 * For backwards compatibility with old analyzeDeviceImages
 */
export async function analyzeDeviceImages(payload) {
  if (!payload?.images?.length) {
    throw new Error('At least one image is required')
  }

  try {
    await ensureAiApiReady()
    if (payload.images.length === 1) {
      const single = await analyzeHybridImage(payload.images[0])
      return toLegacyAiResponse(single)
    }

    const batch = await analyzeBatchImages(payload.images)
    const firstSuccess = batch?.results?.find((entry) => entry?.detected_objects?.length)

    if (!firstSuccess) {
      throw new Error('No supported device could be detected from the selected images')
    }

    return toLegacyAiResponse(firstSuccess)
  } catch (error) {
    if (error?.message?.includes('Cannot reach AI API')) {
      throw new Error('AI service is unavailable. Start backend/app.py on port 5000 or check /ai proxy config.')
    }
    throw error
  }
}

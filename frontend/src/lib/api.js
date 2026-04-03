const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const AI_ANALYZE_URL = import.meta.env.VITE_AI_ANALYZE_URL || 'http://127.0.0.1:5000'
const AI_REQUEST_TIMEOUT_MS = 25000

async function fetchWithTimeout(url, options = {}, timeoutMs = AI_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    })
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('AI analysis timed out. Please try again with a clearer image or a lower confidence threshold.')
    }
    throw error
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
  const response = await fetch(`${API_URL}${path}`, options)
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Request failed')
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

/**
 * Analyze a single image using YOLO + VLM pipeline
 * @param {File} file - Image file
 * @param {number} confThreshold - YOLO confidence threshold (0.0-1.0)
 * @returns {Promise} Analysis result with detected objects
 */
export async function analyzeHybridImage(file, confThreshold = 0.25) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetchWithTimeout(
    `${AI_ANALYZE_URL}/analyze?conf_threshold=${confThreshold}`,
    {
      method: 'POST',
      body: formData,
    }
  )

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Hybrid AI analysis failed')
  }

  return data
}

/**
 * Analyze multiple images using YOLO + VLM pipeline
 * @param {File[]} files - Array of image files
 * @param {number} confThreshold - YOLO confidence threshold
 * @returns {Promise} Batch analysis results
 */
export async function analyzeBatchImages(files, confThreshold = 0.25) {
  const formData = new FormData()

  for (const file of files) {
    formData.append('files', file)
  }

  const response = await fetchWithTimeout(
    `${AI_ANALYZE_URL}/analyze-batch?conf_threshold=${confThreshold}`,
    {
      method: 'POST',
      body: formData,
    }
  )

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Batch analysis failed')
  }

  return data
}

/**
 * Get API health status
 * @returns {Promise} Health status
 */
export async function getApiHealth() {
  const response = await fetch(`${AI_ANALYZE_URL}/health`)
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

  const response = await fetch(`${AI_ANALYZE_URL}/train-yolo?${params}`, {
    method: 'POST',
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Training failed')
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

  const response = await fetch(`${AI_ANALYZE_URL}/load-model?${params}`, {
    method: 'POST',
  })

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.detail || 'Model loading failed')
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
    if (error?.message?.includes('Failed to fetch')) {
      throw new Error('AI service is unavailable. Make sure the analysis backend is running on port 5000.')
    }
    throw error
  }
}

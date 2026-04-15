import { useEffect, useMemo, useRef, useState } from 'react'
import { ModelComparison } from '../components/ModelComparison'
import { ScanResultCard } from '../components/ScanResultCard'
import { useAuth } from '../context/AuthContext'
import { useLiveMetalPrices } from '../hooks/useLiveMetalPrices'
import { aiDeviceScan } from '../lib/api'
import { parseCsv } from '../lib/csv'
import { brandsForType, deviceTypes, findDeviceRow, modelsForBrand } from '../lib/datasetUtils'
import { saveDeviceEntry } from '../lib/deviceHistory'
import { computeManualValuation } from '../lib/valuation'

function normalizeValue(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
}

function confidenceToPercent(value) {
  const numeric = Number(value || 0)
  if (numeric <= 1) return Math.round(numeric * 100)
  return Math.round(numeric)
}

function confidenceLabel(value) {
  const percent = confidenceToPercent(value)
  if (percent < 50) return 'Low confidence'
  if (percent < 70) return 'Medium confidence'
  return 'High confidence'
}

function confidenceTone(value, explicitLabel = '') {
  const normalized = String(explicitLabel || '').toLowerCase()
  if (normalized === 'high' || normalized === 'medium' || normalized === 'low') return normalized
  const percent = confidenceToPercent(value)
  if (percent < 50) return 'low'
  if (percent < 70) return 'medium'
  return 'high'
}

function damageConfidenceLabel(value) {
  const percent = confidenceToPercent(value)
  if (percent < 55) return 'Low damage certainty'
  if (percent < 75) return 'Medium damage certainty'
  return 'High damage certainty'
}

function displayDamageLabel(value) {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'broken' || normalized === 'damaged') return 'Damaged'
  if (normalized === 'not broken') return 'Not Damaged'
  return value || 'Not Damaged'
}

function toMlCondition(condition) {
  const normalized = String(condition || '')
    .trim()
    .toLowerCase()
  if (normalized === 'average') return 'fair'
  if (normalized === 'poor') return 'poor'
  if (normalized === 'excellent') return 'excellent'
  return 'good'
}

function buildValidationResult({
  status,
  message,
  aiResult = null,
  matchScore = 0,
  reasons = [],
  manualSnapshot,
}) {
  return {
    validation: {
      status,
      message,
      matchScore,
      aiDetectedDevice: aiResult?.detected_device || 'Not detected',
      aiCondition: aiResult?.vlm_condition || aiResult?.ai_condition || 'Not analyzed',
      aiSuggestion: aiResult?.suggestion || '',
      aiConfidence: confidenceToPercent(aiResult?.confidence || 0),
      aiConfidenceLabel: confidenceLabel(aiResult?.confidence || 0),
      aiDamageConfidence: confidenceToPercent(aiResult?.damage_confidence || 0),
      aiDamageConfidenceLabel: damageConfidenceLabel(aiResult?.damage_confidence || 0),
      reasons,
      requiresImage: status === 'missing-image',
    },
    aiDetected: aiResult
      ? {
          detected_device_type: aiResult?.detected_device || 'mobile',
          confidence: aiResult?.confidence ?? 0.4,
          confidence_label: aiResult?.confidence_label || 'low',
          damage_confidence: aiResult?.damage_confidence ?? aiResult?.confidence ?? 0.4,
          detected_objects: aiResult?.detected_objects || [],
        }
      : null,
    deviceInfo: manualSnapshot,
  }
}

export function ScanPage() {
  const scanSectionRef = useRef(null)
  const { token } = useAuth()
  const liveMetalPrices = useLiveMetalPrices()
  const [dataset, setDataset] = useState([])
  const [loadError, setLoadError] = useState('')

  const [deviceType, setDeviceType] = useState('')
  const [brand, setBrand] = useState('')
  const [model, setModel] = useState('')

  const [ageYears, setAgeYears] = useState(3)
  const [conditionLabel, setConditionLabel] = useState('Good')
  const [screenDamage, setScreenDamage] = useState('No')
  const [bodyDamage, setBodyDamage] = useState('No')
  const [waterDamage, setWaterDamage] = useState('No')

  const [result, setResult] = useState(null)
  const [predictions, setPredictions] = useState([])
  const [bestModel, setBestModel] = useState('')
  const [selectedFiles, setSelectedFiles] = useState([])
  const [previewImages, setPreviewImages] = useState([])
  const [hoveredPreview, setHoveredPreview] = useState(-1)
  const [imageLoading, setImageLoading] = useState(false)
  const [imageError, setImageError] = useState('')

  useEffect(() => {
    return () => {
      previewImages.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
    }
  }, [previewImages])

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const res = await fetch(`${import.meta.env.BASE_URL}datasets/devices.csv`)
        if (!res.ok) throw new Error('Could not load devices.csv')
        const text = await res.text()
        const rows = parseCsv(text)

        if (cancelled) return

        setDataset(rows)
        const types = deviceTypes(rows)
        if (types[0]) {
          setDeviceType(types[0])
          const firstBrand = brandsForType(rows, types[0])[0]
          setBrand(firstBrand || '')
          const firstModel = modelsForBrand(rows, types[0], firstBrand || '')[0]
          setModel(firstModel || '')
        }
      } catch (error) {
        if (!cancelled) setLoadError(error.message || 'Failed to load dataset')
      }
    }

    load()

    return () => {
      cancelled = true
    }
  }, [])

  const types = useMemo(() => deviceTypes(dataset), [dataset])
  const brands = useMemo(() => (deviceType ? brandsForType(dataset, deviceType) : []), [dataset, deviceType])
  const models = useMemo(
    () => (deviceType && brand ? modelsForBrand(dataset, deviceType, brand) : []),
    [dataset, deviceType, brand],
  )

  useEffect(() => {
    if (!deviceType || !brands.length) return
    if (!brands.includes(brand)) {
      setBrand(brands[0] || '')
    }
  }, [deviceType, brands, brand])

  useEffect(() => {
    if (!deviceType || !brand || !models.length) return
    if (!models.includes(model)) {
      setModel(models[0] || '')
    }
  }, [deviceType, brand, models, model])

  const selectedRow = useMemo(
    () => findDeviceRow(dataset, deviceType, brand, model),
    [dataset, deviceType, brand, model],
  )

  const form = useMemo(
    () => ({
      ageYears,
      conditionLabel,
      screenDamage,
      bodyDamage,
      waterDamage,
    }),
    [ageYears, conditionLabel, screenDamage, bodyDamage, waterDamage],
  )

  function getPrimaryDetection(analysis) {
    if (!analysis) return null
    if (Array.isArray(analysis.detected_objects) && analysis.detected_objects.length > 0) {
      return analysis.detected_objects[0]
    }
    if (Array.isArray(analysis.results)) {
      for (const entry of analysis.results) {
        if (Array.isArray(entry.detected_objects) && entry.detected_objects.length > 0) {
          return entry.detected_objects[0]
        }
      }
    }
    return null
  }

  function mapDetectedCondition(rawCondition) {
    const normalized = normalizeValue(rawCondition)
    if (normalized.includes('working') || normalized.includes('good') || normalized.includes('excellent')) {
      return 'Good'
    }
    if (normalized.includes('average') || normalized.includes('fair')) {
      return 'Average'
    }
    return 'Poor'
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!selectedRow) return

    const manualSnapshot = {
      deviceType,
      brand,
      model,
      ageYears,
      conditionLabel,
      screenDamage,
      bodyDamage,
      waterDamage,
    }

    if (!token) {
      setImageError('Sign in required before calculating an AI-verified estimate.')
      return
    }

    if (selectedFiles.length === 0) {
      setImageError('')
      setResult(
        buildValidationResult({
          status: 'missing-image',
          message:
            'Please attach at least one image for proper justification. The estimate is blocked until the AI scan can verify the device and condition.',
          manualSnapshot,
        }),
      )
      return
    }

    if (selectedFiles.length > 4) {
      setImageError('Upload between 1 and 4 images for AI analysis.')
      return
    }

    setImageLoading(true)
    setImageError('')
    setPredictions([])
    setBestModel('')

    try {
      const response = await aiDeviceScan(token, {
        images: selectedFiles,
        device_type: deviceType,
        brand,
        model,
        age: ageYears,
        condition: conditionLabel,
        screen_damage: screenDamage === 'Yes',
        body_damage: bodyDamage === 'Yes',
        water_damage: waterDamage === 'Yes',
      })
      if (!response.success) {
        const mismatchMessage = response.error || 'User input does not match AI-detected device'
        setImageError(mismatchMessage)
        setResult(
          buildValidationResult({
            status: 'mismatch',
            message: mismatchMessage,
            aiResult: response.detected || null,
            matchScore: Number(response.match_score ?? 0),
            reasons: Array.isArray(response.reasons) ? response.reasons : [],
            manualSnapshot,
          }),
        )
        return
      }

      const primaryDetection = getPrimaryDetection(response.final_analysis)
      let priceSnapshot = liveMetalPrices.prices
      if (!priceSnapshot) {
        try {
          priceSnapshot = await liveMetalPrices.refreshPrices({ force: true })
        } catch {
          priceSnapshot = null
        }
      }

      const computed = computeManualValuation(selectedRow, form, priceSnapshot)
      computed.validation = {
        status: 'approved',
        message: 'AI verification passed. The image and manual input are aligned well enough to show the estimate.',
        matchScore: Number(response.match_score ?? 100),
        aiDetectedDevice: response.detected?.detected_device_type || 'unknown',
        aiCondition:
          response.detected?.condition ||
          response.detected?.vlm_condition ||
          mapDetectedCondition(response.detected?.detected_condition || ''),
        aiSuggestion: primaryDetection?.suggestion || '',
        aiConfidence: confidenceToPercent(response.detected?.confidence || 0),
        aiConfidenceLabel: response.detected?.confidence_label
          ? `${String(response.detected.confidence_label).charAt(0).toUpperCase()}${String(response.detected.confidence_label).slice(1)} confidence`
          : confidenceLabel(response.detected?.confidence || 0),
        aiDamageConfidence: confidenceToPercent(response.detected?.damage_confidence ?? response.detected?.confidence ?? 0),
        aiDamageConfidenceLabel: damageConfidenceLabel(
          response.detected?.damage_confidence ?? response.detected?.confidence ?? 0,
        ),
        reasons: Array.isArray(response.reasons) ? response.reasons : [],
      }
      computed.aiDetected = response.detected
      computed.finalAnalysis = response.final_analysis

      let mlPrediction = null
      try {
        const conditionScore =
          conditionLabel === 'Good' ? 0.9 : conditionLabel === 'Average' ? 0.6 : 0.3
        const batteryHealth =
          conditionLabel === 'Good' ? 90 : conditionLabel === 'Average' ? 70 : 50
        const depreciationRate = Math.min(0.95, Math.max(0.1, Number(ageYears) * 0.1))
        const demandScore =
          conditionLabel === 'Good' ? 0.85 : conditionLabel === 'Average' ? 0.6 : 0.4
        const mlPayload = {
          Device_Type: deviceType,
          Brand: brand,
          Model: model,
          Age_Years: Number(ageYears),
          Condition_Label: conditionLabel,
          Condition_Score: conditionScore,
          Screen_Damage: screenDamage,
          Body_Damage: bodyDamage,
          Battery_Health: batteryHealth,
          Original_Price: Number(computed.basePrice || selectedRow?.original_price || 10000),
          Depreciation_Rate: depreciationRate,
          Demand_Score: demandScore,
        }
        console.log('ML PAYLOAD:', mlPayload)
        const mlResponse = await fetch('http://127.0.0.1:8765/predict', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(mlPayload),
        })
        const mlData = await mlResponse.json().catch(() => ({}))
        console.log('ML STATUS:', mlResponse.status)
        console.log('ML DATA:', mlData)
        if (!mlResponse.ok) {
          throw new Error(mlData?.detail || mlData?.message || `ML API ${mlResponse.status}`)
        }

        const preds = (mlData?.predictions || mlData?.model_comparison || []).map((p) => ({
          model: p?.model || p?.name || p?.model_name || p?.model_key,
          price: Number(p?.price || p?.value || p?.predicted_price || 0),
          accuracy: p?.accuracy || p?.r2 || 0,
        }))
        setPredictions(preds)
        setBestModel(mlData?.best_model || '')
        console.log('PREDICTIONS STATE:', preds)

        // TEMP hard test: verify frontend rendering path if backend returns no predictions.
        if (!Array.isArray(mlData?.predictions) && !Array.isArray(mlData?.model_comparison)) {
          setPredictions([
            { model: 'Linear Regression', price: 58000 },
            { model: 'Random Forest', price: 62625 },
            { model: 'KMeans', price: 42000 },
          ])
        }

        const normalizedPreds = Array.isArray(preds)
          ? preds.map((p, idx) => ({
              model: p?.model || p?.model_name || p?.model_key || `Model ${idx + 1}`,
              price: Number(p?.price ?? p?.predicted_price ?? 0),
            }))
          : []
        const bestPrediction = normalizedPreds.find((p) => p.model === (mlData?.best_model || ''))
        const bestPrice = bestPrediction?.price ?? bestPrediction?.predicted_price
        if (Number.isFinite(Number(bestPrice))) {
          mlData.best_price = Number(bestPrice)
          // Make scan's estimated value follow best-model ML price.
          computed.resaleValue = Number(bestPrice)
        }

        mlPrediction = {
          ...mlData,
          predictions: Array.isArray(preds) ? preds : [],
          best_model: mlData?.best_model || '',
        }
        const bp = mlPrediction.best_price
        if (bp == null || Number.isNaN(Number(bp))) {
          mlPrediction = null
        }
      } catch {
        mlPrediction = null
        setPredictions([])
        setBestModel('')
      }
      computed.mlPrediction = mlPrediction

      setResult(computed)
      saveDeviceEntry(computed)
    } catch (error) {
      const raw = String(error?.message || 'AI analysis failed')
      const looksDisconnected =
        /404|Not Found|Cannot reach|timed out|Failed to fetch|NetworkError|route not found/i.test(raw)
      setImageError(
        looksDisconnected
          ? 'Backend not connected. Please start the FastAPI server on port 8000 (from backend: uvicorn app.main:app --host 0.0.0.0 --port 8000).'
          : raw,
      )
      if (import.meta.env.DEV) {
        console.error('[ScanPage] aiDeviceScan failed', error)
      }
    } finally {
      setImageLoading(false)
    }
  }

  function handleImageSelection(event) {
    const files = Array.from(event.target.files || [])
    if (!files.length) {
      setSelectedFiles([])
      setPreviewImages((prev) => {
        prev.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
        return []
      })
      setImageError('')
      return
    }

    const validMime = new Set(['image/jpeg', 'image/png', 'image/jpg'])
    const invalidFiles = files.filter((file) => !validMime.has(file.type))
    if (invalidFiles.length > 0) {
      setImageError('Only JPG and PNG images are allowed.')
    } else {
      setImageError('')
    }

    const filtered = files.filter((file) => validMime.has(file.type)).slice(0, 4)
    if (files.length > 4) {
      setImageError('Upload between 1 and 4 images for AI analysis.')
    }

    setSelectedFiles(filtered)
    setPreviewImages((prev) => {
      prev.forEach((previewUrl) => URL.revokeObjectURL(previewUrl))
      return filtered.map((file) => URL.createObjectURL(file))
    })
  }

  function handleRemoveImage(index) {
    setSelectedFiles((prev) => prev.filter((_, currentIndex) => currentIndex !== index))
    setPreviewImages((prev) => {
      const copy = [...prev]
      const [removed] = copy.splice(index, 1)
      if (removed) URL.revokeObjectURL(removed)
      return copy
    })
  }

  function scrollToScanSection() {
    scanSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas scan-hero-experience premium-hero-section">
        <div className="scan-hero-copy">
          <span className="eyebrow eyebrow-indigo">AI device workflow</span>
          <h1 className="dashboard-title">AI Device Scan & Analysis</h1>
          <p className="dashboard-subtitle">
            Upload your device image and get instant AI-powered condition analysis and valuation.
          </p>
          <div className="scan-hero-features">
            <div className="scan-hero-feature">AI Detection (YOLO)</div>
            <div className="scan-hero-feature">Condition Analysis (VLM)</div>
            <div className="scan-hero-feature">Smart Valuation</div>
          </div>
          <button type="button" className="primary-button" onClick={scrollToScanSection}>
            Start Scan
          </button>
        </div>
      </section>

      <section className="content-grid scan-workspace-grid" ref={scanSectionRef}>
        <div className="glass-panel panel-hover saas-card premium-panel">
          <h2 className="panel-title">AI Device Scan & Analysis</h2>
          <p className="panel-subtitle">
            Upload 1 to 4 images, complete manual input, then run one unified AI scan.
          </p>
          {loadError ? <div className="error-banner">{loadError}</div> : null}

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="manual-ai-panel">
              <div className="manual-ai-copy">
                <span className="manual-ai-label">AI image scan</span>
                <p className="panel-subtitle">
                  Step 1: Upload at least one image. Step 2: complete all manual fields. Step 3: Run AI Scan.
                </p>
              </div>

              <div className="upload-dropzone manual-upload-dropzone">
                <input
                  type="file"
                  multiple
                  accept=".jpg,.jpeg,.png,image/png,image/jpeg"
                  onChange={handleImageSelection}
                />
                <span className="upload-meta">
                  {selectedFiles.length
                    ? `${selectedFiles.length} image${selectedFiles.length > 1 ? 's' : ''} selected`
                    : 'PNG or JPG, multiple upload enabled'}
                </span>
              </div>

            </div>

            {previewImages.length > 0 ? (
              <div className="scan-previews-wrap">
                <span className="manual-ai-label">Image previews</span>
                <div className={`scan-preview-grid${previewImages.length === 1 ? ' single' : ''}`}>
                  {previewImages.map((previewUrl, index) => (
                    <div
                      key={previewUrl}
                      onMouseEnter={() => setHoveredPreview(index)}
                      onMouseLeave={() => setHoveredPreview(-1)}
                      className={`scan-preview-card${hoveredPreview === index ? ' active' : ''}`}
                    >
                      <img
                        src={previewUrl}
                        alt={`Selected preview ${index + 1}`}
                        className="scan-preview-image"
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveImage(index)}
                        className="scan-preview-remove"
                        aria-label={`Remove image ${index + 1}`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {imageError ? <div className="error-banner">{imageError}</div> : null}

            <div className="field">
              <label htmlFor="dev-type">Device type</label>
              <select
                id="dev-type"
                value={deviceType}
                onChange={(event) => {
                  const nextType = event.target.value
                  const nextBrands = brandsForType(dataset, nextType)
                  const nextBrand = nextBrands[0] || ''
                  const nextModels = modelsForBrand(dataset, nextType, nextBrand)
                  const nextModel = nextModels[0] || ''

                  setDeviceType(nextType)
                  setBrand(nextBrand)
                  setModel(nextModel)
                }}
              >
                {types.map((entry) => (
                  <option key={entry} value={entry}>
                    {entry}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="dev-brand">Brand</label>
              <select
                id="dev-brand"
                value={brands.includes(brand) ? brand : ''}
                onChange={(event) => {
                  const nextBrand = event.target.value
                  const nextModels = modelsForBrand(dataset, deviceType, nextBrand)
                  setBrand(nextBrand)
                  setModel(nextModels[0] || '')
                }}
                disabled={!brands.length}
              >
                {brands.map((entry) => (
                  <option key={entry} value={entry}>
                    {entry}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="dev-model">Model</label>
              <select
                id="dev-model"
                value={models.includes(model) ? model : ''}
                onChange={(event) => setModel(event.target.value)}
                disabled={!models.length}
              >
                {models.map((entry) => (
                  <option key={entry} value={entry}>
                    {entry}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="age-y">Age (years)</label>
              <input
                id="age-y"
                type="number"
                min={1}
                max={15}
                value={ageYears}
                onChange={(event) => setAgeYears(Number(event.target.value) || 1)}
              />
            </div>

            <div className="field">
              <label htmlFor="cond-l">Condition</label>
              <select id="cond-l" value={conditionLabel} onChange={(event) => setConditionLabel(event.target.value)}>
                <option>Good</option>
                <option>Average</option>
                <option>Poor</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor="scr-d">Screen damage</label>
              <select id="scr-d" value={screenDamage} onChange={(event) => setScreenDamage(event.target.value)}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor="bod-d">Body damage</label>
              <select id="bod-d" value={bodyDamage} onChange={(event) => setBodyDamage(event.target.value)}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor="water-d">Water damage</label>
              <select id="water-d" value={waterDamage} onChange={(event) => setWaterDamage(event.target.value)}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </div>

            <button type="submit" className="primary-button" disabled={!selectedRow || selectedFiles.length === 0 || imageLoading}>
              {imageLoading ? 'Running AI scan...' : 'Run AI Scan'}
            </button>
          </form>
        </div>

        <div className="glass-panel panel-hover saas-card premium-panel">
          <h2 className="panel-title">B. Result</h2>
          <p className="panel-subtitle">Estimated value, metal composition value, profit/loss, and recommended action.</p>
          {result?.aiDetected ? (
            <div className="scan-detected-summary">
              <strong className="scan-detected-title">Detected results</strong>
              <div className="scan-detected-line">
                Device: <strong>{result.aiDetected.detected_device_type || 'Not detected'}</strong>
              </div>
              <div className="scan-detected-line">
                Confidence: <strong>{confidenceToPercent(result.aiDetected.confidence)}%</strong> (
                {result.aiDetected.confidence_label
                  ? `${String(result.aiDetected.confidence_label).charAt(0).toUpperCase()}${String(result.aiDetected.confidence_label).slice(1)}`
                  : confidenceLabel(result.aiDetected.confidence).replace(' confidence', '')}
                )
              </div>
              <div className="scan-detected-line">
                <span className={`confidence-badge ${confidenceTone(result.aiDetected.confidence, result.aiDetected.confidence_label)}`}>
                  {confidenceTone(result.aiDetected.confidence, result.aiDetected.confidence_label).toUpperCase()}
                </span>
              </div>
              <div className="scan-detected-line score">
                Match score: <strong>{result.validation?.matchScore ?? 0}%</strong>
              </div>
              {(result.validation?.reasons || [])
                .filter((reason) => String(reason || '').trim().toLowerCase() !== 'major condition difference')
                .slice(0, 2)
                .map((reason) => (
                <div key={reason} className="result-warning-line">
                  {'\u26A0'} {reason}
                </div>
              ))}
              <div className="scan-detected-line">
                VLM condition: <strong>{result.aiDetected.vlm_condition || 'Average'}</strong> | Damage:{' '}
                <strong>{displayDamageLabel(result.aiDetected.vlm_damage)}</strong>
              </div>
              <div className="scan-detected-line">
                Damage confidence:{' '}
                <strong>{confidenceToPercent(result.aiDetected.damage_confidence ?? result.aiDetected.confidence)}%</strong>{' '}
                ({damageConfidenceLabel(result.aiDetected.damage_confidence ?? result.aiDetected.confidence)})
              </div>
              {String(result.aiDetected.confidence_label || '').toLowerCase() === 'low' ? (
                <div className="error-banner scan-detected-warning">
                  Low confidence detection - result may vary
                </div>
              ) : null}
              {confidenceToPercent(result.aiDetected.damage_confidence ?? result.aiDetected.confidence) < 60 ? (
                <div className="error-banner scan-detected-warning">
                  Damage certainty is low - upload a close-up crack image for stronger verification.
                </div>
              ) : null}
              {result.aiDetected.detected_objects?.length ? null : (
                <div className="scan-detected-empty">No supported device boxes detected.</div>
              )}
            </div>
          ) : null}
          <ScanResultCard scan={result} liveMetalPrices={liveMetalPrices} />
          {predictions && predictions.length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <ModelComparison predictions={predictions} bestModel={bestModel} />
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}

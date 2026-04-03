import { useEffect, useMemo, useState } from 'react'
import { ScanResultCard } from '../components/ScanResultCard'
import { useAuth } from '../context/AuthContext'
import { parseCsv } from '../lib/csv'
import { brandsForType, deviceTypes, findDeviceRow, modelsForBrand } from '../lib/datasetUtils'
import { saveDeviceEntry } from '../lib/deviceHistory'
import { analyzeDeviceImages } from '../lib/api'
import { computeManualValuation } from '../lib/valuation'

const AI_DEVICE_MAP = {
  phone: 'Phone',
  laptop: 'Laptop',
  tablet: 'Tablet',
  charger: 'Charger',
  powerbank: 'Powerbank',
  pcb: 'PCB',
}

const AI_CONDITION_MAP = {
  Excellent: 'Good',
  Good: 'Good',
  Fair: 'Average',
  Poor: 'Poor',
}

function normalizeValue(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
}

function buildValidationResult({
  status,
  message,
  aiResult = null,
  matchScore = 0,
  manualSnapshot,
}) {
  return {
    validation: {
      status,
      message,
      matchScore,
      aiDetectedDevice: aiResult?.detected_device || 'Not detected',
      aiCondition: aiResult?.ai_condition || 'Not analyzed',
      aiSuggestion: aiResult?.suggestion || '',
      aiConfidence: Math.round(aiResult?.confidence || 0),
      requiresImage: status === 'missing-image',
    },
    deviceInfo: manualSnapshot,
  }
}

export function ScanPage() {
  const { token } = useAuth()
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
  const [selectedFiles, setSelectedFiles] = useState([])
  const [imageLoading, setImageLoading] = useState(false)
  const [imageError, setImageError] = useState('')

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

  function resolveAiDeviceType(aiDevice) {
    const mapped = AI_DEVICE_MAP[String(aiDevice || '').trim().toLowerCase()]
    if (!mapped) return ''
    return types.find((entry) => entry.toLowerCase() === mapped.toLowerCase()) || ''
  }

  function calculateMatchScore(aiResult) {
    const normalizedManualType = normalizeValue(deviceType)
    const normalizedAiType = normalizeValue(resolveAiDeviceType(aiResult.detected_device) || aiResult.detected_device)
    const normalizedManualCondition = normalizeValue(conditionLabel)
    const normalizedAiCondition = normalizeValue(AI_CONDITION_MAP[aiResult.ai_condition] || aiResult.ai_condition)
    const aiConfidence = Number(aiResult.confidence) || 0

    let score = 0

    if (normalizedAiType && normalizedAiType === normalizedManualType) {
      score += 50
    } else if (
      (!normalizedAiType || normalizedAiType === 'unknown') &&
      aiConfidence >= 60
    ) {
      // If the image analysis is reasonably confident but cannot name the device,
      // give partial credit instead of blocking otherwise-valid photos.
      score += 40
    }

    if (normalizedAiCondition && normalizedAiCondition === normalizedManualCondition) {
      score += 30
    } else if (
      (normalizedManualCondition === 'good' && normalizedAiCondition === 'average') ||
      (normalizedManualCondition === 'average' && normalizedAiCondition === 'good')
    ) {
      score += 20
    }

    score += Math.min(20, Math.round(aiConfidence / 5))

    return Math.min(100, score)
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

    try {
      const aiResult = await analyzeDeviceImages({
        deviceType,
        model,
        condition: conditionLabel,
        age: ageYears,
        images: selectedFiles,
      })
      const matchScore = calculateMatchScore(aiResult)

      if (matchScore < 70) {
        setResult(
          buildValidationResult({
            status: 'mismatch',
            message:
              'Manual input and AI scan do not match strongly enough. Please insert an appropriate image or correct the manual details, then calculate again.',
            aiResult,
            matchScore,
            manualSnapshot,
          }),
        )
        return
      }

      const computed = computeManualValuation(selectedRow, form)
      computed.validation = {
        status: 'approved',
        message: 'AI verification passed. The image and manual input are aligned well enough to show the estimate.',
        matchScore,
        aiDetectedDevice: aiResult.detected_device,
        aiCondition: aiResult.ai_condition,
        aiSuggestion: aiResult.suggestion || '',
        aiConfidence: Math.round(aiResult.confidence || 0),
      }
      setResult(computed)
      saveDeviceEntry(computed)
    } catch (error) {
      setImageError(error.message || 'AI analysis failed')
    } finally {
      setImageLoading(false)
    }
  }

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas">
        <span className="eyebrow eyebrow-indigo">Core system</span>
        <h1 className="dashboard-title">SmartDeviceAI Dashboard</h1>
        <p className="dashboard-subtitle">
          Blend AI-assisted verification with manual lifecycle inputs to produce a clean, reviewable device estimate.
        </p>
      </section>

      <section className="content-grid">
        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">A. Manual input</h2>
          <p className="panel-subtitle">
            Add manual device details and attach 1 to 4 images. The final estimate appears only after the AI scan and
            manual input match at 70% or higher.
          </p>
          {loadError ? <div className="error-banner">{loadError}</div> : null}

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="manual-ai-panel">
              <div className="manual-ai-copy">
                <span className="manual-ai-label">AI image scan</span>
                <p className="panel-subtitle">
                  Use 1 to 4 device images. The AI check runs automatically when you click Calculate estimate.
                </p>
              </div>

              <div className="upload-dropzone manual-upload-dropzone">
                <input
                  type="file"
                  multiple
                  accept="image/png,image/jpeg,image/jpg"
                  onChange={(event) => {
                    setSelectedFiles(Array.from(event.target.files || []))
                    setImageError('')
                  }}
                />
                <span className="upload-meta">
                  {selectedFiles.length
                    ? `${selectedFiles.length} image${selectedFiles.length > 1 ? 's' : ''} selected`
                    : 'PNG or JPG, multiple upload enabled'}
                </span>
              </div>

            </div>

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

            <button type="submit" className="primary-button" disabled={!selectedRow}>
              {imageLoading ? 'Analyzing image and calculating...' : 'Calculate estimate'}
            </button>
          </form>
        </div>

        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">B. Result</h2>
          <p className="panel-subtitle">Estimated value, metal composition value, profit/loss, and recommended action.</p>
          <ScanResultCard scan={result} />
        </div>
      </section>
    </div>
  )
}

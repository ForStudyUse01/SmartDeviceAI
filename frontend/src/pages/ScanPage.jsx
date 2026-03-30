import { useEffect, useMemo, useState } from 'react'
import { ScanResultCard } from '../components/ScanResultCard'
import { parseCsv } from '../lib/csv'
import { brandsForType, deviceTypes, findDeviceRow, modelsForBrand } from '../lib/datasetUtils'
import { saveDeviceEntry } from '../lib/deviceHistory'
import { computeManualValuation } from '../lib/valuation'
import { useAuth } from '../context/AuthContext'
import { uploadScan } from '../lib/api'

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

  const [selectedFile, setSelectedFile] = useState(null)
  const [imageLoading, setImageLoading] = useState(false)
  const [imageError, setImageError] = useState('')
  const [imageResult, setImageResult] = useState(null)

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
          const b0 = brandsForType(rows, types[0])[0]
          setBrand(b0 || '')
          const m0 = modelsForBrand(rows, types[0], b0)[0]
          setModel(m0 || '')
        }
      } catch (e) {
        if (!cancelled) setLoadError(e.message || 'Failed to load dataset')
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
      const b = brands[0]
      if (b) setBrand(b)
    }
  }, [deviceType, brands, brand])

  useEffect(() => {
    if (!deviceType || !brand || !models.length) return
    if (!models.includes(model)) {
      const m = models[0]
      if (m) setModel(m)
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

  function handleSubmit(event) {
    event.preventDefault()
    if (!selectedRow) return
    const computed = computeManualValuation(selectedRow, form)
    setResult(computed)
    saveDeviceEntry(computed)
  }

  async function handleImageScan(event) {
    event.preventDefault()
    if (!selectedFile || !token) {
      setImageError(!token ? 'Sign in required for image scan.' : 'Choose an image first.')
      return
    }
    setImageLoading(true)
    setImageError('')
    try {
      const res = await uploadScan(token, selectedFile)
      setImageResult(res)
    } catch (e) {
      setImageError(e.message || 'Scan failed')
    } finally {
      setImageLoading(false)
    }
  }

  return (
    <div className="dashboard-layout">
      <section className="page-hero-saas">
        <span className="eyebrow eyebrow-indigo">Core system</span>
        <h1 className="dashboard-title">Scan device</h1>
        <p className="dashboard-subtitle">
          Linked device selection, condition &amp; damage inputs, static metal recovery pricing, and intelligent
          recommendations.
        </p>
      </section>

      <section className="content-grid">
        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">A. Device input</h2>
          <p className="panel-subtitle">Cascade: device type → brand → model. All fields drive the estimate.</p>
          {loadError ? <div className="error-banner">{loadError}</div> : null}
          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="dev-type">Device type</label>
              <select
                id="dev-type"
                value={deviceType}
                onChange={(e) => {
                  const t = e.target.value
                  setDeviceType(t)
                  const bs = brandsForType(dataset, t)
                  setBrand(bs[0] || '')
                  const ms = modelsForBrand(dataset, t, bs[0] || '')
                  setModel(ms[0] || '')
                }}
              >
                {types.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="dev-brand">Brand</label>
              <select
                id="dev-brand"
                value={brands.includes(brand) ? brand : ''}
                onChange={(e) => {
                  const b = e.target.value
                  setBrand(b)
                  const ms = modelsForBrand(dataset, deviceType, b)
                  setModel(ms[0] || '')
                }}
                disabled={!brands.length}
              >
                {brands.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="dev-model">Model</label>
              <select
                id="dev-model"
                value={models.includes(model) ? model : ''}
                onChange={(e) => setModel(e.target.value)}
                disabled={!models.length}
              >
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m}
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
                onChange={(e) => setAgeYears(Number(e.target.value) || 1)}
              />
            </div>
            <div className="field">
              <label htmlFor="cond-l">Condition</label>
              <select id="cond-l" value={conditionLabel} onChange={(e) => setConditionLabel(e.target.value)}>
                <option>Good</option>
                <option>Average</option>
                <option>Poor</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="scr-d">Screen damage</label>
              <select id="scr-d" value={screenDamage} onChange={(e) => setScreenDamage(e.target.value)}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="bod-d">Body damage</label>
              <select id="bod-d" value={bodyDamage} onChange={(e) => setBodyDamage(e.target.value)}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="water-d">Water damage</label>
              <select id="water-d" value={waterDamage} onChange={(e) => setWaterDamage(e.target.value)}>
                <option>No</option>
                <option>Yes</option>
              </select>
            </div>

            <button type="submit" className="primary-button" disabled={!selectedRow}>
              Calculate estimate
            </button>
          </form>

          <div className="scan-image-section">
            <h3 className="panel-title" style={{ fontSize: '1.05rem', marginTop: 24 }}>
              Optional: AI image scan
            </h3>
            <p className="panel-subtitle">Upload a device photo — uses existing backend classifier (requires login).</p>
            <form className="upload-form" onSubmit={handleImageScan}>
              <div className="upload-dropzone">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/jpg"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                />
              </div>
              {imageError ? <div className="error-banner">{imageError}</div> : null}
              <button className="secondary-button" type="submit" disabled={imageLoading}>
                {imageLoading ? 'Scanning…' : 'Run image scan'}
              </button>
            </form>
            {imageResult ? (
              <div style={{ marginTop: 16 }}>
                <ScanResultCard scan={imageResult} />
              </div>
            ) : null}
          </div>
        </div>

        <div className="glass-panel panel-hover saas-card">
          <h2 className="panel-title">B. Result</h2>
          <p className="panel-subtitle">Estimated value, metal composition value, P/L, recommended action.</p>
          <ScanResultCard scan={result} />
        </div>
      </section>
    </div>
  )
}

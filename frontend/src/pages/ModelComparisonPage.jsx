import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import devicePriceCatalog from '../data/devicePriceCatalog.json'

const ML_API_URL = 'http://127.0.0.1:8765/predict'

const deviceTypes = Object.keys(devicePriceCatalog)
const firstDeviceType = deviceTypes[0] || ''
const firstBrands = Object.keys(devicePriceCatalog[firstDeviceType] || {})
const firstBrand = firstBrands[0] || ''
const firstModels = Object.keys(devicePriceCatalog[firstDeviceType]?.[firstBrand] || {})
const firstModel = firstModels[0] || ''
const firstPrice = Number(devicePriceCatalog[firstDeviceType]?.[firstBrand]?.[firstModel] || 0)

const initialForm = {
  Device_Type: firstDeviceType,
  Brand: firstBrand,
  Model: firstModel,
  Age_Years: 2,
  Condition_Label: 'Good',
  Condition_Score: 8,
  Screen_Damage: 'No',
  Body_Damage: 'No',
  Battery_Health: 90,
  Original_Price: firstPrice,
}

const conditionScoreOptions = {
  Good: [8, 9, 10],
  Average: [4, 5, 6, 7],
  Poor: [0, 1, 2, 3],
}

function toNumber(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function formatApiError(detail, status) {
  if (Array.isArray(detail)) {
    return detail
      .map((entry) => {
        if (typeof entry === 'string') return entry
        const loc = Array.isArray(entry?.loc) ? entry.loc.join('.') : 'field'
        const msg = entry?.msg || JSON.stringify(entry)
        return `${loc}: ${msg}`
      })
      .join(' | ')
  }
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return `ML API ${status}`
}

export function ModelComparisonPage() {
  const [form, setForm] = useState(initialForm)
  const [predictions, setPredictions] = useState([])
  const [inputData, setInputData] = useState(null)
  const [bestModel, setBestModel] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const availableBrands = useMemo(
    () => Object.keys(devicePriceCatalog[form.Device_Type] || {}),
    [form.Device_Type],
  )
  const availableModels = useMemo(
    () => Object.keys(devicePriceCatalog[form.Device_Type]?.[form.Brand] || {}),
    [form.Device_Type, form.Brand],
  )
  const availableConditionScores = useMemo(
    () => conditionScoreOptions[form.Condition_Label] || conditionScoreOptions.Good,
    [form.Condition_Label],
  )

  const normalizedPredictions = useMemo(
    () =>
      (predictions || []).map((p, idx) => ({
        model: p?.model || p?.name || p?.model_name || p?.model_key || `Model ${idx + 1}`,
        price: toNumber(p?.price ?? p?.value ?? p?.predicted_price),
        accuracy: toNumber(p?.accuracy ?? p?.r2),
      })),
    [predictions],
  )

  function updateField(key, value) {
    setForm((prev) => {
      const next = { ...prev, [key]: value }

      if (key === 'Device_Type') {
        const brands = Object.keys(devicePriceCatalog[value] || {})
        const nextBrand = brands[0] || ''
        const models = Object.keys(devicePriceCatalog[value]?.[nextBrand] || {})
        const nextModel = models[0] || ''
        next.Brand = nextBrand
        next.Model = nextModel
        next.Original_Price = Number(devicePriceCatalog[value]?.[nextBrand]?.[nextModel] || 0)
      }

      if (key === 'Brand') {
        const models = Object.keys(devicePriceCatalog[next.Device_Type]?.[value] || {})
        const nextModel = models[0] || ''
        next.Model = nextModel
        next.Original_Price = Number(devicePriceCatalog[next.Device_Type]?.[value]?.[nextModel] || 0)
      }

      if (key === 'Model') {
        next.Original_Price = Number(devicePriceCatalog[next.Device_Type]?.[next.Brand]?.[value] || 0)
      }

      if (key === 'Condition_Label') {
        const validScores = conditionScoreOptions[value] || conditionScoreOptions.Good
        if (!validScores.includes(Number(next.Condition_Score))) {
          next.Condition_Score = validScores[0]
        }
      }

      return next
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setPredictions([])
    setInputData(null)
    setBestModel('')

    const payload = {
      Device_Type: form.Device_Type,
      Brand: form.Brand,
      Model: form.Model,
      Age_Years: toNumber(form.Age_Years, 0),
      Condition_Label: form.Condition_Label,
      // UI score is 0-10; backend expects 0-100.
      Condition_Score: toNumber(form.Condition_Score, 0) * 10,
      Screen_Damage: form.Screen_Damage,
      Body_Damage: form.Body_Damage,
      Battery_Health: toNumber(form.Battery_Health, 0),
      Original_Price: toNumber(form.Original_Price, 0),
      // Removed from UI, derived from age.
      Depreciation_Rate: Math.min(0.95, Math.max(0.05, toNumber(form.Age_Years, 0) * 0.08)),
      // Removed from UI, derived from condition score.
      Demand_Score: Math.min(100, Math.max(0, toNumber(form.Condition_Score, 0) * 10)),
    }

    try {
      const response = await fetch(ML_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(formatApiError(data?.detail || data?.message, response.status))
      }
      setInputData(payload)
      setPredictions(data?.predictions || [])
      setBestModel(data?.best_model || '')
    } catch (submitError) {
      setError(submitError.message || 'Failed to fetch model predictions')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="model-comp-page">
      <div className="glass-panel saas-card">
        <h1 className="panel-title">Model Comparison</h1>
        <p className="panel-subtitle">Compare price predictions and charts for all ML models.</p>

        <form className="model-comp-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>Device Type</span>
            <select value={form.Device_Type} onChange={(e) => updateField('Device_Type', e.target.value)} required>
              {deviceTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Brand</span>
            <select value={form.Brand} onChange={(e) => updateField('Brand', e.target.value)} required>
              {availableBrands.map((brand) => (
                <option key={brand} value={brand}>
                  {brand}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Model</span>
            <select value={form.Model} onChange={(e) => updateField('Model', e.target.value)} required>
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Age Years</span>
            <select value={form.Age_Years} onChange={(e) => updateField('Age_Years', e.target.value)} required>
              {Array.from({ length: 16 }, (_, idx) => idx).map((age) => (
                <option key={age} value={age}>
                  {age}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Condition Label</span>
            <select value={form.Condition_Label} onChange={(e) => updateField('Condition_Label', e.target.value)} required>
              <option value="Good">Good</option>
              <option value="Average">Average</option>
              <option value="Poor">Poor</option>
            </select>
          </label>
          <label className="field">
            <span>Condition Score (1-10)</span>
            <select value={form.Condition_Score} onChange={(e) => updateField('Condition_Score', e.target.value)} required>
              {availableConditionScores.map((score) => (
                <option key={score} value={score}>
                  {score}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Screen Damage</span>
            <select value={form.Screen_Damage} onChange={(e) => updateField('Screen_Damage', e.target.value)} required>
              <option value="No">No</option>
              <option value="Yes">Yes</option>
            </select>
          </label>
          <label className="field">
            <span>Body Damage</span>
            <select value={form.Body_Damage} onChange={(e) => updateField('Body_Damage', e.target.value)} required>
              <option value="No">No</option>
              <option value="Yes">Yes</option>
            </select>
          </label>
          <label className="field">
            <span>Battery Health</span>
            <select value={form.Battery_Health} onChange={(e) => updateField('Battery_Health', e.target.value)} required>
              {Array.from({ length: 13 }, (_, idx) => 40 + idx * 5).map((health) => (
                <option key={health} value={health}>
                  {health}%
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Original Price</span>
            <input
              type="number"
              min="0"
              value={form.Original_Price}
              readOnly
              required
            />
          </label>

          <button type="submit" className="primary-button" disabled={loading}>
            {loading ? 'Predicting...' : 'Compare Models'}
          </button>
        </form>

        {error ? <div className="error-banner">{error}</div> : null}
      </div>

      {inputData && normalizedPredictions.length > 0 ? (
        <div className="model-comp-results">
          {normalizedPredictions.map((prediction) => {
            const chartData = [
              { name: 'Original Price', value: toNumber(inputData.Original_Price, 0) },
              { name: 'Predicted Price', value: toNumber(prediction.price, 0) },
            ]
            const isBest = prediction.model === bestModel
            return (
              <article key={prediction.model} className={`glass-panel saas-card model-comp-card${isBest ? ' best' : ''}`}>
                <h3 className="panel-title">{prediction.model}</h3>
                <p className="panel-subtitle">
                  Price: ₹{toNumber(prediction.price, 0).toLocaleString('en-IN')}
                  {isBest ? ' (Best)' : ''}
                </p>
                <p className="panel-subtitle">Accuracy: {Math.round(toNumber(prediction.accuracy, 0) * 100)}%</p>
                <div className="model-comp-chart-wrap">
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.25)" />
                      <XAxis dataKey="name" stroke="#cbd5e1" />
                      <YAxis stroke="#cbd5e1" />
                      <Tooltip
                        formatter={(value) => `₹${toNumber(value, 0).toLocaleString('en-IN')}`}
                        contentStyle={{ background: '#0f172a', border: '1px solid rgba(148,163,184,0.35)' }}
                      />
                      <Bar dataKey="value" fill={isBest ? '#22c55e' : '#6366f1'} radius={[8, 8, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </article>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

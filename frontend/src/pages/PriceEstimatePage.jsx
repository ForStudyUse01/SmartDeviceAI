import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ModelComparison } from '../components/ModelComparison'

const ML_BASE = import.meta.env.VITE_ML_PRICE_API || 'http://127.0.0.1:8765'

function formatInr(n) {
  if (n == null || n === '') return '—'
  const v = Number(n)
  if (Number.isNaN(v)) return '—'
  return `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

function formatR2(r2) {
  if (r2 == null || Number.isNaN(Number(r2))) return '—'
  return Number(r2).toFixed(4)
}

function rowPrice(row) {
  const p = row.price ?? row.predicted_price
  return p == null || Number.isNaN(Number(p)) ? null : Number(p)
}

function rowLabel(row) {
  return row.model ?? row.model_name ?? row.model_key ?? 'Model'
}

function normalizePredictionRows(data) {
  if (Array.isArray(data?.predictions)) return data.predictions
  if (Array.isArray(data?.model_comparison)) {
    return data.model_comparison.map((row) => ({
      model: row.model || row.model_name || row.model_key,
      model_key: row.model_key,
      price: row.price ?? row.predicted_price,
      predicted_price: row.predicted_price,
      accuracy: row.accuracy ?? row.r2,
      r2: row.r2,
      mae: row.mae,
      rmse: row.rmse,
      status: row.status,
      prediction_failed: row.prediction_failed,
      is_best: row.is_best,
    }))
  }
  return []
}

function normalizeToken(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

/** Lightweight SVG bar chart — no extra dependencies */
function PredictedPriceChart({ rows, bestModelKey }) {
  const series = (rows || [])
    .map((r) => ({
      key: r.model_key,
      label: rowLabel(r),
      price: rowPrice(r),
      isBest: r.model_key === bestModelKey,
    }))
    .filter((s) => s.price != null)
  if (series.length === 0) return null

  const max = Math.max(...series.map((s) => s.price), 1)
  const w = 420
  const h = 160
  const pad = 36
  const barW = (w - pad * 2) / series.length - 8

  return (
    <div className="ml-price-chart" aria-hidden="true">
      <p className="ml-price-chart-title">Predicted price by model</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="ml-price-chart-svg">
        {series.map((s, i) => {
          const x = pad + i * ((w - pad * 2) / series.length) + 4
          const bh = ((h - 50) * s.price) / max
          const y = h - 40 - bh
          const fill = s.isBest ? 'url(#barBest)' : 'url(#barOther)'
          return (
            <g key={s.key}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={Math.max(bh, 2)}
                rx={6}
                fill={fill}
                className={s.isBest ? 'ml-price-bar-best' : ''}
              />
              <text x={x + barW / 2} y={h - 12} textAnchor="middle" className="ml-price-chart-label">
                {s.key === 'linear_regression'
                  ? 'Linear'
                  : s.key === 'random_forest'
                    ? 'RF'
                    : 'K-Means'}
              </text>
            </g>
          )
        })}
        <defs>
          <linearGradient id="barBest" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(34, 197, 94, 0.95)" />
            <stop offset="100%" stopColor="rgba(124, 92, 255, 0.75)" />
          </linearGradient>
          <linearGradient id="barOther" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(148, 163, 184, 0.55)" />
            <stop offset="100%" stopColor="rgba(71, 85, 105, 0.45)" />
          </linearGradient>
        </defs>
      </svg>
      <p className="ml-price-chart-legend">Higher bar = higher predicted price</p>
    </div>
  )
}

function ConfidenceBadge({ level }) {
  if (!level) return null
  const cls =
    level === 'High'
      ? 'ml-price-confidence ml-price-confidence-high'
      : level === 'Medium'
        ? 'ml-price-confidence ml-price-confidence-medium'
        : 'ml-price-confidence ml-price-confidence-low'
  return (
    <span className={cls} title="Based on the selected best model’s test R²">
      Confidence: {level}
    </span>
  )
}

export function PriceEstimatePage() {
  const [options, setOptions] = useState({ brand: [], device_type: [], condition: [] })
  const [form, setForm] = useState({
    brand: 'Samsung',
    device_type: 'smartphone',
    age_years: 2,
    condition: 'good',
    original_price: 45000,
    usage_hours_per_day: 5,
  })
  const [result, setResult] = useState(null)
  const [predictions, setPredictions] = useState([])
  const [bestModel, setBestModel] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [optionsError, setOptionsError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function loadOpts() {
      try {
        const res = await fetch(`${ML_BASE}/options`)
        if (!res.ok) throw new Error(`Options failed (${res.status})`)
        const data = await res.json()
        if (!cancelled) {
          setOptions({
            brand: data.brand || [],
            device_type: data.device_type || [],
            condition: data.condition || [],
          })
        }
      } catch (e) {
        if (!cancelled) {
          setOptionsError(
            e.message || 'Could not load dropdowns. Start the ML server: uvicorn price_ml_server:app --port 8765'
          )
        }
      }
    }
    loadOpts()
    return () => {
      cancelled = true
    }
  }, [])

  async function onSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    setPredictions([])
    setBestModel('')
    try {
      const res = await fetch(`${ML_BASE}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          brand: form.brand,
          device_type: form.device_type,
          age_years: Number(form.age_years),
          condition: form.condition,
          original_price: Number(form.original_price),
          usage_hours_per_day: Number(form.usage_hours_per_day),
        }),
      })
      const data = await res.json().catch(() => ({}))
      console.log('API RESPONSE:', data)
      if (!res.ok) {
        throw new Error(data.detail || data.message || `Request failed (${res.status})`)
      }
      const rows = normalizePredictionRows(data)
      setPredictions(rows)
      setBestModel(data.best_model || data.best_model_name || '')
      setResult(data)
    } catch (err) {
      setError(err.message || 'Prediction failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ml-price-page">
      <div className="ml-price-inner glass-panel saas-card">
        <header className="ml-price-header">
          <span className="eyebrow eyebrow-indigo">Local ML</span>
          <h1 className="ml-price-title">Resale price comparison</h1>
          <p className="ml-price-lead">
            Linear regression, random forest, and K-means cluster pricing — trained offline on{' '}
            <code className="ml-price-code">backend/data/electronics_prices.csv</code>. Run{' '}
            <code className="ml-price-code">python train_models.py</code> then{' '}
            <code className="ml-price-code">uvicorn price_ml_server:app --port 8765</code> from{' '}
            <code className="ml-price-code">backend</code>.
          </p>
          <Link to="/dashboard" className="secondary-button ml-price-back">
            ← Back to dashboard
          </Link>
        </header>

        {optionsError ? <p className="ml-price-banner error">{optionsError}</p> : null}

        <form className="ml-price-form" onSubmit={onSubmit}>
          <div className="ml-price-grid">
            <label className="ml-price-field">
              Brand
              <select
                value={form.brand}
                onChange={(ev) => setForm((f) => ({ ...f, brand: ev.target.value }))}
                required
              >
                {(options.brand.length ? options.brand : [form.brand]).map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
            <label className="ml-price-field">
              Device type
              <select
                value={form.device_type}
                onChange={(ev) => setForm((f) => ({ ...f, device_type: ev.target.value }))}
                required
              >
                {(options.device_type.length ? options.device_type : [form.device_type]).map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
            <label className="ml-price-field">
              Age (years)
              <input
                type="number"
                min={0}
                max={50}
                step={0.5}
                value={form.age_years}
                onChange={(ev) => setForm((f) => ({ ...f, age_years: ev.target.value }))}
                required
              />
            </label>
            <label className="ml-price-field">
              Condition
              <select
                value={form.condition}
                onChange={(ev) => setForm((f) => ({ ...f, condition: ev.target.value }))}
                required
              >
                {(options.condition.length ? options.condition : [form.condition]).map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
            <label className="ml-price-field">
              Original price (₹)
              <input
                type="number"
                min={0}
                step={100}
                value={form.original_price}
                onChange={(ev) => setForm((f) => ({ ...f, original_price: ev.target.value }))}
                required
              />
            </label>
            <label className="ml-price-field">
              Usage (hrs / day)
              <input
                type="number"
                min={0}
                max={24}
                step={0.5}
                value={form.usage_hours_per_day}
                onChange={(ev) => setForm((f) => ({ ...f, usage_hours_per_day: ev.target.value }))}
                required
              />
            </label>
          </div>
          <button type="submit" className="primary-button ml-price-submit" disabled={loading}>
            {loading ? 'Estimating…' : 'Compare models'}
          </button>
        </form>

        {error ? <p className="ml-price-banner error">{error}</p> : null}

        {result ? (
          <div className="ml-price-results">
            <div className="ml-price-best-estimate-card">
              <p className="ml-price-best-estimate-label">Estimated resale value</p>
              <p className="ml-price-best-estimate-value">{formatInr(result.best_price)}</p>
            </div>
            <div className="ml-price-results-heading">
              <h2 className="ml-price-results-title">Model comparison (hold-out test metrics)</h2>
              <div className="ml-price-results-meta">
                <ConfidenceBadge level={result.confidence} />
                {result.best_score != null ? (
                  <span className="ml-price-best-score" title="Weighted composite score on test metrics">
                    Score: {Number(result.best_score).toFixed(4)}
                  </span>
                ) : null}
              </div>
            </div>
            {result.reason ? <p className="ml-price-reason">{result.reason}</p> : null}
            {result.kmeans_note ? <p className="ml-price-kmeans-note">{result.kmeans_note}</p> : null}
            <p className="ml-price-results-note">
              <strong>{result.best_model_name || result.best_model}</strong>
              {result.cluster_id != null ? (
                <>
                  {' '}
                  · K-means cluster id: <strong>{result.cluster_id}</strong>
                </>
              ) : null}
            </p>

            <PredictedPriceChart rows={predictions} bestModelKey={bestModel || result.best_model_key} />

            {predictions.length > 0 ? (
              <ModelComparison predictions={predictions} bestModel={bestModel} />
            ) : (
              <p className="ml-model-comparison-empty">No model results available</p>
            )}

            <div className="ml-price-table-wrap">
              <table className="ml-price-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Price</th>
                    <th>R²</th>
                    <th>MAE</th>
                    <th>RMSE</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((row, idx) => {
                    const isBest =
                      row.is_best || normalizeToken(rowLabel(row)) === normalizeToken(bestModel || result.best_model)
                    return (
                    <tr
                      key={row.model_key || row.model || idx}
                      className={isBest ? 'ml-price-row-best ml-price-row-animate' : ''}
                    >
                      <td>
                        <span className="ml-price-model-cell">
                          {rowLabel(row)}
                          {row.prediction_failed || row.status === 'Error' ? (
                            <span
                              className="ml-price-warn-tip"
                              title="Prediction failed for this model"
                              aria-label="Prediction failed"
                            >
                              ⚠️
                            </span>
                          ) : null}
                          {row.model_key === 'kmeans' ? (
                            <span
                              className="ml-price-info-tip"
                              title={
                                result.kmeans_note ||
                                'K-Means assigns devices to feature-space clusters; price is the centroid (mean training resale) for that cluster.'
                              }
                              aria-label="K-Means explanation"
                            >
                              ⓘ
                            </span>
                          ) : null}
                        </span>
                      </td>
                      <td>{formatInr(rowPrice(row) ?? row.price ?? row.predicted_price)}</td>
                      <td>{formatR2(row.r2)}</td>
                      <td>{formatInr(row.mae)}</td>
                      <td>{formatInr(row.rmse)}</td>
                      <td>
                        {row.status ? (
                          <span className={isBest ? 'ml-price-status-best' : 'ml-price-status'}>
                            {row.status}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <p className="ml-price-table-note">R² indicates how well each model fits the held-out test data.</p>
            <p className="ml-price-footnote">
              R², MAE, and RMSE are computed on the test split for each model separately. They do not change per
              prediction; only the predicted price column is specific to this device. Best model uses weighted score{' '}
              <code className="ml-price-code">0.6·R² − 0.2·norm(RMSE) − 0.2·norm(MAE)</code> across models.
              {result.score_breakdown ? (
                <>
                  {' '}
                  See API field <code className="ml-price-code">score_breakdown</code> for per-model contribution
                  (r2_weight, rmse_penalty, mae_penalty).
                </>
              ) : null}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

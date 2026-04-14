function formatInr(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `₹${num.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
}

function formatAccuracy(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  const percent = num <= 1 ? num * 100 : num
  return `${Math.round(percent)}%`
}

function normalize(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

export function ModelComparison({ predictions, bestModel }) {
  if (!Array.isArray(predictions) || predictions.length === 0) {
    return <p className="ml-model-comparison-empty">No model results available</p>
  }

  const bestNorm = normalize(bestModel)

  return (
    <section className="ml-model-comparison">
      <div className="ml-model-comparison-heading">
        <h3>Model comparison</h3>
        <p>Best model selected based on highest accuracy</p>
      </div>
      <div className="ml-model-comparison-grid">
        {predictions.map((item) => {
          const modelName = item.model || item.model_name || item.model_key || 'Model'
          const isBest = normalize(modelName) === bestNorm
          const price = item.price ?? item.predicted_price
          const accuracy = item.accuracy ?? item.r2
          return (
            <article
              key={`${modelName}-${item.price}-${item.accuracy}`}
              className={`ml-model-card${isBest ? ' is-best' : ''}`}
            >
              <header className="ml-model-card-header">
                <h4>{modelName}</h4>
                {isBest ? <span className="ml-model-badge">Recommended</span> : null}
              </header>
              <p className="ml-model-metric">
                <span>Price</span>
                <strong>{formatInr(price)}</strong>
              </p>
              <p className="ml-model-metric">
                <span>Accuracy</span>
                <strong>{formatAccuracy(accuracy)}</strong>
              </p>
            </article>
          )
        })}
      </div>
    </section>
  )
}

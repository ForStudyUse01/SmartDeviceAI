import { enrichScan } from '../lib/valuation'
import { getFormattedMetalRows } from '../lib/liveMetalPrices'

export function ScanResultCard({ scan, liveMetalPrices }) {
  if (!scan) {
    return (
      <div className="empty-state">
        Select a device and run calculation to see value, metal recovery, and recommended action.
      </div>
    )
  }

  if (scan.validation && scan.validation.status !== 'approved') {
    const validation = scan.validation
    const di = scan.deviceInfo

    return (
      <div className="scan-result-sections">
        <div className="scan-section">
          <h3 className="scan-section-title">Verification required</h3>
          <div className="scan-section-body">
            <div className="error-banner" style={{ marginBottom: 12 }}>
              {validation.message}
            </div>
            <ul className="device-info-list">
              <li>
                <span className="result-key">Manual type</span> {di?.deviceType || '-'}
              </li>
              <li>
                <span className="result-key">Manual condition</span> {di?.conditionLabel || '-'}
              </li>
              <li>
                <span className="result-key">AI detected device</span> {validation.aiDetectedDevice}
              </li>
              <li>
                <span className="result-key">AI condition</span> {validation.aiCondition}
              </li>
              <li>
                <span className="result-key">Match score</span> {validation.matchScore}%
              </li>
              <li>
                <span className="result-key">AI confidence</span> {validation.aiConfidence}%
              </li>
              <li>
                <span className="result-key">Damage confidence</span> {validation.aiDamageConfidence ?? 0}%
              </li>
            </ul>
            <p className="metric-hint" style={{ marginTop: 12 }}>
              {validation.aiSuggestion ||
                'Attach a clearer image that properly shows the device so the AI can justify the final estimate.'}
            </p>
          </div>
        </div>
      </div>
    )
  }

  const s = enrichScan(scan)
  const validation = s.validation

  const showProfit = (s.profit ?? 0) > 0
  const showLoss = (s.loss ?? 0) > 0
  const di = s.deviceInfo
  const metalRows = getFormattedMetalRows(liveMetalPrices?.prices)

  return (
    <div className="scan-result-sections">
      <div className="scan-section">
        <h3 className="scan-section-title">Device info</h3>
        <div className="scan-section-body">
          {di ? (
            <ul className="device-info-list">
              <li>
                <span className="result-key">Type</span> {di.deviceType}
              </li>
              <li>
                <span className="result-key">Brand</span> {di.brand}
              </li>
              <li>
                <span className="result-key">Model</span> {di.model}
              </li>
              <li>
                <span className="result-key">Age</span> {di.ageYears} yr
              </li>
              <li>
                <span className="result-key">Condition</span> {di.conditionLabel}
              </li>
              <li>
                <span className="result-key">Screen damage</span> {di.screenDamage}
              </li>
              <li>
                <span className="result-key">Body damage</span> {di.bodyDamage}
              </li>
              <li>
                <span className="result-key">Water damage</span> {di.waterDamage ?? '—'}
              </li>
            </ul>
          ) : (
            <div>
              <strong>{s.component || '—'}</strong>
            </div>
          )}
        </div>
      </div>

      {validation ? (
        <div className="scan-section">
          <h3 className="scan-section-title">AI verification</h3>
          <div className="scan-section-body">
            <ul className="device-info-list">
              <li>
                <span className="result-key">Status</span> {validation.message}
              </li>
              <li>
                <span className="result-key">Match score</span> {validation.matchScore}%
              </li>
              <li>
                <span className="result-key">AI detected device</span> {validation.aiDetectedDevice}
              </li>
              <li>
                <span className="result-key">AI condition</span> {validation.aiCondition}
              </li>
              <li>
                <span className="result-key">AI confidence</span> {validation.aiConfidence}%
              </li>
              <li>
                <span className="result-key">Damage confidence</span> {validation.aiDamageConfidence ?? 0}%
              </li>
            </ul>
            {validation.aiSuggestion ? (
              <p className="metric-hint" style={{ marginTop: 12 }}>
                AI condition analysis: {validation.aiSuggestion}
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="scan-section">
        <h3 className="scan-section-title">Estimated value</h3>
        <div className="scan-section-body">
          <span className="result-key">Resale (after factors)</span>
          <div className="result-value" style={{ marginTop: 6 }}>
            ₹{s.resaleValue?.toLocaleString?.('en-IN') ?? s.resaleValue}
          </div>
          {s.mlPrediction && Number.isFinite(Number(s.mlPrediction.best_price)) ? (
            <div className="scan-ml-estimate">
              <div className="scan-ml-divider" aria-hidden="true" />
              <div className="scan-ml-head">🤖 AI Predicted Price</div>
              <div className="scan-ml-price-row">
                <span className="scan-ml-price">
                  ₹{Number(s.mlPrediction.best_price).toLocaleString('en-IN')}
                </span>
                {(() => {
                  const ml = Number(s.mlPrediction.best_price)
                  const resale = Number(s.resaleValue) || 0
                  if (!(resale > 0) || !Number.isFinite(ml)) return null
                  if (Math.abs(ml - resale) < 1) return null
                  const up = ml > resale
                  return (
                    <span
                      className={up ? 'scan-ml-trend scan-ml-trend-up' : 'scan-ml-trend scan-ml-trend-down'}
                      title={up ? 'ML estimate above resale (after factors)' : 'ML estimate below resale (after factors)'}
                    >
                      {up ? '↑' : '↓'}
                    </span>
                  )
                })()}
              </div>
              <div className="scan-ml-meta">
                <span>
                  Best Model: <strong>{s.mlPrediction.best_model_name || '—'}</strong>
                </span>
                <span>
                  Confidence: <strong>{s.mlPrediction.confidence || '—'}</strong>
                </span>
              </div>
            </div>
          ) : null}
          <p className="metric-hint" style={{ marginTop: 8 }}>
            Repair allowance: 10–25% of list price by condition · profit = resale − repair.
          </p>
        </div>
      </div>

      <div className="scan-section">
        <h3 className="scan-section-title">Metal composition (value)</h3>
        <div className="scan-section-body">
          <div className="live-metal-header">
            {liveMetalPrices?.prices && !liveMetalPrices?.error ? (
              <span className="live-metal-status">
                <span className="live-dot" aria-hidden="true" />
                Live
              </span>
            ) : (
              <span className="live-metal-status muted">Market data</span>
            )}
            {liveMetalPrices?.loading ? (
              <span className="live-metal-meta">Fetching live market data...</span>
            ) : liveMetalPrices?.error ? (
              <span className="live-metal-meta live-metal-error">{liveMetalPrices.error}</span>
            ) : liveMetalPrices?.prices?.updatedAt ? (
              <span className="live-metal-meta">
                Updated {new Date(liveMetalPrices.prices.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            ) : null}
          </div>
          {metalRows.length > 0 ? (
            <div className="live-metal-grid">
              {metalRows.map((metal) => (
                <div key={metal.key} className="live-metal-item">
                  <span className="result-key">{metal.label}</span>
                  <span className="live-metal-value">{metal.value}</span>
                </div>
              ))}
            </div>
          ) : null}
          <div className="result-value" style={{ fontSize: '1.25rem' }}>
            ₹{(s.metalRecoveryValue ?? s.value ?? 0).toLocaleString('en-IN')}
          </div>
          <p className="metric-hint" style={{ marginTop: 8 }}>
            {s.metalCompositionNote}
          </p>
        </div>
      </div>

      <div className="scan-section">
        <h3 className="scan-section-title">Profit / loss</h3>
        <div className="profit-loss-row">
          <div className={`profit-loss-item ${showProfit ? 'profit' : ''}`}>
            <div className="label">Profit</div>
            <div className="amount">₹{showProfit ? (s.profit ?? 0).toLocaleString('en-IN') : '0'}</div>
          </div>
          <div className={`profit-loss-item ${showLoss ? 'loss' : ''}`}>
            <div className="label">Loss</div>
            <div className="amount">₹{showLoss ? (s.loss ?? 0).toLocaleString('en-IN') : '0'}</div>
          </div>
        </div>
        <div className="metric-hint" style={{ marginTop: 10 }}>
          Repair estimate: ₹{(s.repairCost ?? 0).toLocaleString('en-IN')} · Net: ₹
          {(s.netMargin ?? 0).toLocaleString('en-IN')}
        </div>
      </div>

      <div className="recommended-action recommended-action-indigo">
        <h3 className="scan-section-title" style={{ color: 'var(--text)' }}>
          Recommended action
        </h3>
        <ul>
          <li>
            <span className="check" aria-hidden="true">
              ✔
            </span>
            <span>
              Best option: <strong>{s.bestOptionLabel || s.decision}</strong>
            </span>
          </li>
          <li>
            <span className="check" aria-hidden="true">
              ✔
            </span>
            <span>
              Estimated profit: <strong>₹{(s.profit ?? 0).toLocaleString('en-IN')}</strong>
              {s.netMargin < 0 ? <span className="muted-text"> (net loss after repair)</span> : null}
            </span>
          </li>
          <li>
            <span className="check" aria-hidden="true">
              ✔
            </span>
            <span>
              Risk: <strong>{s.risk}</strong>
              {s.decision ? (
                <span className="muted-text">
                  {' '}
                  · Decision: {s.decision}
                </span>
              ) : null}
            </span>
          </li>
        </ul>
      </div>
    </div>
  )
}

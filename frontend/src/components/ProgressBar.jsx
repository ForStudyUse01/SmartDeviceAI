export function ProgressBar({ label, value }) {
  return (
    <div className="progress-card">
      <div className="progress-header">
        <span className="progress-label">{label}</span>
        <strong className="progress-value">{value}%</strong>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

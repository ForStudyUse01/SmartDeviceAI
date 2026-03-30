export function StatusChip({ label, value, tone }) {
  return (
    <div className="status-chip">
      <span className={`status-dot ${tone}`}></span>
      <span className="status-label">{label}</span>
      <strong className="status-value">{value}</strong>
    </div>
  )
}

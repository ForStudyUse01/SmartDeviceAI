export function ScanHistoryList({ scans }) {
  if (!scans.length) {
    return <div className="empty-state">No scans yet. Your analysis history will appear here.</div>
  }

  return (
    <div className="history-list">
      {scans.map((scan) => (
        <div className="history-item" key={scan.id}>
          <div>
            <strong>{scan.component}</strong>
            <div className="history-meta">
              {scan.risk} risk · INR {scan.value} · Health {scan.deviceHealth}%
            </div>
          </div>
          <div className="history-meta">{new Date(scan.createdAt).toLocaleString()}</div>
        </div>
      ))}
    </div>
  )
}

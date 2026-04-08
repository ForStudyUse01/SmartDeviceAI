import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ScanResultCard } from '../components/ScanResultCard'
import { getDeviceById, getDeviceHistory } from '../lib/deviceHistory'
import { generatePlatformLinks } from '../lib/resalePlatforms'

const SORT_OPTIONS = [
  { value: 'highest', label: 'Highest Price 💰' },
  { value: 'lowest', label: 'Lowest Price 📉' },
  { value: 'best', label: 'Best Platform ⭐' },
  { value: 'fastest', label: 'Fastest Sale ⚡' },
]

function buildDeviceDescription(item) {
  const condition = item.snapshot?.condition || item.snapshot?.deviceInfo?.conditionLabel || 'Good'
  if (condition === 'Poor') return 'Device powers on but shows visible wear and may need repair or part replacement.'
  if (condition === 'Average') return 'Fully functional device with visible signs of use and moderate cosmetic wear.'
  return 'Fully functional device with minor wear and clean overall condition.'
}

function buildClipboardText(item, platform) {
  const condition = item.snapshot?.condition || item.snapshot?.deviceInfo?.conditionLabel || 'Good'
  const expectedPrice = Number(platform?.price ?? item.value ?? 0).toLocaleString('en-IN')
  const description = buildDeviceDescription(item)
  return [
    `Device: ${item.deviceName}`,
    `Condition: ${condition}`,
    `Expected Price: ₹${expectedPrice}`,
    `Description: ${description}`,
  ].join('\n')
}

export function DevicesPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [, bump] = useState(0)
  const [sortBy, setSortBy] = useState('highest')
  const [toast, setToast] = useState('')

  const items = getDeviceHistory()
  const detail = id ? getDeviceById(id) : null

  const deviceCards = useMemo(
    () =>
      items.map((item) => {
        const deviceName = item.brand ? `${item.brand} ${item.model}` : item.deviceName
        const platforms = generatePlatformLinks(deviceName, item.value || 0)
        const bestDealPrice = Math.max(...platforms.map((platform) => platform.price))
        const bestDealPlatform = platforms.find((platform) => platform.price === bestDealPrice) || platforms[0]
        const cashifyPlatform = platforms.find((platform) => platform.name === 'Cashify') || platforms[0]
        const topRatedPlatform =
          [...platforms].sort((left, right) => right.rating - left.rating || right.price - left.price)[0] || platforms[0]

        return {
          ...item,
          deviceName,
          platforms,
          bestDealPlatform,
          bestDealPrice,
          cashifyPlatform,
          topRatedPlatform,
        }
      }),
    [items],
  )

  async function copyDeviceDetails(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return
    }

    const textArea = document.createElement('textarea')
    textArea.value = text
    textArea.setAttribute('readonly', '')
    textArea.style.position = 'fixed'
    textArea.style.opacity = '0'
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  }

  function showToast(message) {
    setToast(message)
    window.clearTimeout(showToast.timeoutId)
    showToast.timeoutId = window.setTimeout(() => setToast(''), 2400)
  }

  async function handlePlatformAction(item, platform) {
    try {
      await copyDeviceDetails(buildClipboardText(item, platform))
      showToast('Device details copied! Paste on the website.')
    } catch {
      showToast('Could not copy automatically. You can still open the platform.')
    } finally {
      window.open(platform.url, '_blank', 'noopener,noreferrer')
    }
  }

  async function handleCopyDetails(item) {
    try {
      await copyDeviceDetails(buildClipboardText(item, item.bestDealPlatform))
      showToast('Device details copied! Paste on the website.')
    } catch {
      showToast('Could not copy device details.')
    }
  }

  const sortedCards = useMemo(() => {
    const copy = [...deviceCards]
    copy.sort((left, right) => {
      if (sortBy === 'lowest') {
        return left.cashifyPlatform.price - right.cashifyPlatform.price
      }
      if (sortBy === 'best') {
        return (
          right.topRatedPlatform.rating - left.topRatedPlatform.rating ||
          right.topRatedPlatform.price - left.topRatedPlatform.price
        )
      }
      if (sortBy === 'fastest') {
        return right.cashifyPlatform.price - left.cashifyPlatform.price
      }
      return right.bestDealPrice - left.bestDealPrice
    })
    return copy
  }, [deviceCards, sortBy])

  if (id && detail) {
    return (
      <div className="dashboard-layout">
        <div className="page-hero-saas">
          <button
            type="button"
            className="secondary-button detail-back-button"
            onClick={() => navigate('/my-devices')}
          >
            ← Back to list
          </button>
          <h1 className="dashboard-title">Device detail</h1>
          <p className="dashboard-subtitle">Saved estimate from local history.</p>
        </div>
        <div className="glass-panel panel-hover saas-card premium-panel">
          <ScanResultCard scan={detail} />
        </div>
      </div>
    )
  }

  if (id && !detail) {
    return (
      <div className="dashboard-layout">
        <p className="muted-text">Record not found.</p>
        <Link to="/my-devices" className="primary-button">
          Back
        </Link>
      </div>
    )
  }

  return (
    <div className="dashboard-layout devices-page">
      {toast ? <div className="device-toast">{toast}</div> : null}
      <section className="page-hero-saas devices-hero">
        <h1 className="dashboard-title">My devices</h1>
        <p className="dashboard-subtitle">Estimates saved in this browser (localStorage). Click a card for details.</p>
        <div className="device-page-toolbar">
          <div className="field device-sort-field">
            <label htmlFor="device-sort">Sort devices</label>
            <select id="device-sort" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="secondary-button" onClick={() => bump((n) => n + 1)}>
            Refresh
          </button>
        </div>
      </section>

      <div className="device-card-grid">
        {items.length === 0 ? (
          <div className="empty-state saas-card">
            No saved devices yet. Run an estimate on <Link to="/scan">Scan Device</Link>.
          </div>
        ) : (
          sortedCards.map((item) => (
            <div key={item.id} className="device-history-card saas-card">
              <div className="device-history-card-header">
                <div className="device-history-card-copy">
                  <div className="device-history-card-title">{item.deviceName}</div>
                  <div className="device-history-card-meta">
                    <span className="device-history-value">₹{Number(item.value || 0).toLocaleString('en-IN')}</span>
                    <span className="device-history-decision">{item.decision}</span>
                  </div>
                </div>
                <span className="device-best-deal-badge">Best Deal 🟢 {item.bestDealPlatform.name}</span>
              </div>

              <div className="device-history-card-main">
                <div className="device-quick-stats">
                  <div className="device-stat-pill">
                    <span className="device-stat-label">Best offer</span>
                    <span className="device-stat-value">₹{item.bestDealPrice.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="device-stat-pill profit">
                    <span className="device-stat-label">Profit highlight</span>
                    <span className="device-stat-value">
                      +₹{Math.max(0, item.bestDealPrice - Number(item.value || 0)).toLocaleString('en-IN')}
                    </span>
                  </div>
                </div>

                <div className="device-history-card-footer">
                  <div className="device-history-card-date">{new Date(item.date).toLocaleString()}</div>
                  <div className="device-card-actions">
                    <button
                      type="button"
                      className="primary-button device-resell-link"
                      onClick={() => handlePlatformAction(item, item.bestDealPlatform)}
                    >
                      Resell
                    </button>
                    <button type="button" className="secondary-button device-copy-link" onClick={() => handleCopyDetails(item)}>
                      Copy Details
                    </button>
                    <Link to={`/my-devices/${item.id}`} className="secondary-button device-detail-link">
                      View details
                    </Link>
                  </div>
                </div>
              </div>

              <div className="device-platforms-section">
                <div className="device-platforms-title">Sell on Platforms</div>
                <div className="device-platforms-grid">
                  {item.platforms.slice(0, 3).map((platform) => (
                    <button
                      type="button"
                      key={`${item.id}-${platform.name}`}
                      className={`platform-link-card ${platform.accent}${platform.name === item.bestDealPlatform.name ? ' best-deal' : ''}`}
                      onClick={() => handlePlatformAction(item, platform)}
                    >
                      <span className="platform-link-top">
                        <span className="platform-link-name">{platform.name}</span>
                        <span className="platform-link-rating">{platform.rating.toFixed(1)} ★</span>
                      </span>
                      <span className="platform-link-price">
                        ₹{platform.price.toLocaleString('en-IN')}
                        {platform.name === 'Cashify' ? ' ⚡' : ''}
                      </span>
                      <span className="platform-link-badge">
                        {platform.name === item.bestDealPlatform.name ? 'Best Deal 🟢' : platform.badge}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

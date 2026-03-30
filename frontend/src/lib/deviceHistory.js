const KEY = 'smartdeviceai_devices_v1'

function safeParse(raw) {
  try {
    const data = JSON.parse(raw)
    return Array.isArray(data) ? data : []
  } catch {
    return []
  }
}

export function getDeviceHistory() {
  return safeParse(localStorage.getItem(KEY))
}

export function saveDeviceEntry(entry) {
  const list = getDeviceHistory()
  const item = {
    id: entry.id || `local-${Date.now()}`,
    deviceName: entry.deviceName || entry.deviceInfo?.deviceType || 'Device',
    brand: entry.brand,
    model: entry.model,
    value: entry.resaleValue ?? entry.value,
    decision: entry.decision,
    date: entry.createdAt || new Date().toISOString(),
    snapshot: entry,
  }
  const next = [item, ...list.filter((x) => x.id !== item.id)].slice(0, 50)
  localStorage.setItem(KEY, JSON.stringify(next))
  return item
}

export function getDeviceById(id) {
  return getDeviceHistory().find((x) => x.id === id)?.snapshot || null
}

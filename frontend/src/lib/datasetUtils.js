/**
 * Cascading dropdown helpers for devices.csv (Device_Type → Brand → Model).
 */

export function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean).map((v) => String(v).trim()))].sort((a, b) =>
    a.localeCompare(b),
  )
}

/** One row per (Device_Type, Brand, Model) — first occurrence wins for template fields. */
export function uniqueDeviceRows(rows) {
  const map = new Map()
  for (const r of rows) {
    const type = r.Device_Type?.trim()
    const brand = r.Brand?.trim()
    const model = r.Model?.trim()
    if (!type || !brand || !model) continue
    const key = `${type}|${brand}|${model}`
    if (!map.has(key)) map.set(key, r)
  }
  return Array.from(map.values())
}

export function deviceTypes(rows) {
  return uniqueSorted(uniqueDeviceRows(rows).map((r) => r.Device_Type))
}

export function brandsForType(rows, deviceType) {
  return uniqueSorted(
    uniqueDeviceRows(rows)
      .filter((r) => r.Device_Type === deviceType)
      .map((r) => r.Brand),
  )
}

export function modelsForBrand(rows, deviceType, brand) {
  return uniqueSorted(
    uniqueDeviceRows(rows)
      .filter((r) => r.Device_Type === deviceType && r.Brand === brand)
      .map((r) => r.Model),
  )
}

export function findDeviceRow(rows, deviceType, brand, model) {
  return uniqueDeviceRows(rows).find(
    (r) => r.Device_Type === deviceType && r.Brand === brand && r.Model === model,
  )
}

const NUMERIC_KEYS = new Set([
  'base_price_inr',
  'gold_mg',
  'copper_g',
  'silver_mg',
  'aluminum_g',
  'lithium_g',
  'cobalt_mg',
  'palladium_mg',
  'Age_Years',
  'Condition_Score',
  'Battery_Health',
  'Original_Price',
  'Depreciation_Rate',
  'Current_Market_Price',
  'Resale_Price',
  'Exchange_Price',
  'Repair_Cost',
  'Refurbished_Price',
  'Demand_Score',
  'Profit_if_Repaired',
  'OLX_Resale_Price',
  'Cashify_Exchange_Price',
  'Price_Variation_%',
])

export function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) return []
  const headers = lines[0].split(',').map((h) => h.trim())
  return lines.slice(1).map((line) => {
    const parts = line.split(',')
    const row = {}
    headers.forEach((h, i) => {
      const raw = parts[i]?.trim() ?? ''
      if (NUMERIC_KEYS.has(h)) {
        const n = Number.parseFloat(raw)
        row[h] = Number.isFinite(n) ? n : 0
      } else {
        row[h] = raw
      }
    })
    return row
  })
}

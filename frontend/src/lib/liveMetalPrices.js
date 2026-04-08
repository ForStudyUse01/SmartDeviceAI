const CACHE_KEY = 'smartdeviceai.live-metals.v1'
export const LIVE_METAL_REFRESH_MS = 60_000

const TROY_OUNCE_IN_GRAMS = 31.1034768
const POUNDS_PER_KILOGRAM = 2.2046226218
const FALLBACK_USD_TO_INR = 83

const METAL_API_BASE = 'https://api.gold-api.com/price'
const FOREX_API_URL = 'https://open.er-api.com/v6/latest/USD'
const METAL_SYMBOLS = {
  gold: 'XAU',
  silver: 'XAG',
  copper: 'HG',
  palladium: 'XPD',
}

export const METAL_DISPLAY_CONFIG = {
  gold: { label: 'Gold', unit: '/ 10g', decimals: 0 },
  silver: { label: 'Silver', unit: '/ g', decimals: 2 },
  copper: { label: 'Copper', unit: '/ kg', decimals: 2 },
  palladium: { label: 'Palladium', unit: '/ 10g', decimals: 0 },
}

function roundPrice(value, decimals = 0) {
  const factor = 10 ** decimals
  return Math.round((Number(value) || 0) * factor) / factor
}

function normalizeMetalsError(error) {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return 'Live prices unavailable'
}

async function fetchSymbolPrice(symbol) {
  const response = await fetch(`${METAL_API_BASE}/${symbol}`, {
    headers: {
      Accept: 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(`Live prices unavailable`)
  }

  const payload = await response.json()
  if (typeof payload?.price !== 'number' || !Number.isFinite(payload.price)) {
    throw new Error('Live prices unavailable')
  }

  return {
    symbol,
    price: payload.price,
    updatedAt: payload.updatedAt || null,
  }
}

async function getUsdToInrRate() {
  try {
    const response = await fetch(FOREX_API_URL)
    if (!response.ok) return FALLBACK_USD_TO_INR
    const payload = await response.json()
    const liveRate = payload?.rates?.INR
    return typeof liveRate === 'number' && Number.isFinite(liveRate) ? liveRate : FALLBACK_USD_TO_INR
  } catch {
    return FALLBACK_USD_TO_INR
  }
}

function buildSnapshot(metalPayloads, usdToInr) {
  const goldPer10g = roundPrice((metalPayloads.gold.price * usdToInr * 10) / TROY_OUNCE_IN_GRAMS, 0)
  const silverPerGram = roundPrice((metalPayloads.silver.price * usdToInr) / TROY_OUNCE_IN_GRAMS, 2)
  const copperPerKg = roundPrice(metalPayloads.copper.price * usdToInr * POUNDS_PER_KILOGRAM, 2)
  const palladiumPer10g = metalPayloads.palladium
    ? roundPrice((metalPayloads.palladium.price * usdToInr * 10) / TROY_OUNCE_IN_GRAMS, 0)
    : null

  return {
    gold: goldPer10g,
    silver: silverPerGram,
    copper: copperPerKg,
    palladium: palladiumPer10g,
    currency: 'INR',
    source: 'Gold-API + USD/INR FX',
    updatedAt: new Date().toISOString(),
    usdToInr,
  }
}

export function getCachedLiveMetalPrices() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed?.updatedAt) return null
    return parsed
  } catch {
    return null
  }
}

function writeCachedLiveMetalPrices(snapshot) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(CACHE_KEY, JSON.stringify(snapshot))
  } catch {
    // ignore cache write failures
  }
}

function isFresh(snapshot) {
  if (!snapshot?.updatedAt) return false
  return Date.now() - new Date(snapshot.updatedAt).getTime() < LIVE_METAL_REFRESH_MS
}

export async function getLiveMetalPrices({ force = false } = {}) {
  const cached = getCachedLiveMetalPrices()
  if (!force && cached && isFresh(cached)) {
    return cached
  }

  try {
    const [usdToInr, gold, silver, copper, palladiumResult] = await Promise.all([
      getUsdToInrRate(),
      fetchSymbolPrice(METAL_SYMBOLS.gold),
      fetchSymbolPrice(METAL_SYMBOLS.silver),
      fetchSymbolPrice(METAL_SYMBOLS.copper),
      fetchSymbolPrice(METAL_SYMBOLS.palladium).catch(() => null),
    ])

    const snapshot = buildSnapshot(
      {
        gold,
        silver,
        copper,
        palladium: palladiumResult,
      },
      usdToInr,
    )
    writeCachedLiveMetalPrices(snapshot)
    return snapshot
  } catch (error) {
    throw new Error(normalizeMetalsError(error))
  }
}

export const fetchLiveMetalPrices = getLiveMetalPrices

export function formatMetalPrice(value, metalKey) {
  const config = METAL_DISPLAY_CONFIG[metalKey]
  const decimals = config?.decimals ?? 0
  return `₹${Number(value ?? 0).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })} ${config?.unit || ''}`.trim()
}

export function getFormattedMetalRows(snapshot) {
  if (!snapshot) return []
  return Object.entries(METAL_DISPLAY_CONFIG)
    .filter(([key]) => typeof snapshot[key] === 'number' && Number.isFinite(snapshot[key]))
    .map(([key, config]) => ({
      key,
      label: config.label,
      value: formatMetalPrice(snapshot[key], key),
    }))
}

export function buildMetalCompositionNote(snapshot) {
  if (!snapshot) {
    return 'Live prices unavailable. Metal recovery estimate will refresh automatically when market data becomes available.'
  }

  const parts = [
    `gold ${formatMetalPrice(snapshot.gold, 'gold')}`,
    `silver ${formatMetalPrice(snapshot.silver, 'silver')}`,
    `copper ${formatMetalPrice(snapshot.copper, 'copper')}`,
  ]
  if (typeof snapshot.palladium === 'number' && Number.isFinite(snapshot.palladium)) {
    parts.push(`palladium ${formatMetalPrice(snapshot.palladium, 'palladium')}`)
  }

  return `Live spot reference: ${parts.join(', ')} — weighted by device category.`
}


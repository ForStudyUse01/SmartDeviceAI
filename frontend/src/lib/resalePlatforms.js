const PLATFORM_CONFIG = [
  {
    name: 'Cashify',
    rating: 4.5,
    badge: 'Fast payout',
    accent: 'speed',
    priceFactor: 0.9,
    buildUrl: () => 'https://www.cashify.in/sell-old-mobile-phone',
  },
  {
    name: 'OLX',
    rating: 4.2,
    badge: 'Best Deal',
    accent: 'deal',
    priceFactor: 1.05,
    buildUrl: (deviceName) => `https://www.olx.in/items/q-${encodeURIComponent(deviceName)}`,
  },
  {
    name: 'Quikr',
    rating: 3.8,
    badge: 'Popular',
    accent: 'neutral',
    priceFactor: 1.03,
    buildUrl: (deviceName) => `https://www.quikr.com/search?q=${encodeURIComponent(deviceName)}`,
  },
  {
    name: 'Amazon',
    rating: 4.3,
    badge: 'Exchange Info',
    accent: 'info',
    priceFactor: 0.95,
    buildUrl: (deviceName) => `https://www.amazon.in/s?k=${encodeURIComponent(deviceName)}`,
  },
  {
    name: 'Flipkart',
    rating: 4.2,
    badge: 'Exchange Info',
    accent: 'info',
    priceFactor: 0.95,
    buildUrl: (deviceName) => `https://www.flipkart.com/search?q=${encodeURIComponent(deviceName)}`,
  },
]

function roundPlatformPrice(baseValue, factor) {
  const numericBase = Math.max(0, Number(baseValue) || 0)
  return Math.round(numericBase * factor)
}

export function generatePlatformLinks(deviceName, baseValue) {
  const safeName = String(deviceName || 'device').trim() || 'device'

  return PLATFORM_CONFIG.map((platform) => ({
    name: platform.name,
    rating: platform.rating,
    badge: platform.badge,
    accent: platform.accent,
    price: roundPlatformPrice(baseValue, platform.priceFactor),
    url: platform.buildUrl(safeName),
  }))
}


import { useCallback, useEffect, useState } from 'react'
import {
  getLiveMetalPrices,
  getCachedLiveMetalPrices,
  LIVE_METAL_REFRESH_MS,
} from '../lib/liveMetalPrices'

export function useLiveMetalPrices() {
  const [prices, setPrices] = useState(() => getCachedLiveMetalPrices())
  const [loading, setLoading] = useState(() => !getCachedLiveMetalPrices())
  const [error, setError] = useState('')

  const refreshPrices = useCallback(async ({ force = false } = {}) => {
    setLoading(true)
    try {
      const snapshot = await getLiveMetalPrices({ force })
      setPrices(snapshot)
      setError('')
      return snapshot
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : 'Live prices unavailable'
      setError(message)
      throw loadError
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true

    refreshPrices().catch(() => {
      if (!active) return
    })

    const intervalId = window.setInterval(() => {
      refreshPrices({ force: true }).catch(() => {
        if (!active) return
      })
    }, LIVE_METAL_REFRESH_MS)

    return () => {
      active = false
      window.clearInterval(intervalId)
    }
  }, [refreshPrices])

  return {
    prices,
    loading,
    error,
    refreshPrices,
  }
}


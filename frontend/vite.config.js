import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const dashboardApiTarget = env.VITE_API_URL || 'http://127.0.0.1:8000'
  const aiApiTarget = env.VITE_AI_ANALYZE_URL || 'http://127.0.0.1:5000'
  const mlPriceTarget = env.VITE_ML_PRICE_URL || 'http://127.0.0.1:8765'

  /** Optional same-origin paths; primary client uses `VITE_API_URL` → absolute :8000. */
  const devProxy = {
    '/ai-device-scan': {
      target: dashboardApiTarget,
      changeOrigin: true,
    },
    '/api': {
      target: dashboardApiTarget,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
    '/ai': {
      target: aiApiTarget,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/ai/, ''),
    },
    '/ml-price': {
      target: mlPriceTarget,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/ml-price/, ''),
    },
  }

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: devProxy,
    },
    preview: {
      proxy: devProxy,
    },
  }
})

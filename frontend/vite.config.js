import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const dashboardApiTarget = env.VITE_API_URL || 'http://127.0.0.1:8000'
  const aiApiTarget = env.VITE_AI_ANALYZE_URL || 'http://127.0.0.1:5000'

  return {
    plugins: [react()],
    server: {
      proxy: {
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
      },
    },
  }
})

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.API_TARGET || 'http://127.0.0.1:8000'
  const proxy = {
    '/api': { target, changeOrigin: false, rewrite: (path: string) => path.replace(/^\/api/, '') },
    '/auth': { target, changeOrigin: false },
  }
  return {
    plugins: [react(), tailwindcss()],
    server: { proxy, host: '127.0.0.1', port: 3000, strictPort: true, allowedHosts: env.FRONTEND_HOST ? [env.FRONTEND_HOST] : [] },
    preview: { proxy, host: '127.0.0.1', port: 3000, strictPort: true },
    test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], include: ['src/**/*.test.{ts,tsx}'] },
  }
})

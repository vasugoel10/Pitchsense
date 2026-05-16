import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: '/static/',
  build: {
    outDir: 'build',
    assetsDir: '',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // HTTP API calls → Django on :8000
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/mgmt-console-7x9k': { target: 'http://localhost:8000', changeOrigin: true },
      // WebSocket connections → Django Channels on :8000
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
    }
  }
})

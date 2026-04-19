import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: '/static/', // Django static URL routing
  build: {
    outDir: 'build',
    assetsDir: '', // This outputs directly into build/ so Django doesn't double prefix
    emptyOutDir: true,
  }
})

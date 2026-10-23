/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies /api to the backend (make api, port 8000), so the browser stays on one origin,
// as it does behind nginx in docker compose.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.API_URL ?? 'http://localhost:8000', changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    coverage: { // npm run coverage: lines and branches of our code (shadcn's generated components are left out)
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/components/ui/**', 'src/api/schema.d.ts', 'src/test/**', 'src/**/*.test.{ts,tsx}', 'src/main.tsx'],
      reporter: ['text-summary', 'text'],
    },
  },
})

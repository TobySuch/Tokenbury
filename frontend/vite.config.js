import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const stripHugoTemplates = {
  name: 'strip-hugo-templates',
  enforce: 'pre',
  transformIndexHtml: {
    order: 'pre',
    handler: (html) => html.replace(/\{\{[\s\S]*?\}\}/g, ''),
  },
}

export default defineConfig({
  plugins: [react(), tailwindcss(), stripHugoTemplates],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.js'],
  },
})

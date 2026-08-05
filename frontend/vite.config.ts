import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // No rewrite: backend routes now live at /api/* directly (see main.py's
      // APIRouter prefix), matching the production build where FastAPI serves
      // both the API and the static frontend from one origin.
      '/api': 'http://127.0.0.1:8000',
    },
  },
})

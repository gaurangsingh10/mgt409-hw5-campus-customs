import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// `npm run dev` serves the desk on http://localhost:5173 and opens it in the browser.
// The page talks to the FastAPI backend at VITE_API_BASE (frontend/.env, default http://localhost:8000).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, open: true },
})

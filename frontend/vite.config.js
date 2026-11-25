import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Development only (npm run dev on :5173). In normal use the master serves the
// built UI itself on :8000 (npm run build, then python -m dap.master).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // reachable from other PCs, not only from localhost
    proxy: { '/api': 'http://localhost:8000' }, // the master on this PC
  },
})

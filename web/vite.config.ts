import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // shared/ lives one level up, next to extension/.
  server: { fs: { allow: ['..'] } },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 3010,
    // Tailscale Serve (tailnet only) proxies this hostname to 127.0.0.1:3010.
    allowedHosts: ['vrs-global.tailb38520.ts.net'],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
})

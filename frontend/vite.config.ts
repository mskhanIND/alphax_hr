import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'))

// Production build is served by Frappe from /assets/alphax_hr/frontend/.
// Files are content-hashed; alphax_hr/www/alphax.py reads .vite/manifest.json
// to find the entry. (A query-string version on the entry would make lazy chunks
// import a second copy of React.)
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_FRAPPE_URL || 'http://localhost:8000'
  return {
    plugins: [react(), tailwindcss()],
    define: { __APP_VERSION__: JSON.stringify(pkg.version) },
    base: mode === 'production' ? '/assets/alphax_hr/frontend/' : '/',
    build: {
      outDir: '../alphax_hr/public/frontend',
      emptyOutDir: true,
      manifest: true,
    },
    server: {
      port: 5173,
      proxy: { '/api': { target, changeOrigin: true }, '/assets': { target, changeOrigin: true }, '/files': { target, changeOrigin: true } },
    },
    test: { environment: 'node' },
  }
})

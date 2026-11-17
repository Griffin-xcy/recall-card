import path from 'path'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { inspectAttr } from 'kimi-plugin-inspect-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.PORT || '8000'
  return {
    base: './',
    plugins: [inspectAttr(), react()],
    server: {
      host: '0.0.0.0',
      port: 7100,
      proxy: {
        '/api': `http://127.0.0.1:${backendPort}`,
      },
    },
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
  }
})

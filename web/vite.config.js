// Vite 配置:开发代理到后端;构建产物由 FastAPI 静态托管(docs/v1.0/tech.md §7)
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/rss.xml': 'http://127.0.0.1:8000',
    },
  },
})

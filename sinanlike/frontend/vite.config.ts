import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  base: './',  // Electron file:// 协议需要相对路径
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18000',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        timeout: 180000,  // 3 分钟 — 匹配后端长时间请求（生成材料 ~90s）
        proxyTimeout: 180000,
      },
    },
  },
})

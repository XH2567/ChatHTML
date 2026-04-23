import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      // 代理论文资源请求到后端
      '/api/jobs': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 代理 AI 聊天请求到后端
      '/api/chat': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 代理静态资源请求（CSS、图片等）
      '/artifacts': {
        target: 'http://127.0.0.1:8000/api/jobs',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/artifacts\/([^/]+)/, '/$1/artifacts'),
      },
    },
  },
})

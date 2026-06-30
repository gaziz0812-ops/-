import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  // [VITE] plugins подключает обработку .vue-файлов.
  plugins: [vue()],

  // [VITE] server настраивает dev-server, который запускается через npm run dev.
  server: {
    // [VITE] allowedHosts разрешает открывать dev-server через ngrok-домены.
    allowedHosts: [
      '.ngrok-free.app',
      '.ngrok-free.dev',
    ],

    // [VITE] proxy перенаправляет запросы frontend-а /api/... в локальный Django.
    proxy: {
      '/api': {
        // [OUR] Локальный Django backend, куда Vite будет проксировать API-запросы.
        target: 'http://127.0.0.1:8000',
        // [VITE] changeOrigin подменяет Host-заголовок на target, чтобы backend видел локальный origin.
        changeOrigin: true,
      },

      '/media': {
        // [OUR] Загруженные фото товара тоже проксируем в Django через frontend/ngrok.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

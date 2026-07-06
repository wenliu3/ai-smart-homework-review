import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router']
    }),
    Components({
      resolvers: [ElementPlusResolver()]
    })
  ],
  resolve: {
    // 配置别名
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  build: {
    // 构建优化配置
    rollupOptions: {
      output: {
        // 手动配置代码分割
        manualChunks: {
          // 将Vue相关库打包到一个chunk
          'vue-vendor': ['vue', 'vue-router'],
          // 将Element Plus相关库打包到一个chunk
          'element-vendor': ['element-plus', '@element-plus/icons-vue'],
          // 将其他第三方库打包到一个chunk
          'vendor': ['axios', 'nprogress']
        }
      }
    },
    // 设置chunk大小警告阈值
    chunkSizeWarningLimit: 1000
  },
  server: {
    host: '0.0.0.0', // 监听所有网络接口，支持本地IP访问
    port: 8080,
    open: true, // 自动打开浏览器
    cors: true, // 启用CORS
    proxy: {
      '/api': {
        target: 'http://localhost:83',// 本地后端 (或使用原测试后端: http://124.222.166.174:83)
        changeOrigin: true,
        secure: false, // 如果后端使用HTTPS，设置为true
        // 可选：添加请求头以便后端正确识别代理
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            // 添加X-Forwarded-For头，帮助后端获取真实IP
            const clientIp = req.socket.remoteAddress || req.connection.remoteAddress;
            if (clientIp) {
              proxyReq.setHeader('X-Forwarded-For', clientIp);
              proxyReq.setHeader('X-Real-IP', clientIp);
            }
          });
        }
      },
      '/uploads': {
        target: 'http://localhost:83',
        changeOrigin: true,
      }
    }
  }
}) 
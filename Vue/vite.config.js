import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 项目根目录（Vue 的上一级）：前端与后端共用同一份 .env，避免两处配置漂移
const projectRoot = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig(({ mode }) => {
  // 不会被注入浏览器包（Vite 仅暴露 VITE_ 前缀给 import.meta.env）。
  const env = loadEnv(mode, projectRoot, '')

  return {
    envDir: projectRoot,
    plugins: [
      vue(),
      // （SPA 导航后地址栏不更新，曾导致"登录成功却停在登录页"），故移除。
      Components({
        resolvers: [ElementPlusResolver({ importStyle: false })],
        dts: false,
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    // echarts / element-plus / swiper 等体积大或藏在懒加载页里的依赖，若运行期才被
    // 发现会触发 re-optimize + 整页 reload（表现为白屏刷新/长时间白屏），必须全部
    optimizeDeps: {
      include: [
        'echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers',
        'element-plus/es', 'element-plus/es/components/message-box/style/index',
        '@vueuse/core',
        'axios', 'qrcode', 'qrcode.vue', 'element-china-area-data',
        'swiper/vue', 'swiper/modules'
      ]
    },
    server: {
      proxy: {
        '/api': { target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5000', changeOrigin: true },
        '/goods-images': { target: env.VITE_MINIO_PROXY_TARGET || 'http://127.0.0.1:9000', changeOrigin: true }
      }
    },
  }
})

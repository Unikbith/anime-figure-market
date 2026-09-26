import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// 项目根目录（Vue 的上一级）：前端与后端共用同一份 .env，避免两处配置漂移
const projectRoot = fileURLToPath(new URL('..', import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 第三个参数 '' 表示同时读取非 VITE_ 前缀变量；这些值只在本 Node 配置文件内使用，
  // 不会被注入浏览器包（Vite 仅暴露 VITE_ 前缀给 import.meta.env）。
  const env = loadEnv(mode, projectRoot, '')

  return {
    // 指定 env 目录为项目根目录，使 import.meta.env.VITE_* 能读到根目录 .env
    envDir: projectRoot,
    plugins: [
      vue(),
      // 注：vite-plugin-vue-devtools 的 overlay 会干扰 vue-router 的 history 状态
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
    // 显式预打包。清单与 src 里的第三方 import 保持同步。
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

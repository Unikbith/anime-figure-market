import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import 'element-plus/dist/index.css'
// 全局共享样式与品牌令牌（设计系统单一真源，见 src/styles/common.css）
import './styles/common.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.mount('#app')

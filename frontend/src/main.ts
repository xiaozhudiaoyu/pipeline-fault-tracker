// 应用入口：创建 Vue 实例，注册全局插件，挂载到 index.html 的 #app。
//
// 插件注册顺序约定「先 UI 组件库、再路由、再数据层」，便于阅读：
//   · ElementPlus —— 全局注册 el-* 组件。本项目采用【全量引入】（最省心）；
//     按需自动引入需额外安装 unplugin-vue-components / unplugin-auto-import，
//     超出用户预授权依赖清单，故不采用（规则 2.6 / 3.1）。
//   · router —— 注册 RouterLink / RouterView 全局组件并接管 URL。
//   · VueQueryPlugin —— 启用 TanStack Query（t5 起用 useQuery/useMutation 管理服务端状态）。
//
// CSS 引入顺序：先 element-plus 基础样式，后本项目 main.css，确保 main.css 可覆盖默认样式。
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)

app.use(ElementPlus)
app.use(router)
app.use(VueQueryPlugin)

app.mount('#app')

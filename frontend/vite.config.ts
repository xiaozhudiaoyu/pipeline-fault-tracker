// Vite 构建/开发服务器配置。
//
// 为什么保持极简（不加 node 内置模块、不加路径别名）？
//   · 遵循最小改动（规则 3.1）：只用 vue 插件，vite.config.ts 不 import node:url / node:path，
//     因而不需要额外安装 @types/node（不在用户预授权的依赖清单内，规则 2.6）；
//   · 源码内部一律用相对路径 import（本项目 src 层级浅，../xxx 足够清晰）。
//
// 前后端联调约定（与 backend/app/config.py 对齐）：
//   · 后端跑在 http://127.0.0.1:8000，接口路径自带 /api 前缀；
//   · 前端 dev server 跑在 5173 端口，后端 CORS 已放行 http://localhost:5173 与 http://127.0.0.1:5173；
//   · 不走 vite proxy，前端直接用 VITE_API_BASE_URL 访问后端源（见 frontend/.env.example）。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 仅绑定回环地址，不暴露到局域网；端口与后端 CORS 白名单一致。
    host: '127.0.0.1',
    port: 5173,
  },
})

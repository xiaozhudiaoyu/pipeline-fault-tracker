// 路由表：骨架阶段仅一条占位首页。
//
// 约定与要点（业务接入时沿用）：
//   · history 模式（createWebHistory）——URL 无 # 更干净；dev 由 Vite 处理 SPA 回退，
//     生产部署时需服务器把未知路径回退到 index.html（README 会注明）；
//   · 全部路由懒加载（() => import(...)）——按页分包，首屏只加载当前页；
//   · 【顺序关键】静态路径（如 /books/new）必须排在动态路径（如 /books/:id）之前，
//     否则 "new" 会被当成 :id 参数匹配；
//   · props: true——把路径参数 :id 作为 prop 注入组件（组件内 defineProps<{ id: string }>）。
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },
  ],
})

export default router

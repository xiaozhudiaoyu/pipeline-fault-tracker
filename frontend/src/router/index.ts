// 路由表：三个页面（列表 / 登记 / 详情）。
//
// 约定与要点：
//   · history 模式（createWebHistory）——URL 无 # 更干净；dev 由 Vite 处理 SPA 回退，
//     生产部署时需服务器把未知路径回退到 index.html（README 会注明）；
//   · 全部路由懒加载（() => import(...)）——按页分包，首屏只加载列表页；
//   · 【顺序关键】/faults/new 必须排在 /faults/:id 之前，否则 "new" 会被当成 :id 参数匹配；
//   · 详情页 props: true——把路径参数 :id 作为 prop 注入组件（组件内 defineProps<{ id: string }>）。
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'fault-list',
      component: () => import('../views/FaultListView.vue'),
    },
    {
      path: '/faults/new',
      name: 'fault-create',
      component: () => import('../views/FaultCreateView.vue'),
    },
    {
      path: '/faults/:id',
      name: 'fault-detail',
      component: () => import('../views/FaultDetailView.vue'),
      props: true,
    },
  ],
})

export default router

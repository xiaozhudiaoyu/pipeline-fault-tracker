// 路由表：三个页面（列表 / 表单 / 详情），表单页同时承载「新建」与「编辑」。
//
// 约定与要点：
//   · history 模式（createWebHistory）——URL 无 # 更干净；dev 由 Vite 处理 SPA 回退，
//     生产部署时需服务器把未知路径回退到 index.html（README 会注明）；
//   · 全部路由懒加载（() => import(...)）——按页分包，首屏只加载列表页；
//   · 【顺序关键】/items/new 必须排在 /items/:id 之前，否则 "new" 会被当成 :id 参数匹配；
//   · props: true——把路径参数 :id 作为 prop 注入组件（组件内 defineProps<{ id: string }>）。
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'item-list',
      component: () => import('../views/ItemListView.vue'),
    },
    {
      path: '/items/new',
      name: 'item-create',
      component: () => import('../views/ItemFormView.vue'),
    },
    {
      path: '/items/:id',
      name: 'item-detail',
      component: () => import('../views/ItemDetailView.vue'),
      props: true,
    },
    {
      path: '/items/:id/edit',
      name: 'item-edit',
      component: () => import('../views/ItemFormView.vue'),
      props: true,
    },
  ],
})

export default router

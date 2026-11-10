// 路由表：登录页 + 三个业务页（列表 / 新建 / 详情）+ 用户管理页（管理员）。
//
// 约定与要点：
//   · history 模式（createWebHistory）——URL 无 # 更干净；dev 由 Vite 处理 SPA 回退，
//     生产部署时需服务器把未知路径回退到 index.html（README 会注明）；
//   · 全部路由懒加载（() => import(...)）——按页分包，首屏只加载列表页；
//   · 【顺序关键】/faults/new 必须排在 /faults/:id 之前，否则 "new" 会被当成 :id 参数匹配；
//   · 详情页 props: true——把路径参数 :id 作为 prop 注入组件（组件内 defineProps<{ id: string }>）；
//   · 第三阶段 meta 权限标记：requiresAuth（默认 true，仅 /login 显式 false）、
//     requiresAdmin（用户管理页）——前端守卫只做体验层拦截，安全边界在后端（M4/M5 已全面鉴权）。
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { bindRouter, bootstrap, isAdmin, isAuthenticated } from '../composables/useAuth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
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
  {
    path: '/users',
    name: 'user-manage',
    component: () => import('../views/UserManageView.vue'),
    meta: { requiresAdmin: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局前置守卫（第三阶段登录门禁）：
//   ① 首次导航先 bootstrap()——带 token 时调 /me 恢复登录态（刷新页面不掉登录）；
//   ② 未登录访问业务页 → 跳 /login（useAuth 的 redirect query 已在 goLogin 处理，
//      这里直达登录页不带 redirect：手动输错 URL 的场景回列表页即可）；
//   ③ 已登录再访问 /login → 回列表页；
//   ④ 非管理员访问 /users → 回列表页（后端会 403，这里只是不进空页面）。
router.beforeEach(async (to) => {
  await bootstrap()

  if (to.meta.requiresAuth === false) {
    return isAuthenticated.value ? { name: 'fault-list' } : true
  }
  if (!isAuthenticated.value) {
    return { name: 'login' }
  }
  if (to.meta.requiresAdmin) {
    if (!isAdmin.value) return { name: 'fault-list' }
  }
  return true
})

// 把实例注入 useAuth（401 跳登录、登出跳登录都用它的 goLogin）
bindRouter(router)

export default router

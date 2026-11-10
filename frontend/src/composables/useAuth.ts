// 登录态组合式（第三阶段 M6）：模块级单例，全应用共享同一份 token/用户状态。
//
// 为什么不用 pinia：预授权依赖清单无新库（规则 2.5/3.1），本项目仅一处全局状态，
//   模块作用域的 ref + 导出函数即是标准 Vue 组合式单例写法。
//
// 状态机：
//   unknown（初始）→ bootstrap() 持 token 调 /me → authenticated / anonymous
//   login() 成功后调 /me 置 authenticated（登录响应只有 JWT）
//   logout() / 401 回调 → 清 token + user → anonymous
//
// 即时失效（D3）：管理员停用/重置密码/对方登出 → 该用户下一次请求 401 →
//   client.ts 触发 notifyUnauthorized → 本模块注册的回调清态并跳登录页。
//
// 注意：router 实例不能在本模块顶层 import 使用（守卫与 router/index 互相引用会成环），
//   改由 router/index.ts 创建实例后调用 bindRouter() 注入，跳转统一走 goLogin()。
import { computed, ref } from 'vue'
import type { Router } from 'vue-router'
import type { QueryClient } from '@tanstack/vue-query'

import { fetchMe, login as apiLogin, logout as apiLogout } from '../api/auth'
import { ApiError } from '../api/client'
import { clearToken, getToken, registerUnauthorizedHandler, setToken } from '../utils/token'
import type { User } from '../types/user'

// ---- 模块级单例状态（import 即存在，全应用共享）----
const user = ref<User | null>(null)
const bootstrapped = ref(false) // 是否已完成首次 /me 恢复（路由守卫等它）

let routerRef: Router | null = null
let queryClientRef: QueryClient | null = null

export const isAuthenticated = computed(() => user.value !== null)
export const isAdmin = computed(() => user.value?.role === 'admin')
export const currentUser = computed(() => user.value)

// router/index.ts 在 createRouter 后调用一次。
export function bindRouter(r: Router): void {
  routerRef = r
}

// main.ts 在创建 QueryClient 后调用一次：登录/登出/401 时清空查询缓存，
// 防止上一账号的列表/用户表等数据残留在内存里被新身份读到（同 bindRouter 解循环依赖的思路）。
export function bindQueryClient(qc: QueryClient): void {
  queryClientRef = qc
}

function resetQueryCache(): void {
  queryClientRef?.clear()
}

// 跳登录页：携带 redirect（非根路径时），登录成功后回原页。
// 已在登录页则不重复推——登录接口自身 401（密码错误）不会带 token 触发回调，此处再兜一层。
function goLogin(): void {
  if (!routerRef || routerRef.currentRoute.value.path === '/login') return
  const redirect = routerRef.currentRoute.value.fullPath
  void routerRef.push({ path: '/login', query: redirect && redirect !== '/' ? { redirect } : {} })
}

// 恢复登录态：有 token 才请求 /me；失败（过期/停用/无效）一律静默清 token 视为未登录。
// 幂等：bootstrapped 后直接返回，路由守卫每次导航调用无额外请求。
export async function bootstrap(): Promise<void> {
  if (bootstrapped.value) return
  if (getToken()) {
    try {
      user.value = await fetchMe()
    } catch {
      clearToken()
      user.value = null
    }
  }
  bootstrapped.value = true
}

// 登录成功 = 存 token + 拉当前用户；失败原样抛错，由登录页展示 message。
// 换账号登录先清缓存：上一会话（如 token 过期前浏览过的列表）可能残留他人可见数据。
export async function login(username: string, password: string): Promise<void> {
  const resp = await apiLogin(username, password)
  resetQueryCache()
  setToken(resp.access_token)
  user.value = await fetchMe()
  bootstrapped.value = true
}

// 登出：通知后端作废 token（失败不阻塞），本地无论如何都清并回登录页。
export async function logout(): Promise<void> {
  try {
    await apiLogout()
  } catch {
    // token 已失效或网络异常：跳过远端，本地照常退出
  } finally {
    clearToken()
    user.value = null
    resetQueryCache()
    goLogin()
  }
}

// 401 统一善后（client.ts 回调）：任何携带 token 的请求收到 401 即登录态失效。
registerUnauthorizedHandler(() => {
  clearToken()
  user.value = null
  resetQueryCache()
  goLogin()
})

// 把登录/请求错误翻译成展示文案（登录页与 useAuth 消费者共用）。
export function authErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message
  if (err instanceof TypeError) return '无法连接后端服务，请确认服务已启动'
  return '操作失败，请稍后重试'
}

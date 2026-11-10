// 认证接口封装：对应后端 routers/auth.py 的三个端点（第三阶段 M3/M6）。
import { request } from './client'
import type { TokenResponse, User } from '../types/user'

// POST /api/auth/login —— 用户名密码换 JWT（公开接口；失败 401，话术统一防枚举）。
export function login(username: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('/api/auth/login', { method: 'POST', body: { username, password } })
}

// POST /api/auth/logout —— 登出：后端 bump token_version 使旧 token 即时失效（204 无内容）。
// 本地清 token 由调用方（useAuth.logout）负责——网络失败时本地也要能退出。
export function logout(): Promise<void> {
  return request<void>('/api/auth/logout', { method: 'POST' })
}

// GET /api/auth/me —— 当前登录用户；路由守卫刷新页面时用它恢复登录态（401 = token 已失效）。
export function fetchMe(signal?: AbortSignal): Promise<User> {
  return request<User>('/api/auth/me', { signal })
}

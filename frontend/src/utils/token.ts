// token 存取（第三阶段 M6）：独立小模块，避免 api/client ←→ composables/useAuth 循环依赖。
//
// 职责：JWT 的 localStorage 持久化（刷新页面不丢登录态）+ 401 时的「登出回调」注册点。
// 为什么存 localStorage 而不是仅内存：需求验收含「刷新页面后仍保持登录」；
// 本项目为内网小系统，不引入 httpOnly Cookie 方案（后端是无状态 JWT，D3 决策）。
// 安全约定：token 只在 client.ts 拼 Authorization 头时使用，日志与报错文案不带 token。

const STORAGE_KEY = 'pft_token'

// 401 统一处理回调：由 useAuth 在创建时注册（清用户态 + 跳登录页）。
// 用回调注册而非直接 import router：本模块活在 api 依赖底层，引 router 会成环。
let onUnauthorized: (() => void) | null = null

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function registerUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler
}

// client.ts 在收到 401 时调用：本地已存有 token 才触发登出跳转
//（登录接口本身返回 401「用户名或密码错误」不应把用户弹出登录页）。
export function notifyUnauthorized(): void {
  onUnauthorized?.()
}

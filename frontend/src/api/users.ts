// 用户管理接口封装：对应后端 routers/users.py（第三阶段 M6，全部仅管理员）。
import { request } from './client'
import type { User, UserCreatePayload } from '../types/user'

// GET /api/users —— 全部用户（含停用，username 升序）：管理页表格 + 指派/改派下拉共用，
// 处理人员候选由调用方按 role === 'handler' && is_active 过滤（后端无候选专用端点，见 routers/users.py 头注）。
export function fetchUsers(signal?: AbortSignal): Promise<User[]> {
  return request<User[]>('/api/users', { signal })
}

// POST /api/users —— 创建账号（201；重名 409；校验失败 422）。
export function createUser(payload: UserCreatePayload): Promise<User> {
  return request<User>('/api/users', { method: 'POST', body: payload })
}

// PATCH /api/users/{id}/active —— 启用/停用（停用即时失效其全部 token；停用自己 403）。
export function setUserActive(id: number, isActive: boolean): Promise<User> {
  return request<User>(`/api/users/${id}/active`, { method: 'PATCH', body: { is_active: isActive } })
}

// POST /api/users/{id}/reset-password —— 管理员重置密码（被重置者旧 token 立即失效）。
export function resetUserPassword(id: number, password: string): Promise<User> {
  return request<User>(`/api/users/${id}/reset-password`, { method: 'POST', body: { password } })
}

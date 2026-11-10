// 用户与角色类型：与后端 backend/app/schemas.py 的 UserOut / UserBrief / UserCreate 一一对应。
// 说明（规则 3.4）：字段名/取值均已对照后端源码核实（models.FaultRole：user/handler/admin）。

// 用户角色枚举（后端 models.FaultRole）
export type FaultRole = 'user' | 'handler' | 'admin'

// 完整用户（后端 UserOut：管理员用户管理页使用，不含 password_hash/token_version）
export interface User {
  id: number
  username: string
  display_name: string
  role: FaultRole
  is_active: boolean
  created_at: string // ISO 8601
}

// 故障上嵌套的用户卡（后端 UserBrief；旧数据 created_by/assignee 为 null → 显示"历史数据"）
export type UserBrief = Pick<User, 'id' | 'username' | 'display_name' | 'role'>

// POST /api/users 请求体（后端 UserCreate：username 3~50 唯一，密码 ≥6）
export interface UserCreatePayload {
  username: string
  password: string
  display_name: string
  role: FaultRole
}

// POST /api/auth/login 响应（后端 TokenResponse）
export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number // 秒
}

// 角色展示元数据（同 FAULT_STATUS_META 手法）：标签色沿用 Element Plus 语义色
export const FAULT_ROLE_META: Record<FaultRole, { label: string; tag: 'info' | 'warning' | 'danger' }> = {
  user: { label: '普通用户', tag: 'info' },
  handler: { label: '处理人员', tag: 'warning' },
  admin: { label: '管理员', tag: 'danger' },
}

// 角色下拉选项（用户管理页新建账号用；顺序固定：普通 → 处理 → 管理员）
export const FAULT_ROLE_OPTIONS: { value: FaultRole; label: string }[] = [
  { value: 'user', label: FAULT_ROLE_META.user.label },
  { value: 'handler', label: FAULT_ROLE_META.handler.label },
  { value: 'admin', label: FAULT_ROLE_META.admin.label },
]

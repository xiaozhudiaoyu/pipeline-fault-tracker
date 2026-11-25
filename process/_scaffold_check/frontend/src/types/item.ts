// 领域类型与常量：与后端 backend/app/schemas.py 的响应契约一一对应。
// 说明：后端 datetime 字段经 JSON 序列化为 ISO 8601 字符串，故前端一律用 string 承接。

// 状态枚举（后端 models.ItemStatus 的值：active / archived）
export type ItemStatus = 'active' | 'archived'

// 记录（后端 ItemOut，列表与详情共用）
export interface Item {
  id: number
  name: string
  description: string | null
  status: ItemStatus
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
}

// 分页列表（后端 ItemListOut）
export interface ItemList {
  items: Item[]
  total: number
  page: number
  size: number
}

// GET /api/items 查询参数（全部可选；不传=不筛选/用后端默认 page=1 size=20）
export interface ItemListParams {
  status?: ItemStatus
  page?: number
  size?: number
}

// POST /api/items 请求体（后端 ItemCreate）
export interface ItemCreatePayload {
  name: string
  description?: string | null
}

// PATCH /api/items/{id} 请求体（后端 ItemUpdate）——部分更新。
// 字段全部可选：后端用 exclude_unset 只应用「传了的」字段，故前端只发有改动的键。
export interface ItemUpdatePayload {
  name?: string
  description?: string
  status?: ItemStatus
}

// 统一错误结构（后端 ErrorOut / FieldErrorOut）
export interface FieldError {
  field: string // 如 body.name / query.page / path.item_id
  type: string // 如 missing / string_too_short / not_found / duplicate
  message: string
}
export interface ApiErrorBody {
  code: string
  message: string
  details: FieldError[]
}

// 状态展示元数据：中文标签 + el-tag 颜色类型（供列表状态列 / 筛选下拉复用，避免各处重复）
export const ITEM_STATUS_META: Record<ItemStatus, { label: string; tag: 'success' | 'info' }> = {
  active: { label: '启用中', tag: 'success' },
  archived: { label: '已归档', tag: 'info' },
}

// 状态下拉选项（顺序固定）
export const ITEM_STATUS_OPTIONS: { value: ItemStatus; label: string }[] = [
  { value: 'active', label: ITEM_STATUS_META.active.label },
  { value: 'archived', label: ITEM_STATUS_META.archived.label },
]

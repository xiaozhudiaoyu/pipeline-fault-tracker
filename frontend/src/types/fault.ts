// 领域类型与常量：与后端 backend/app/schemas.py 的响应契约一一对应（规则 3.4：字段名/类型核对出处）。
// 说明：后端 datetime 字段经 JSON 序列化为 ISO 8601 字符串，故前端一律用 string 承接。

// 故障状态枚举（后端 models.FaultStatus 的值：pending / processing / done）
export type FaultStatus = 'pending' | 'processing' | 'done'

// 流水线（后端 PipelineOut）
export interface Pipeline {
  id: number
  code: string
  name: string
  description: string | null
}

// 故障记录（后端 FaultOut，列表与详情共用；pipeline 为嵌套对象，免去二次请求）
export interface Fault {
  id: number
  pipeline_id: number
  pipeline: Pipeline
  location: string
  occurred_at: string // ISO 8601
  symptom: string
  status: FaultStatus
  handling_note: string | null
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
  closed_at: string | null // ISO 8601；未完成为 null
}

// 分页列表（后端 FaultListOut）
export interface FaultList {
  items: Fault[]
  total: number
  page: number
  size: number
}

// GET /api/faults 查询参数（全部可选；不传=不筛选/用后端默认 page=1 size=20）
export interface FaultListParams {
  pipeline_id?: number
  status?: FaultStatus
  page?: number
  size?: number
}

// POST /api/faults 请求体（后端 FaultCreate：不含 status/handling_note/closed_at，新故障由后端置 pending）
export interface FaultCreatePayload {
  pipeline_id: number
  location: string
  occurred_at: string // ISO 8601
  symptom: string
}

// PATCH /api/faults/{id}/transition 请求体（后端 FaultTransition）
export interface FaultTransitionPayload {
  target_status: FaultStatus
  handling_note?: string | null
}

// 统一错误结构（后端 ErrorOut / FieldErrorOut）
export interface FieldError {
  field: string // 如 body.symptom / query.page / path.fault_id / body.code
  type: string // 如 missing / string_too_short / not_found / duplicate / invalid_transition / required
  message: string
}
export interface ApiErrorBody {
  code: string
  message: string
  details: FieldError[]
}

// 状态展示元数据：中文标签 + el-tag 颜色类型（供 StatusTag / 筛选下拉 / 状态推进面板复用，避免各处重复）
export const FAULT_STATUS_META: Record<FaultStatus, { label: string; tag: 'info' | 'warning' | 'success' }> = {
  pending: { label: '待处理', tag: 'info' },
  processing: { label: '处理中', tag: 'warning' },
  done: { label: '已完成', tag: 'success' },
}

// 状态下拉选项（顺序固定：待处理 → 处理中 → 已完成）
export const FAULT_STATUS_OPTIONS: { value: FaultStatus; label: string }[] = [
  { value: 'pending', label: FAULT_STATUS_META.pending.label },
  { value: 'processing', label: FAULT_STATUS_META.processing.label },
  { value: 'done', label: FAULT_STATUS_META.done.label },
]

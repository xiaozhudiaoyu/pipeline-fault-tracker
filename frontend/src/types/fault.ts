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

// PATCH /api/faults/{id} 请求体（后端 FaultUpdate）——修改基础信息，不含状态流转。
// 三字段全部可选：后端用 exclude_unset 只应用「传了的」字段，故前端只发有改动的键。
// 注意：handling_note 不接受显式 null（后端 422），不改就不发这个键；done 后不可改（后端 409）。
export interface FaultUpdatePayload {
  location?: string
  symptom?: string
  handling_note?: string
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

// 状态机合法流转表：镜像后端 crud.transition_fault 的流转矩阵（后端是最终裁判，前端仅用于 UX——
// 只把「当前状态下允许的流转」渲染成按钮，避免用户点了才被 409 拒绝）。
//   pending    → processing（说明可选） / done（说明必填）
//   processing → pending（回退，说明可选） / done（说明必填）
//   done       → 终态不可逆（空数组，不渲染任何流转按钮）
export const ALLOWED_TRANSITIONS: Record<FaultStatus, FaultStatus[]> = {
  pending: ['processing', 'done'],
  processing: ['pending', 'done'],
  done: [],
}

// 目标状态是否需要必填处理说明（对应后端 HandlingNoteRequiredError：target=done 时 handling_note 必填）
export function isNoteRequired(target: FaultStatus): boolean {
  return target === 'done'
}

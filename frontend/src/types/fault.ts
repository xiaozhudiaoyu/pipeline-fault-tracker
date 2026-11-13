// 领域类型与常量：与后端 backend/app/schemas.py 的响应契约一一对应（规则 3.4：字段名/类型核对出处）。
// 说明：后端 datetime 字段经 JSON 序列化为 ISO 8601 字符串，故前端一律用 string 承接。
import type { UserBrief } from './user'

// 故障状态枚举（后端 models.FaultStatus；第三阶段 D2：既有三值不动，新增待确认）
export type FaultStatus = 'pending' | 'processing' | 'awaiting_confirmation' | 'done'

// 故障优先级枚举（第二阶段，后端 models.FaultPriority：normal / urgent）
export type FaultPriority = 'normal' | 'urgent'

// 流水线（后端 PipelineOut）
export interface Pipeline {
  id: number
  code: string
  name: string
  description: string | null
}

// 图片附件元数据（第四阶段，后端 schemas.AttachmentOut）。
// url 是回放端点相对路径（/api/attachments/{id}），但裸 <img src> 带不了 Authorization 头会 401，
// 展示须经 api/attachments.fetchAttachmentBlob 拉 blob 再 createObjectURL（见 FaultAttachmentGallery）。
export interface Attachment {
  id: number
  fault_id: number
  original_name: string
  content_type: string
  size_bytes: number
  uploader_id: number | null
  uploader_name: string | null
  created_at: string // ISO 8601
  url: string
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
  priority: FaultPriority
  handling_note: string | null
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
  closed_at: string | null // ISO 8601；未完成为 null
  // 第三阶段新增（后端 FaultOut.created_by/assignee：嵌套 UserBrief，旧数据为 null → 渲染“历史数据”）
  created_by: UserBrief | null
  assignee: UserBrief | null
  // 第四阶段新增（后端 FaultOut.attachments：图片附件元数据内嵌，空即无图）
  attachments: Attachment[]
}

// 追加进展 / 提交结果的响应体（后端 FaultActionResultOut）：FaultOut 全集 + 本次新建的时间线 id。
// 两步式附图：动作返回后前端拿 timeline_id 逐张上传随附图片（POST /api/timelines/{id}/attachments）。
export interface FaultActionResult extends Fault {
  timeline_id: number
}

// 分页列表（后端 FaultListOut）
export interface FaultList {
  items: Fault[]
  total: number
  page: number
  size: number
}

// GET /api/faults 查询参数（全部可选；不传=不筛选/用后端默认 page=1 size=20）。
// 第三阶段：角色默认视图由后端裁决（admin 全量/handler 本人相关/user 仅本人创建），
// 前端不传视图参数；assignee_id/unassigned 仅对 admin 有实际过滤意义（非 admin 与角色视图取交集）。
export interface FaultListParams {
  pipeline_id?: number
  status?: FaultStatus
  priority?: FaultPriority
  assignee_id?: number
  unassigned?: boolean
  page?: number
  size?: number
}

// POST /api/faults 请求体（后端 FaultCreate：不含 status/handling_note/closed_at，新故障由后端置 pending；
// priority 可选——不传即后端缺省 normal，需求二.1）
export interface FaultCreatePayload {
  pipeline_id: number
  location: string
  occurred_at: string // ISO 8601
  symptom: string
  priority?: FaultPriority
}

// PATCH /api/faults/{id} 请求体（后端 FaultUpdate）——第四阶段扩展为可改 location/symptom/occurred_at：
// 后端仅 pending 且创建人/admin 可改；priority 改走 POST /{id}/priority，
// handling_note 由「提交处理结果」动作写入（旧字段传了会被静默忽略）。
// remove_attachment_ids：现场图片改由本通道删除（仅本故障且非时间线附图的 id 会生效，其余忽略）；不传即不删。
export interface FaultUpdatePayload {
  location?: string
  symptom?: string
  occurred_at?: string
  remove_attachment_ids?: number[]
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

// 状态展示元数据：中文标签 + el-tag 颜色类型（供 StatusTag / 筛选下拉 / 时间线复用，避免各处重复）。
// 第三阶段四态：待确认（awaiting_confirmation）用 primary 区别于处理中的 warning 与已完成的 success。
export const FAULT_STATUS_META: Record<
  FaultStatus,
  { label: string; tag: 'primary' | 'info' | 'warning' | 'success' }
> = {
  pending: { label: '待处理', tag: 'info' },
  processing: { label: '处理中', tag: 'warning' },
  awaiting_confirmation: { label: '待确认', tag: 'primary' },
  done: { label: '已完成', tag: 'success' },
}

// 状态筛选选项（顺序固定：按处理进度推进方向 待处理 → 处理中 → 待确认 → 已完成）
export const FAULT_STATUS_OPTIONS: { value: FaultStatus; label: string }[] = [
  { value: 'pending', label: FAULT_STATUS_META.pending.label },
  { value: 'processing', label: FAULT_STATUS_META.processing.label },
  { value: 'awaiting_confirmation', label: FAULT_STATUS_META.awaiting_confirmation.label },
  { value: 'done', label: FAULT_STATUS_META.done.label },
]

// 优先级展示元数据（同 FAULT_STATUS_META 手法）：紧急用 danger 醒目，普通用 info 低调。
export const FAULT_PRIORITY_META: Record<FaultPriority, { label: string; tag: 'info' | 'danger' }> = {
  normal: { label: '普通', tag: 'info' },
  urgent: { label: '紧急', tag: 'danger' },
}

// 优先级下拉选项（顺序固定：普通 → 紧急，与默认值口径一致）
export const FAULT_PRIORITY_OPTIONS: { value: FaultPriority; label: string }[] = [
  { value: 'normal', label: FAULT_PRIORITY_META.normal.label },
  { value: 'urgent', label: FAULT_PRIORITY_META.urgent.label },
]

// （第三阶段 D5）旧 ALLOWED_TRANSITIONS / isNoteRequired 已随 /transition 端点一并废除：
// 可执行动作由后端基于「当前状态 × 角色 × 归属」判定，前端在 FaultActionPanel 内镜像同一矩阵渲染按钮。

// 未分派故障的筛选哨兵值：负责人下拉里「未分派」项的选项值（真实用户 id 从 1 起，-1 不冲突）。
// 列表页把它换算成 { unassigned: true } 查询参数，不直接发给后端。
export const UNASSIGNED_SENTINEL = -1

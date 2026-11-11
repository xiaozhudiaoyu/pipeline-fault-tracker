// 故障接口封装：对应后端 routers/faults.py（第三阶段 M5 契约）。
// 旧 transitionFault（PATCH /transition）已随后端 D5 决策移除，由 8 个语义化动作端点替代：
// 每个动作一个函数，请求体只承载必要参数；权限与状态机判定全在后端，前端照 403/409 提示即可。
import { request } from './client'
import { getToken } from '../utils/token'
import type {
  Fault,
  FaultCreatePayload,
  FaultList,
  FaultListParams,
  FaultPriority,
  FaultUpdatePayload,
} from '../types/fault'
import type { TimelineEntry } from '../types/timeline'

// GET /api/faults —— 分页查询（后端按角色过滤默认视图；筛选参数可选叠加）。
export function fetchFaults(params: FaultListParams = {}, signal?: AbortSignal): Promise<FaultList> {
  return request<FaultList>('/api/faults', { query: { ...params }, signal })
}

// GET /api/faults/{id} —— 单条详情（不存在或无权查看均 404）。
export function fetchFault(id: number, signal?: AbortSignal): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}`, { signal })
}

// POST /api/faults —— 新建故障（成功 201；pipeline_id 无效 404；校验失败 422）。
// created_by 由后端从当前登录用户取，请求体不含创建人字段（防伪造）。
export function createFault(payload: FaultCreatePayload): Promise<Fault> {
  return request<Fault>('/api/faults', { method: 'POST', body: payload })
}

// PATCH /api/faults/{id} —— 修改故障信息（仅 pending 且创建人/admin；其余 403/409/422 由后端裁决）。
export function updateFault(id: number, payload: FaultUpdatePayload): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}`, { method: 'PATCH', body: payload })
}

// ── 处理闭环动作端点（需求四）─────────────────────────────────────────
// 命名与后端 routers/faults.py 端点一一对应；全部 POST，成功返回最新 Fault（前端写回详情缓存）。

// GET /api/faults/{id}/timelines —— 时间线（按时间正序，含升级导入的 is_imported 记录）。
export function fetchTimelines(id: number, signal?: AbortSignal): Promise<TimelineEntry[]> {
  return request<TimelineEntry[]>(`/api/faults/${id}/timelines`, { signal })
}

// POST /{id}/assign —— 指派（admin）：pending 且无负责人 → 设定负责人，状态不变。
export function assignFault(id: number, assigneeId: number): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/assign`, { method: 'POST', body: { assignee_id: assigneeId } })
}

// POST /{id}/reassign —— 改派（admin）：pending/processing 换负责人，理由必填（≥2 字）。
export function reassignFault(id: number, assigneeId: number, reason: string): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/reassign`, {
    method: 'POST',
    body: { assignee_id: assigneeId, reason },
  })
}

// POST /{id}/start —— 开始处理（当前负责人）：pending → processing。
export function startFault(id: number): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/start`, { method: 'POST' })
}

// POST /{id}/progress —— 追加进展（当前负责人）：processing 内多次，状态不变，note 必填（≥2 字）。
export function addProgress(id: number, note: string): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/progress`, { method: 'POST', body: { note } })
}

// POST /{id}/submit —— 提交处理结果（当前负责人）：processing → awaiting_confirmation，
// result_note（≥5 字）同时落 handling_note。
export function submitFault(id: number, resultNote: string): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/submit`, { method: 'POST', body: { result_note: resultNote } })
}

// POST /{id}/confirm —— 确认完成（创建人；创建人不可用时 admin 代确认，代确认 reason 必填）：→ done。
export function confirmFault(id: number, reason?: string): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/confirm`, { method: 'POST', body: { reason: reason ?? null } })
}

// POST /{id}/return —— 退回处理（创建人）：awaiting_confirmation → processing，理由必填（≥2 字）。
export function returnFault(id: number, reason: string): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/return`, { method: 'POST', body: { reason } })
}

// POST /{id}/priority —— 优先级调整（admin 或创建人，done 之前）：不改状态，记入时间线。
export function changePriority(id: number, priority: FaultPriority): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/priority`, { method: 'POST', body: { priority } })
}

// ── 导出 CSV ──────────────────────────────────────────────────────────
// 导出请求携当前筛选（不含分页——导出语义是"筛选出的全部行"，需求文档 D2 口径）。
export type FaultExportParams = Pick<
  FaultListParams,
  'pipeline_id' | 'status' | 'priority' | 'assignee_id' | 'unassigned'
>

// 第三阶段改动：后端全部接口要求登录后才可访问，旧「隐藏 <a> 直链下载」不再可行
//（<a href> 不携带 Authorization 头）。改为 fetch blob + 临时 URL 触发下载，
// 文件名优先取后端 Content-Disposition，取不到时本地时间兜底。
export async function exportFaultsCsv(params: FaultExportParams = {}): Promise<void> {
  const base = import.meta.env.VITE_API_BASE_URL
  const sp = new URLSearchParams()
  // 跳过空值：列表页 params 已把 clearable 清空后的 '' 收敛成 undefined，这里只需判 undefined/null
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      sp.append(key, String(value))
    }
  }
  const qs = sp.toString()
  const url = `${base}/api/faults/export${qs ? `?${qs}` : ''}`

  const token = getToken()
  const resp = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!resp.ok) {
    // 与 client.request 不同：正常导出响应是文件流不是 JSON，非 2xx 时按状态码给简短话术即可
    throw new Error(resp.status === 401 ? '登录已失效，请重新登录后再导出' : `导出失败（${resp.status}）`)
  }

  // 文件名：后端 Content-Disposition 形如 attachment; filename=faults_20261109….csv
  const disposition = resp.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/.exec(disposition)
  const filename = match?.[1] ?? `faults_${new Date().toISOString().slice(0, 14).replace(/[:T-]/g, '')}.csv`

  const blob = await resp.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objectUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a) // 用完即移除，不在 DOM 留垃圾节点
  URL.revokeObjectURL(objectUrl) // 释放 blob 内存
}

// 故障接口封装：对应后端 routers/faults.py 的六个端点。
import { request } from './client'
import type {
  Fault,
  FaultCreatePayload,
  FaultList,
  FaultListParams,
  FaultTransitionPayload,
  FaultUpdatePayload,
} from '../types/fault'

// GET /api/faults —— 分页查询（按流水线/状态筛选，occurred_at 倒序）。
export function fetchFaults(params: FaultListParams = {}, signal?: AbortSignal): Promise<FaultList> {
  return request<FaultList>('/api/faults', { query: { ...params }, signal })
}

// GET /api/faults/{id} —— 单条详情（不存在返回 404 fault_not_found）。
export function fetchFault(id: number, signal?: AbortSignal): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}`, { signal })
}

// POST /api/faults —— 登记故障（成功 201；pipeline_id 无效 404；校验失败 422）。
export function createFault(payload: FaultCreatePayload): Promise<Fault> {
  return request<Fault>('/api/faults', { method: 'POST', body: payload })
}

// PATCH /api/faults/{id}/transition —— 状态流转（400 缺说明 / 404 不存在 / 409 非法流转 / 422 校验）。
export function transitionFault(id: number, payload: FaultTransitionPayload): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}/transition`, { method: 'PATCH', body: payload })
}

// PATCH /api/faults/{id} —— 修改基础信息（404 不存在 / 409 done 后说明锁定 / 422 校验）。
export function updateFault(id: number, payload: FaultUpdatePayload): Promise<Fault> {
  return request<Fault>(`/api/faults/${id}`, { method: 'PATCH', body: payload })
}

// GET /api/faults/export —— 导出 CSV（复用列表筛选口径，不分页；筛选参数与列表同形，故用 Pick 复用类型；
// 第二阶段起导出口径含 priority，与列表筛选保持同步）。
export type FaultExportParams = Pick<FaultListParams, 'pipeline_id' | 'status' | 'priority'>

// 导出触发方式（需求文档 D3 决策）：拼 URL + 隐藏 <a> click，浏览器原生处理下载与文件名
//（文件名由后端 Content-Disposition 下发）。不走 request()：它按 JSON 解析响应，
// 而导出返回的是 CSV 文件流；参数合法性由筛选组件（下拉/数字）保证，422 实际触发不了。
export function exportFaultsCsv(params: FaultExportParams = {}): void {
  const base = import.meta.env.VITE_API_BASE_URL
  const sp = new URLSearchParams()
  // 跳过空值：参数类型不含 ''（列表页 params 已把 clearable 清空后的 '' 收敛成 undefined），
  // 故只需判 undefined/null（client.buildUrl 额外判 '' 是因为它的 QueryValue 类型含 string）
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      sp.append(key, String(value))
    }
  }
  const qs = sp.toString()
  const url = `${base}/api/faults/export${qs ? `?${qs}` : ''}`

  const a = document.createElement('a')
  a.href = url
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a) // 用完即移除，不在 DOM 留垃圾节点
}

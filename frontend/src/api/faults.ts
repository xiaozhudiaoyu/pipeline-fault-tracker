// 故障接口封装：对应后端 routers/faults.py 的五个端点。
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

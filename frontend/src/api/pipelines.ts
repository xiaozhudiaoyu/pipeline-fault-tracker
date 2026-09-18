// 流水线接口封装。
// 按用户决策（2026-09-18）：前端对流水线【只读】——仅用 GET 列表做筛选/登记下拉数据源，
// 不做创建 UI（后端虽有 POST /api/pipelines，但前端不对接）。
import { request } from './client'
import type { Pipeline } from '../types/fault'

// GET /api/pipelines —— 返回全部流水线（后端按 code 升序）。
export function fetchPipelines(signal?: AbortSignal): Promise<Pipeline[]> {
  return request<Pipeline[]>('/api/pipelines', { signal })
}

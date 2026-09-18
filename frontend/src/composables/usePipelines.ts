// 流水线列表查询（TanStack Query v4）。
// 供「列表页筛选下拉」与「登记页流水线下拉」复用（通用能力封装，避免各页各拉一次）。
import { useQuery } from '@tanstack/vue-query'

import { fetchPipelines } from '../api/pipelines'

export function usePipelines() {
  return useQuery({
    queryKey: ['pipelines'],
    queryFn: ({ signal }) => fetchPipelines(signal),
    // 流水线是变化很少的主数据，缓存 5 分钟内不重新请求，减少无谓往返。
    staleTime: 5 * 60 * 1000,
  })
}

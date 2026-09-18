// 故障列表查询（TanStack Query v4）。
// queryKey 里放入响应式的 params（ComputedRef），vue-query 会自动追踪：筛选/翻页变化即重新请求。
import { useQuery } from '@tanstack/vue-query'
import type { ComputedRef } from 'vue'

import { fetchFaults } from '../api/faults'
import type { FaultList, FaultListParams } from '../types/fault'

export function useFaultList(params: ComputedRef<FaultListParams>) {
  // 显式泛型 <FaultList, Error>：钉住数据类型与错误类型。
  // vue-query v4 的 useQuery 默认 TError=unknown，不显式声明则 error.value 收窄后是 {}，取不到 .message。
  return useQuery<FaultList, Error>({
    // params 是 ref，vue-query 解包后作为 key 的一部分；其值变化 → key 变化 → 自动 refetch。
    queryKey: ['faults', params],
    queryFn: ({ signal }) => fetchFaults(params.value, signal),
    // 翻页/改筛选时保留上一页数据，避免表格闪空（v4 选项，v5 已改名 placeholderData）。
    keepPreviousData: true,
  })
}

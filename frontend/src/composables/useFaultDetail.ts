// 单条故障详情查询（TanStack Query v4）。
// id 来自路由参数（字符串转数字，可能是 NaN）；用 enabled 守卫，仅在拿到合法正整数 ID 时才请求，
// 避免 /faults/abc 这类非法路径打出 GET /api/faults/NaN（后端会 422）。
import { useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'
import type { Ref } from 'vue'

import { fetchFault } from '../api/faults'
import type { Fault } from '../types/fault'

export function useFaultDetail(id: Ref<number>) {
  // 合法 ID 才启用查询（NaN / 0 / 负数一律不发请求）
  const enabled = computed(() => Number.isFinite(id.value) && id.value > 0)
  return useQuery<Fault, Error>({
    // id 是 ref，vue-query 解包后作为 key；其值变化 → key 变化 → 自动 refetch。
    queryKey: ['fault', id],
    queryFn: ({ signal }) => fetchFault(id.value, signal),
    enabled,
  })
}

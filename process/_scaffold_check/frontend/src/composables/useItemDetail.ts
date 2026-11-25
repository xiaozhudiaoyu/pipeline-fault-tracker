// 详情查询（TanStack Query v4）。
import { useQuery } from '@tanstack/vue-query'
import type { ComputedRef, Ref } from 'vue'

import { fetchItem } from '../api/items'
import type { Item } from '../types/item'

export function useItemDetail(
  id: ComputedRef<number> | Ref<number>,
  enabled: ComputedRef<boolean> | Ref<boolean> | boolean = true,
) {
  return useQuery<Item, Error>({
    queryKey: ['item', id],
    queryFn: ({ signal }) => fetchItem(id.value, signal),
    // enabled=false 时不发请求（如新建模式没有 id 可查）；有 id 后再自动启用。
    enabled,
    // 未找到（404）时启用重试无意义，关掉避免无谓请求；网络错误（TypeError）仍会重试。
    retry: (_failureCount, err) => {
      return !(err instanceof Error && err.message.includes('没有找到'))
    },
  })
}

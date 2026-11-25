// 列表查询（TanStack Query v4）。
// queryKey 里放入响应式的 params（ComputedRef），vue-query 会自动追踪：筛选/翻页变化即重新请求。
import { useQuery } from '@tanstack/vue-query'
import type { ComputedRef } from 'vue'

import { fetchItems } from '../api/items'
import type { ItemList, ItemListParams } from '../types/item'

export function useItemList(params: ComputedRef<ItemListParams>) {
  // 显式泛型 <ItemList, Error>：钉住数据类型与错误类型。
  // vue-query v4 的 useQuery 默认 TError=unknown，不显式声明则 error.value 收窄后是 {}，取不到 .message。
  return useQuery<ItemList, Error>({
    // params 是 ref，vue-query 解包后作为 key 的一部分；其值变化 → key 变化 → 自动 refetch。
    queryKey: ['items', params],
    queryFn: ({ signal }) => fetchItems(params.value, signal),
    // 翻页/改筛选时保留上一页数据，避免表格闪空（v4 选项，v5 已改名 placeholderData）。
    keepPreviousData: true,
  })
}

// 通用查询封装（TanStack Query v4）。
//
// 骨架阶段没有具体资源，业务接入时基于本函数套一层：
//
//   export function useBookList(params: ComputedRef<BookListParams>) {
//     return useApiQuery<BookList>(['books', params], ({ signal }) => fetchBooks(params.value, signal))
//   }
//
// 统一策略：404（记录不存在）不重试，其余错误按 TanStack 默认策略重试。
import { useQuery } from '@tanstack/vue-query'
import type { QueryFunction, QueryKey } from '@tanstack/vue-query'

import { ApiError } from '../api/client'

export function useApiQuery<T>(queryKey: QueryKey, queryFn: QueryFunction<T, QueryKey>) {
  return useQuery<T, Error>({
    queryKey,
    queryFn,
    // 404（记录不存在）重试无意义，关掉避免无谓请求；网络错误等仍会重试。
    retry: (_failureCount, err) => !(err instanceof ApiError && err.status === 404),
  })
}

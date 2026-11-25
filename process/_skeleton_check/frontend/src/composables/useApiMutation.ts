// 通用变更封装（TanStack Query v4）。
//
// 骨架阶段没有具体资源，业务接入时基于本函数套一层：
//
//   export function useBookMutations() {
//     return {
//       create: useApiMutation<Book, BookCreatePayload>({
//         mutationFn: createBook,
//         invalidate: [['books']],
//         successMessage: '创建成功',
//       }),
//       update: useApiMutation<Book, { id: number; payload: BookUpdatePayload }>({ ... }),
//       remove: useApiMutation<void, number>({ ... }),
//     }
//   }
//
// 统一策略：成功后失效重取指定 queryKey 并提示（可选），失败统一 ElMessage 报错。
// 注意 v4 的变更进行中状态是 isLoading（v5 才是 isPending），提交按钮 loading 用它。
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import type { QueryKey } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'

import { toUserMessage } from '../api/client'

interface UseApiMutationOptions<TData, TVariables> {
  mutationFn: (variables: TVariables) => Promise<TData>
  /** 成功后失效重取的 queryKey 列表（每个元素是一个 queryKey，如 [['books'], ['book', id]]） */
  invalidate?: QueryKey[]
  /** 成功提示文案（不传则静默） */
  successMessage?: string
}

export function useApiMutation<TData, TVariables>(options: UseApiMutationOptions<TData, TVariables>) {
  const queryClient = useQueryClient()
  return useMutation<TData, Error, TVariables>({
    mutationFn: options.mutationFn,
    onSuccess: () => {
      for (const key of options.invalidate ?? []) {
        queryClient.invalidateQueries(key)
      }
      if (options.successMessage) ElMessage.success(options.successMessage)
    },
    onError: (err) => ElMessage.error(toUserMessage(err)),
  })
}

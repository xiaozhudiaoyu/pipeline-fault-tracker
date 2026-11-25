// 「变更」操作（创建 / 更新 / 删除）——基于 TanStack Query v4 的 useMutation。
// 集中处理三件事，避免各页面重复写：
//   1. 调接口（createItem / updateItem / deleteItem）；
//   2. 成功后刷新相关查询缓存（列表 invalidate、详情写回）；
//   3. 全局反馈（ElMessage 成功/失败提示）。
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'

import { ApiError } from '../api/client'
import { createItem, deleteItem, updateItem } from '../api/items'
import type { Item, ItemCreatePayload, ItemUpdatePayload } from '../types/item'

// 把后端错误 / 网络错误翻译成用户可读文案（有字段级 details 时补上第一条，帮助定位问题）。
export function toUserMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const first = err.details[0]
    return first && first.message ? `${err.message}（${first.message}）` : err.message
  }
  // fetch 在网络层失败（后端未启动 / 跨域 / 断网）抛 TypeError: Failed to fetch——比原始文案更易懂。
  if (err instanceof TypeError) {
    return '无法连接后端服务，请确认服务已启动'
  }
  if (err instanceof Error) {
    return err.message || '操作失败，请稍后重试'
  }
  return '操作失败，请稍后重试'
}

// id + payload 用对象承载（useMutation 的 variables 只能是单一入参）。
export interface UpdateVariables {
  id: number
  payload: ItemUpdatePayload
}

export function useItemMutations() {
  const queryClient = useQueryClient()

  // 创建：成功后让列表失效（新记录按 created_at 倒序应出现在列表靠前位置）。
  const create = useMutation<Item, Error, ItemCreatePayload>({
    mutationFn: (payload) => createItem(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] })
      ElMessage.success('创建成功')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  // 更新：成功后把返回的最新记录写回详情缓存 + 让列表失效。
  const update = useMutation<Item, Error, UpdateVariables>({
    mutationFn: ({ id, payload }) => updateItem(id, payload),
    onSuccess: (item) => {
      queryClient.setQueryData(['item', item.id], item)
      queryClient.invalidateQueries({ queryKey: ['items'] })
      ElMessage.success('修改已保存')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  // 删除：成功后移除详情缓存 + 列表失效。
  const remove = useMutation<void, Error, number>({
    mutationFn: (id) => deleteItem(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: ['item', id] })
      queryClient.invalidateQueries({ queryKey: ['items'] })
      ElMessage.success('删除成功')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  return { create, update, remove }
}

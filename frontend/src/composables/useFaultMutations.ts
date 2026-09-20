// 故障「变更」操作（登记 / 状态流转 / 修改基础信息）——基于 TanStack Query v4 的 useMutation。
// 集中处理三件事，避免各页面重复写：
//   1. 调接口（createFault / transitionFault / updateFault）；
//   2. 成功后刷新相关查询缓存（列表 invalidate、详情写回）；
//   3. 全局反馈（ElMessage 成功/失败提示）——即需求里的「全局反馈」。
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'

import { ApiError } from '../api/client'
import { createFault, transitionFault, updateFault } from '../api/faults'
import type { Fault, FaultCreatePayload, FaultTransitionPayload, FaultUpdatePayload } from '../types/fault'

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

// 状态流转需要 id + payload 两个值，用一个对象承载（useMutation 的 variables 只能是单一入参）。
export interface TransitionVariables {
  id: number
  payload: FaultTransitionPayload
}

// 修改基础信息同样需要 id + payload。
export interface UpdateVariables {
  id: number
  payload: FaultUpdatePayload
}

export function useFaultMutations() {
  const queryClient = useQueryClient()

  // 登记：成功后让列表失效（新记录按 occurred_at 倒序应出现在列表靠前位置）。
  const create = useMutation<Fault, Error, FaultCreatePayload>({
    mutationFn: (payload) => createFault(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['faults'] })
      ElMessage.success('故障登记成功')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  // 状态流转：成功后把返回的最新故障写回详情缓存 + 让列表失效（状态列可能变化）。
  const transition = useMutation<Fault, Error, TransitionVariables>({
    mutationFn: ({ id, payload }) => transitionFault(id, payload),
    onSuccess: (fault) => {
      queryClient.setQueryData(['fault', fault.id], fault)
      queryClient.invalidateQueries({ queryKey: ['faults'] })
      ElMessage.success('状态已更新')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  // 修改基础信息：成功后写回详情缓存 + 列表失效（location/symptom 列可能变化）。
  const update = useMutation<Fault, Error, UpdateVariables>({
    mutationFn: ({ id, payload }) => updateFault(id, payload),
    onSuccess: (fault) => {
      queryClient.setQueryData(['fault', fault.id], fault)
      queryClient.invalidateQueries({ queryKey: ['faults'] })
      ElMessage.success('修改已保存')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })

  return { create, transition, update }
}

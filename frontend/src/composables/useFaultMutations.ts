// 故障「变更」操作——基于 TanStack Query v4 的 useMutation。
// 集中处理三件事，避免各页面重复写：
//   1. 调接口（createFault / updateFault / 8 个闭环动作）；
//   2. 成功后刷新相关查询缓存（详情写回、列表与时间线失效）；
//   3. 全局反馈（ElMessage 成功/失败提示）——即需求里的「全局反馈」。
//
// 第三阶段 M6：旧 transition mutation 随 /transition 端点废除（D5），
// 改为 useFaultActions() 返回 8 个动作各自的 mutation——分开返回是为了
// 让面板按「哪个动作在提交」精确禁用按钮（需求四.5 防重复点击）。
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'

import { ApiError } from '../api/client'
import {
  addProgress,
  assignFault,
  changePriority,
  confirmFault,
  createFault,
  reassignFault,
  returnFault,
  startFault,
  submitFault,
  updateFault,
} from '../api/faults'
import type { Fault, FaultCreatePayload, FaultPriority, FaultUpdatePayload } from '../types/fault'

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

// 修改故障信息需要 id + payload。
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

  // 修改故障信息：成功后写回详情缓存 + 列表失效（location/symptom 列可能变化）。
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

  return { create, update }
}

// ── 闭环动作 mutations（详情页 FaultActionPanel 使用）─────────────────
// 每个动作一个变量类型：面板调用时统一传 faultId（无附加参数的动作只传 id）。

// 8 个动作共用的成功后处理：详情写回 + 列表失效 + 时间线失效（动作必产时间线，需求四.2 同事务）。
function useActionBase<V>(fn: (vars: V) => Promise<Fault>, successText: string) {
  const queryClient = useQueryClient()
  return useMutation<Fault, Error, V>({
    mutationFn: fn,
    onSuccess: (fault) => {
      queryClient.setQueryData(['fault', fault.id], fault)
      queryClient.invalidateQueries({ queryKey: ['faults'] })
      queryClient.invalidateQueries({ queryKey: ['fault-timelines', fault.id] })
      ElMessage.success(successText)
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })
}

export interface AssignVariables {
  id: number
  assigneeId: number
}

// 闭环动作集合：返回对象按动作命名，面板逐一取 .isLoading 禁用对应按钮。
// 说明：权限矩阵前端只做「按钮显不显示」，真正的裁判是后端 403/409——被拒时 ElMessage 播报原因。
export function useFaultActions() {
  return {
    // 指派（admin）：pending 无负责人 → 设定负责人
    assign: useActionBase<AssignVariables>(({ id, assigneeId }) => assignFault(id, assigneeId), '已指派负责人'),
    // 改派（admin）：换负责人，理由进时间线
    reassign: useActionBase<AssignVariables & { reason: string }>(
      ({ id, assigneeId, reason }) => reassignFault(id, assigneeId, reason),
      '已改派负责人',
    ),
    // 开始处理（负责人）：pending → processing
    start: useActionBase<number>((id) => startFault(id), '已开始处理'),
    // 追加进展（负责人）：processing 内多次
    progress: useActionBase<{ id: number; note: string }>(
      ({ id, note }) => addProgress(id, note),
      '进展已记录',
    ),
    // 提交处理结果（负责人）：processing → awaiting_confirmation
    submit: useActionBase<{ id: number; resultNote: string }>(
      ({ id, resultNote }) => submitFault(id, resultNote),
      '处理结果已提交，等待创建人确认',
    ),
    // 确认完成（创建人 / admin 代确认）：→ done
    confirm: useActionBase<{ id: number; reason?: string }>(
      ({ id, reason }) => confirmFault(id, reason),
      '故障已确认完成',
    ),
    // 退回处理（创建人）：awaiting_confirmation → processing
    return: useActionBase<{ id: number; reason: string }>(
      ({ id, reason }) => returnFault(id, reason),
      '已退回处理',
    ),
    // 优先级调整（admin / 创建人，done 之前）：不改状态
    priority: useActionBase<{ id: number; priority: FaultPriority }>(
      ({ id, priority }) => changePriority(id, priority),
      '优先级已调整',
    ),
  }
}

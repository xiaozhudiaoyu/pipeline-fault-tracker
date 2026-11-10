// 时间线类型：与后端 backend/app/schemas.py 的 TimelineOut 一一对应（第三阶段需求四.1）。
// 动作枚举取值已对照后端 models.TimelineAction 核实（return 在 Python 侧属性名为 return_，
// 但枚举值是 "return"，JSON 里就是 "return"）。
import type { FaultStatus } from './fault'

// 时间线动作类型（后端 models.TimelineAction）
export type TimelineAction =
  | 'create'
  | 'assign'
  | 'reassign'
  | 'start'
  | 'progress'
  | 'submit'
  | 'confirm'
  | 'return'
  | 'priority_change'

// 时间线一条记录（后端 TimelineOut）
export interface TimelineEntry {
  id: number
  fault_id: number
  action: TimelineAction
  operator_id: number | null // 历史数据（升级导入）为 null
  operator_name: string | null
  from_status: FaultStatus | null
  to_status: FaultStatus | null
  from_assignee_id: number | null
  to_assignee_id: number | null
  note: string | null
  is_imported: boolean // true = 升级时从旧 handling_note 导入的"历史数据"
  created_at: string // ISO 8601
}

// 动作展示文案（FaultTimelineList 标题用；动词与 FaultActionPanel 按钮口径一致，需求四.5"同一操作同一名称"）
export const TIMELINE_ACTION_LABELS: Record<TimelineAction, string> = {
  create: '新建故障',
  assign: '指派负责人',
  reassign: '改派负责人',
  start: '开始处理',
  progress: '追加进展',
  submit: '提交处理结果',
  confirm: '确认完成',
  return: '退回处理',
  priority_change: '调整优先级',
}

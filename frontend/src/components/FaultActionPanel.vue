<script setup lang="ts">
// 故障处理动作面板（第三阶段 M6，需求四.3）：按「当前状态 × 角色 × 归属」直接渲染动作按钮，
// 废除旧「下拉选目标状态再推进」交互（旧 StatusTransitionPanel 随 D5 一并移除）。
//
// 显隐矩阵镜像后端 app/auth.py 的 check_can_*（后端是最终裁判，这里只做体验层过滤）：
//   指派 assign   ：admin，pending/processing 且无负责人（processing 分支专为旧库升级来、
//                   负责人为 NULL 的遗留数据开口子，对齐后端 check_can_assign——它只挡 done/待确认）
//   改派 reassign ：admin，pending/processing 且已有负责人（D6：待确认不可改派）
//   开始 start    ：当前负责人，pending
//   进展 progress ：当前负责人，processing（可多次）
//   提交 submit   ：当前负责人，processing → 待确认
//   确认 confirm  ：创建人；创建人不可用（历史数据/已停用）时 admin 代确认（理由必填，SM11）；
//                   负责人本人任何情形不可自行确认（SM12，后端 403 兜底）
//   退回 return   ：创建人，待确认（admin 也不能代退回，保守同后端）
//   优先级 priority：admin 或创建人，done 之前
//   修改故障信息 edit：admin 或创建人，仅 pending（镜像 crud.update_fault，只改 location/symptom，
//                   原 FaultEditPanel 内嵌面板随本次改造并入动作对话框）
//
// 防重复点击（需求四.5）：任一动作提交中禁用全部按钮；对话框动作确定按钮同口径 loading。
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import FaultFlowSteps from './FaultFlowSteps.vue'
import { useFaultActions, useFaultMutations } from '../composables/useFaultMutations'
import { useUsers } from '../composables/useUsers'
import { isAdmin, currentUser } from '../composables/useAuth'
import { progressNoteSchema, reasonSchema, resultNoteSchema, TEXT_LIMITS } from '../schemas/auth'
import { faultUpdateSchema, FAULT_TEXT_LIMITS } from '../schemas/fault'
import { FAULT_PRIORITY_OPTIONS, FAULT_STATUS_META } from '../types/fault'
import type { Fault, FaultPriority, FaultUpdatePayload } from '../types/fault'

const props = defineProps<{ fault: Fault }>()

const actions = useFaultActions()
// 修改故障信息走 PATCH /api/faults/{id}（非闭环动作，useFaultMutations.update：成功写回详情缓存）。
const { update } = useFaultMutations()

// 用户表仅 admin 拉（/api/users 后端限管理员）：指派/改派候选 + 代确认前查创建人是否停用
const { data: users } = useUsers(isAdmin)

// ── 归属判定 ──────────────────────────────────────────────────────────
const me = computed(() => currentUser.value)
const isCreator = computed(() => !!me.value && props.fault.created_by?.id === me.value.id)
const isAssignee = computed(() => !!me.value && props.fault.assignee?.id === me.value.id)
// 创建人是否"可用"：有创建人且其账号启用。历史数据（created_by=null）或已停用 → admin 可代确认。
const creatorUsable = computed(() => {
  const creator = props.fault.created_by
  if (!creator) return false
  const fresh = users.value?.find((u) => u.id === creator.id)
  return fresh ? fresh.is_active : true // 用户表查不到（理论不发生）按可用处理，交给后端裁判
})

// ── 动作显隐矩阵（状态 × 角色 × 归属）────────────────────────────────
const s = computed(() => props.fault.status)
// 指派（对齐 check_can_assign）：admin 且无负责人即可指派，不限 pending——processing 但负责人
// 为 NULL 的历史遗留数据也需要能被接手（后端本就放行，assign_fault 不改状态只挂负责人）。
// done/awaiting 后端会拒（assign 与改派语义分离：已有负责人应走 reassign）。
const canAssign = computed(
  () => isAdmin.value && (s.value === 'pending' || s.value === 'processing') && !props.fault.assignee
)
const canReassign = computed(
  () => isAdmin.value && (s.value === 'pending' || s.value === 'processing') && !!props.fault.assignee
)
const canStart = computed(() => isAssignee.value && s.value === 'pending')
const canProgress = computed(() => isAssignee.value && s.value === 'processing')
const canSubmit = computed(() => isAssignee.value && s.value === 'processing')
// 创建人确认（非负责人本人）；admin 代确认：创建人不可用且自己不是负责人
const canConfirmByCreator = computed(
  () => s.value === 'awaiting_confirmation' && isCreator.value && !isAssignee.value
)
const canConfirmByAdmin = computed(
  () =>
    isAdmin.value &&
    s.value === 'awaiting_confirmation' &&
    !isAssignee.value &&
    !creatorUsable.value
)
const canReturn = computed(() => s.value === 'awaiting_confirmation' && isCreator.value)
const canPriority = computed(() => (isAdmin.value || isCreator.value) && s.value !== 'done')
// 修改故障信息（镜像 crud.update_fault）：仅 pending 且（创建人本人 或 admin）
const canEdit = computed(() => s.value === 'pending' && (isAdmin.value || isCreator.value))

// 终态与「与我无关」两种空态文案
const isDone = computed(() => s.value === 'done')
const hasAnyAction = computed(
  () =>
    canAssign.value || canReassign.value || canStart.value || canProgress.value ||
    canSubmit.value || canConfirmByCreator.value || canConfirmByAdmin.value ||
    canReturn.value || canPriority.value || canEdit.value
)

// 当前卡在谁手里（需求四.5"知道当前等待谁操作"）
const waitingHint = computed(() => {
  const f = props.fault
  if (f.status === 'pending') {
    return f.assignee ? `已分派给 ${f.assignee.display_name}，等待其开始处理` : '尚未指派负责人，等待管理员分派'
  }
  if (f.status === 'processing') {
    return f.assignee
      ? `处理中，当前由 ${f.assignee.display_name} 跟进`
      : '处理中，但负责人缺失（历史遗留数据），等待管理员指派接手'
  }
  if (f.status === 'awaiting_confirmation') {
    return creatorUsable.value
      ? `等待创建人 ${f.created_by?.display_name ?? '（历史数据）'} 确认或退回`
      : '创建人账号不可用，等待管理员代确认'
  }
  return '已完成（终态），按业务规则不可再流转'
})

// ── 提交中禁全部按钮（需求四.5 防重复点击）───────────────────────────
// update（修改故障信息）与闭环动作并列，任一提交中同样禁全部按钮。
const anyLoading = computed(
  () => Object.values(actions).some((m) => m.isLoading.value) || update.isLoading.value,
)

// ── 需要输入的动作统一走一个对话框 ────────────────────────────────────
type DialogName = 'assign' | 'reassign' | 'progress' | 'submit' | 'confirm' | 'return' | 'priority' | 'edit'

const dialogName = ref<DialogName | null>(null)
// el-dialog 的 v-model 需要 boolean：用可写 computed 代理（关闭时只认 false，避免把 boolean 写回 DialogName）
const dialogVisible = computed({
  get: () => dialogName.value !== null,
  set: (v) => {
    if (!v) closeDialog()
  },
})
const dialogError = ref('')
const dialogForm = reactive<{ assigneeId: number | undefined; text: string; priority: FaultPriority; location: string; symptom: string }>({
  assigneeId: undefined,
  text: '',
  priority: 'normal',
  location: '',
  symptom: '',
})
// 修改故障信息的字段级报错（Zod issues 按字段归并，同原 FaultEditPanel 口径）
const fieldErrors = reactive<Record<string, string>>({})

function clearFieldErrors() {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
}

const DIALOG_TITLES: Record<DialogName, string> = {
  assign: '指派负责人',
  reassign: '改派负责人',
  progress: '追加进展',
  submit: '提交处理结果',
  confirm: '代确认完成',
  return: '退回处理',
  priority: '调整优先级',
  edit: '修改故障信息',
}
const dialogTitle = computed(() => (dialogName.value ? DIALOG_TITLES[dialogName.value] : ''))
const showAssigneeSelect = computed(() => dialogName.value === 'assign' || dialogName.value === 'reassign')
const showText = computed(() =>
  ['reassign', 'progress', 'submit', 'confirm', 'return'].includes(dialogName.value ?? '')
)
const TEXT_PLACEHOLDERS: Partial<Record<DialogName, string>> = {
  reassign: '请填写改派理由（至少 2 个字）',
  progress: '请填写本次进展（至少 2 个字）',
  submit: '请填写处理结果说明（至少 5 个字，将作为结案说明）',
  confirm: '创建人账号不可用，请填写代确认理由（必填，至少 2 个字）',
  return: '请填写退回原因（至少 2 个字）',
}
const textPlaceholder = computed(() => (dialogName.value ? TEXT_PLACEHOLDERS[dialogName.value] ?? '' : ''))

// 文本框输入上限按动作取值，与 zod 校验共用 schemas/auth 的 TEXT_LIMITS（单一来源）：
// 理由类（改派/退回/代确认）后端只收 500 字，进展/结果说明 2000 字。
// 之前写死 2000 导致计数器放到 2000、提交却被 500 的校验拦下（显示与校验不对称）。
const TEXT_MAXLENGTHS: Partial<Record<DialogName, number>> = {
  reassign: TEXT_LIMITS.reason,
  confirm: TEXT_LIMITS.reason,
  return: TEXT_LIMITS.reason,
  progress: TEXT_LIMITS.progressNote,
  submit: TEXT_LIMITS.resultNote,
}
// 未登记的动作兜底取最严的 reason 上限（宁可少不行，避免又多一个 2000 默认值）
const textMaxlength = computed(() =>
  dialogName.value ? TEXT_MAXLENGTHS[dialogName.value] ?? TEXT_LIMITS.reason : TEXT_LIMITS.reason,
)

// 指派/改派候选：启用中的处理人员；改派时排除现任（选同样的人无意义且会写时间线噪声）
const handlerOptions = computed(() =>
  (users.value ?? []).filter((u) => u.role === 'handler' && u.is_active && u.id !== props.fault.assignee?.id)
)

function openDialog(name: DialogName) {
  dialogName.value = name
  dialogError.value = ''
  clearFieldErrors()
  dialogForm.assigneeId = undefined
  dialogForm.text = ''
  dialogForm.priority = props.fault.priority
  // 修改故障信息：预填当前值（同原 FaultEditPanel 的 startEdit）
  if (name === 'edit') {
    dialogForm.location = props.fault.location
    dialogForm.symptom = props.fault.symptom
  }
}

function closeDialog() {
  dialogName.value = null
}

// 对话框确定：按动作校验 → 调对应 mutation → 成功关框（缓存刷新与提示在 useFaultActions 内统一处理）
function onDialogConfirm() {
  const name = dialogName.value
  if (!name) return
  dialogError.value = ''

  const assigneeId = dialogForm.assigneeId
  const text = dialogForm.text.trim()

  if (name === 'assign' || name === 'reassign') {
    if (!assigneeId) {
      dialogError.value = '请选择负责人'
      return
    }
  }
  if (name === 'reassign' || name === 'return' || name === 'confirm') {
    const r = reasonSchema.safeParse(text)
    if (!r.success) {
      dialogError.value = r.error.issues[0]?.message ?? '请填写理由'
      return
    }
  }
  if (name === 'progress') {
    const r = progressNoteSchema.safeParse(text)
    if (!r.success) {
      dialogError.value = r.error.issues[0]?.message ?? '请填写进展内容'
      return
    }
  }
  if (name === 'submit') {
    const r = resultNoteSchema.safeParse(text)
    if (!r.success) {
      dialogError.value = r.error.issues[0]?.message ?? '请填写处理结果说明'
      return
    }
  }

  // 修改故障信息：Zod 校验 → 只发改动过的字段（后端 exclude_unset 只应用传来的键，
  // 避免无谓 bump updated_at）→ 无改动不发请求直接关框（同原 FaultEditPanel.onSubmit）。
  if (name === 'edit') {
    clearFieldErrors()
    const r = faultUpdateSchema.safeParse({ location: dialogForm.location, symptom: dialogForm.symptom })
    if (!r.success) {
      for (const issue of r.error.issues) {
        const key = String(issue.path[0] ?? 'form')
        if (!fieldErrors[key]) fieldErrors[key] = issue.message
      }
      return
    }
    const payload: FaultUpdatePayload = {}
    const loc = dialogForm.location.trim()
    if (loc !== props.fault.location) payload.location = loc
    const sym = dialogForm.symptom.trim()
    if (sym !== props.fault.symptom) payload.symptom = sym
    if (Object.keys(payload).length === 0) {
      closeDialog()
      ElMessage.info('没有需要保存的改动')
      return
    }
    update.mutate({ id: props.fault.id, payload }, { onSuccess: () => closeDialog() })
    return
  }

  const id = props.fault.id
  const done = () => closeDialog()
  if (name === 'assign') actions.assign.mutate({ id, assigneeId: assigneeId! }, { onSuccess: done })
  else if (name === 'reassign') actions.reassign.mutate({ id, assigneeId: assigneeId!, reason: text }, { onSuccess: done })
  else if (name === 'progress') actions.progress.mutate({ id, note: text }, { onSuccess: done })
  else if (name === 'submit') actions.submit.mutate({ id, resultNote: text }, { onSuccess: done })
  else if (name === 'confirm') actions.confirm.mutate({ id, reason: text }, { onSuccess: done })
  else if (name === 'return') actions.return.mutate({ id, reason: text }, { onSuccess: done })
  else if (name === 'priority') actions.priority.mutate({ id, priority: dialogForm.priority }, { onSuccess: done })
}

// 无对话框的直接动作：开始处理 / 创建人确认完成
function onStart() {
  actions.start.mutate(props.fault.id)
}
function onConfirmByCreator() {
  actions.confirm.mutate({ id: props.fault.id })
}

// 对话框当前动作的 loading（确定按钮转圈防重复）
const dialogLoading = computed(() => {
  const name = dialogName.value
  if (!name) return false
  const map: Record<DialogName, { isLoading: { value: boolean } }> = {
    assign: actions.assign,
    reassign: actions.reassign,
    progress: actions.progress,
    submit: actions.submit,
    confirm: actions.confirm,
    return: actions.return,
    priority: actions.priority,
    edit: update,
  }
  return map[name].isLoading.value
})
</script>

<template>
  <div class="action-panel">
    <!-- <h3 class="panel-title">处理操作</h3> -->

    <!-- 处理进度步骤条（用户指定置于本面板标题下方；组件自带底部分隔线） -->
    <FaultFlowSteps :fault="fault" />

    <!-- 当前环节提示：让用户知道流程卡在哪、等待谁（需求四.5） -->
    <p class="waiting-hint">
      <el-tag :type="FAULT_STATUS_META[fault.status]?.tag ?? 'info'" size="small" disable-transitions>
        {{ FAULT_STATUS_META[fault.status]?.label ?? fault.status }}
      </el-tag>
      <span class="waiting-text">{{ waitingHint }}</span>
    </p>

    <!-- 动作按钮区：仅渲染当前有权执行的动作；全部动作提交中时整体禁用 -->
    <div v-if="!isDone && hasAnyAction" class="action-buttons">
      <el-button v-if="canAssign" type="primary" :disabled="anyLoading" @click="openDialog('assign')">
        指派负责人
      </el-button>
      <el-button v-if="canReassign" type="primary" plain :disabled="anyLoading" @click="openDialog('reassign')">
        改派负责人
      </el-button>
      <el-button v-if="canStart" type="primary" :disabled="anyLoading" @click="onStart">开始处理</el-button>
      <el-button v-if="canProgress" :disabled="anyLoading" @click="openDialog('progress')">追加进展</el-button>
      <el-button v-if="canSubmit" type="success" :disabled="anyLoading" @click="openDialog('submit')">
        提交处理结果
      </el-button>
      <el-button v-if="canConfirmByCreator" type="success" :disabled="anyLoading" @click="onConfirmByCreator">
        确认完成
      </el-button>
      <el-button v-if="canConfirmByAdmin" type="warning" :disabled="anyLoading" @click="openDialog('confirm')">
        代确认完成
      </el-button>
      <el-button v-if="canReturn" type="danger" plain :disabled="anyLoading" @click="openDialog('return')">
        退回处理
      </el-button>
      <el-button v-if="canPriority" :disabled="anyLoading" @click="openDialog('priority')">调整优先级</el-button>
      <el-button v-if="canEdit" :disabled="anyLoading" @click="openDialog('edit')">修改故障信息</el-button>
    </div>

    <el-alert
      v-else-if="isDone"
      title="该故障已完成（终态），不可再执行处理动作。"
      type="success"
      show-icon
      :closable="false"
    />
    <el-alert
      v-else
      title="当前没有您可执行的操作：处理动作仅对创建人、负责人或管理员开放。"
      type="info"
      show-icon
      :closable="false"
    />

    <!-- 统一动作对话框：指派/改派（选人）、进展/提交/代确认/退回（填文本）、优先级（单选） -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px" :close-on-click-modal="false">
      <el-form label-position="top" @submit.prevent>
        <el-form-item v-if="showAssigneeSelect" label="负责人（仅启用中的处理人员）" :error="dialogError">
          <el-select v-model="dialogForm.assigneeId" placeholder="选择处理人员" class="dialog-control" filterable>
            <el-option v-for="h in handlerOptions" :key="h.id" :label="`${h.display_name}（${h.username}）`" :value="h.id" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="showText" label="说明 / 理由" :error="dialogError">
          <el-input
            v-model="dialogForm.text"
            type="textarea"
            :rows="3"
            :placeholder="textPlaceholder"
            :maxlength="textMaxlength"
            show-word-limit
          />
        </el-form-item>

        <el-form-item v-if="dialogName === 'priority'" label="目标优先级">
          <!-- 本机 element-plus 2.5.6 的 el-radio 只有 label prop（value prop 自 2.6 才引入，已核源码） -->
          <el-radio-group v-model="dialogForm.priority">
            <el-radio v-for="opt in FAULT_PRIORITY_OPTIONS" :key="opt.value" :label="opt.value">
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <!-- 修改故障信息：字段与原 FaultEditPanel 一致，仅开放 location / symptom -->
        <template v-if="dialogName === 'edit'">
          <el-form-item label="故障位置" required :error="fieldErrors.location">
            <el-input
              v-model="dialogForm.location"
              placeholder="如：3 号工位传送带"
              :maxlength="FAULT_TEXT_LIMITS.location"
              show-word-limit
              class="dialog-control"
            />
          </el-form-item>
          <el-form-item label="故障现象" required :error="fieldErrors.symptom">
            <el-input
              v-model="dialogForm.symptom"
              type="textarea"
              :rows="3"
              placeholder="请描述故障现象（至少 5 个字）"
              :maxlength="FAULT_TEXT_LIMITS.symptom"
              show-word-limit
              class="dialog-control"
            />
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <el-button :disabled="dialogLoading" @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="dialogLoading" @click="onDialogConfirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.action-panel {
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color, #dcdfe6);
}
.panel-title {
  margin: 0 0 12px;
  /* 全局字阶 L2：面板标题 16px，字重补齐 600 */
  font-size: 16px;
  font-weight: 600;
}
.waiting-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0 0 16px;
}
.waiting-text {
  color: var(--el-text-color-secondary, #909399);
  font-size: 14px;
}
.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  .el-button+.el-button {
    margin-left: 0;
  }
}
.dialog-control {
  width: 100%;
}
</style>

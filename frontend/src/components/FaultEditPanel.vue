<script setup lang="ts">
// 修改基础信息面板：默认只读，点「编辑」展开表单（预填当前值）→ 保存/取消。
// 校验镜像后端 FaultUpdate（faultUpdateSchema），但后端是最终裁判（非法/锁定返回 422/409）。
// 业务规则：done 后 handling_note 锁定不可改（镜像 crud.update_fault 的 409），禁用输入避免用户点了才被拒。
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useFaultMutations } from '../composables/useFaultMutations'
import { faultUpdateSchema } from '../schemas/fault'
import { FAULT_PRIORITY_OPTIONS } from '../types/fault'
import type { Fault, FaultPriority, FaultUpdatePayload } from '../types/fault'

const props = defineProps<{ fault: Fault }>()

const { update } = useFaultMutations()
// 同登记页：把嵌套 Ref 提为顶层别名，模板中才会自动解包成布尔值。
const submitting = update.isLoading

// 编辑态开关：false=只读（只显示「编辑」按钮），true=展开表单
const editing = ref(false)

const form = reactive<{ location: string; symptom: string; handling_note: string; priority: FaultPriority }>({
  location: '',
  symptom: '',
  handling_note: '',
  priority: 'normal',
})
const fieldErrors = reactive<Record<string, string>>({})

// done 后处理说明锁定（镜像后端 update_fault：done 时改 handling_note → 409）
const noteLocked = computed(() => props.fault.status === 'done')

function clearErrors() {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
}

// 进入编辑态：用当前值预填表单（handling_note 为 null 时填空串）
function startEdit() {
  form.location = props.fault.location
  form.symptom = props.fault.symptom
  form.handling_note = props.fault.handling_note ?? ''
  form.priority = props.fault.priority
  clearErrors()
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  clearErrors()
}

// 切换到另一条故障（详情页 id 变化复用同一实例）时退出编辑态并清错误
watch(
  () => props.fault.id,
  () => {
    editing.value = false
    clearErrors()
  }
)

function onSubmit() {
  clearErrors()

  const result = faultUpdateSchema.safeParse(form)
  if (!result.success) {
    // 按字段归并 Zod issues（每个字段只取第一条，同登记页）
    for (const issue of result.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      if (!fieldErrors[key]) fieldErrors[key] = issue.message
    }
    return
  }

  // 只发「改动过」的字段：后端 exclude_unset 只应用传来的键，避免无谓地 bump updated_at。
  const payload: FaultUpdatePayload = {}
  const loc = form.location.trim()
  if (loc !== props.fault.location) payload.location = loc
  const sym = form.symptom.trim()
  if (sym !== props.fault.symptom) payload.symptom = sym
  // 优先级（第二阶段）：仅在改动时发；后端保证改它不碰 status（需求二.1），done 后也可改。
  if (form.priority !== props.fault.priority) payload.priority = form.priority
  // handling_note：done 锁定不发；非 done 时仅在「非空且有改动」时发（后端不支持清空/显式 null）。
  if (!noteLocked.value) {
    const note = form.handling_note.trim()
    if (note.length > 0 && note !== (props.fault.handling_note ?? '')) {
      payload.handling_note = note
    }
  }

  // 没有任何改动：不发请求，直接退出编辑态
  if (Object.keys(payload).length === 0) {
    ElMessage.info('没有需要保存的改动')
    editing.value = false
    return
  }

  update.mutate(
    { id: props.fault.id, payload },
    {
      onSuccess: () => {
        // 成功 toast 与详情写回已在 useFaultMutations 内统一处理，这里只收起表单
        editing.value = false
      },
    }
  )
}
</script>

<template>
  <div class="edit-panel">
    <h3 class="panel-title">修改基础信息</h3>

    <el-button v-if="!editing" type="primary" plain @click="startEdit">编辑</el-button>

    <el-form v-else label-position="top" @submit.prevent>
      <el-form-item label="故障位置" required :error="fieldErrors.location">
        <el-input
          v-model="form.location"
          placeholder="如：3 号工位传送带"
          maxlength="200"
          show-word-limit
          class="control"
        />
      </el-form-item>

      <el-form-item label="故障现象" required :error="fieldErrors.symptom">
        <el-input
          v-model="form.symptom"
          type="textarea"
          :rows="3"
          placeholder="请描述故障现象（至少 5 个字）"
          maxlength="1000"
          show-word-limit
          class="control-wide"
        />
      </el-form-item>

      <el-form-item label="优先级">
        <!-- 修改优先级不改变处理状态（需求二.1）；done 后仍可改（不受说明锁定限制） -->
        <el-select v-model="form.priority" class="control">
          <el-option v-for="opt in FAULT_PRIORITY_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>

      <el-form-item
        :label="noteLocked ? '处理说明（已完成，锁定）' : '处理说明'"
        :error="fieldErrors.handling_note"
      >
        <el-input
          v-model="form.handling_note"
          type="textarea"
          :rows="3"
          :disabled="noteLocked"
          :placeholder="noteLocked ? '故障已完成，按业务规则处理说明不可修改' : '可修改处理说明（一旦填写至少 5 个字）'"
          maxlength="2000"
          show-word-limit
          class="control-wide"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="onSubmit">保存</el-button>
        <el-button :disabled="submitting" @click="cancelEdit">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.edit-panel {
  padding-top: 16px;
  margin-bottom: 24px;
  border-top: 1px solid var(--el-border-color, #dcdfe6);
}
.panel-title {
  margin: 0 0 16px;
  font-size: 16px;
}
.control {
  width: 320px;
}
.control-wide {
  width: 100%;
  max-width: 480px;
}
</style>

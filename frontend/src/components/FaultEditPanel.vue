<script setup lang="ts">
// 修改基础信息面板（第三阶段收窄）：默认只读，点「编辑」展开表单（预填当前值）→ 保存/取消。
// 可改字段仅剩 location / symptom：后端 crud.update_fault 只应用这两个键，
// priority 改走动作面板「调整优先级」（需时间线记录），handling_note 由「提交处理结果」写入。
// 可见性镜像后端门槛：仅 pending 且（创建人本人 或 admin），其余情况整块不渲染（后端仍是最终裁判）。
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { useFaultMutations } from '../composables/useFaultMutations'
import { currentUser, isAdmin } from '../composables/useAuth'
import { faultUpdateSchema } from '../schemas/fault'
import type { Fault, FaultUpdatePayload } from '../types/fault'

const props = defineProps<{ fault: Fault }>()

const { update } = useFaultMutations()
// 同登记页：把嵌套 Ref 提为顶层别名，模板中才会自动解包成布尔值。
const submitting = update.isLoading

// 权限门槛（镜像 crud.update_fault）：pending + (创建人 或 admin)
const canEdit = computed(
  () =>
    props.fault.status === 'pending' &&
    (isAdmin.value || (!!currentUser.value && props.fault.created_by?.id === currentUser.value.id))
)

// 编辑态开关：false=只读（只显示「编辑」按钮），true=展开表单
const editing = ref(false)

const form = reactive<{ location: string; symptom: string }>({
  location: '',
  symptom: '',
})
const fieldErrors = reactive<Record<string, string>>({})

function clearErrors() {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
}

// 进入编辑态：用当前值预填表单
function startEdit() {
  form.location = props.fault.location
  form.symptom = props.fault.symptom
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
  <div v-if="canEdit" class="edit-panel">
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
  /* 全局字阶 L2：面板标题 16px，字重补齐 600 与其他标题统一 */
  font-size: 16px;
  font-weight: 600;
}
.control {
  width: 320px;
}
.control-wide {
  width: 100%;
  max-width: 480px;
}
</style>

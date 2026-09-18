<script setup lang="ts">
// 状态推进面板：按当前故障状态渲染「允许的流转」，选目标状态 + 填处理说明 → 提交流转。
// 流转规则镜像后端（ALLOWED_TRANSITIONS + isNoteRequired），但后端是最终裁判（非法流转返回 409/400）。
import { computed, reactive, ref, watch } from 'vue'

import { useFaultMutations } from '../composables/useFaultMutations'
import { faultTransitionSchema } from '../schemas/fault'
import { ALLOWED_TRANSITIONS, FAULT_STATUS_META, isNoteRequired } from '../types/fault'
import type { Fault, FaultStatus, FaultTransitionPayload } from '../types/fault'

const props = defineProps<{ fault: Fault }>()

const { transition } = useFaultMutations()
// 同登记页：把嵌套 Ref 提为顶层别名，模板中才会自动解包成布尔值。
const submitting = transition.isLoading

// 当前状态允许的目标状态（done 为空数组 → 面板改显示「已终结」提示）
const allowedTargets = computed<FaultStatus[]>(() => ALLOWED_TRANSITIONS[props.fault.status] ?? [])

const form = reactive<{ target_status: FaultStatus | undefined; handling_note: string }>({
  target_status: undefined,
  handling_note: '',
})
const targetError = ref('')
const noteError = ref('')

// 目标为 done 时说明必填（用于动态 label 与占位提示）
const noteRequired = computed(() => (form.target_status ? isNoteRequired(form.target_status) : false))

// 切换到另一条故障（详情页 id 变化复用同一实例）时重置表单与错误
watch(
  () => props.fault.id,
  () => {
    form.target_status = undefined
    form.handling_note = ''
    targetError.value = ''
    noteError.value = ''
  }
)

function onSubmit() {
  targetError.value = ''
  noteError.value = ''

  // 先取到局部常量再判空：局部 const 的类型收窄在后续函数调用间保持稳定（reactive 属性收窄不可靠）
  const target = form.target_status
  if (!target) {
    targetError.value = '请选择要推进到的状态'
    return
  }

  const result = faultTransitionSchema.safeParse({
    target_status: target,
    handling_note: form.handling_note,
  })
  if (!result.success) {
    for (const issue of result.error.issues) {
      const key = issue.path[0]
      if (key === 'handling_note' && !noteError.value) noteError.value = issue.message
      else if (key === 'target_status' && !targetError.value) targetError.value = issue.message
    }
    return
  }

  // 空说明发 null（后端语义：null=本次不改说明），非空发去首尾空格后的值
  const note = form.handling_note.trim()
  const payload: FaultTransitionPayload = {
    target_status: target,
    handling_note: note.length > 0 ? note : null,
  }
  transition.mutate(
    { id: props.fault.id, payload },
    {
      onSuccess: () => {
        // 成功后清空选择（详情数据已由 useFaultMutations 写回缓存并驱动面板刷新）
        form.target_status = undefined
        form.handling_note = ''
      },
    }
  )
}
</script>

<template>
  <div class="transition-panel">
    <h3 class="panel-title">推进处理状态</h3>

    <el-alert
      v-if="allowedTargets.length === 0"
      title="该故障已完成（终态），按业务规则不可再流转。"
      type="success"
      show-icon
      :closable="false"
    />

    <el-form v-else label-position="top" @submit.prevent>
      <el-form-item label="目标状态" required :error="targetError">
        <el-select v-model="form.target_status" placeholder="选择要推进到的状态" class="control">
          <el-option v-for="t in allowedTargets" :key="t" :label="FAULT_STATUS_META[t].label" :value="t" />
        </el-select>
      </el-form-item>

      <el-form-item :label="noteRequired ? '处理说明（必填）' : '处理说明（可选）'" :error="noteError">
        <el-input
          v-model="form.handling_note"
          type="textarea"
          :rows="3"
          :placeholder="noteRequired ? '完成处理必须填写说明' : '可补充本次处理说明'"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="onSubmit">提交流转</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.transition-panel {
  padding-top: 16px;
  border-top: 1px solid var(--el-border-color, #dcdfe6);
}
.panel-title {
  margin: 0 0 16px;
  font-size: 16px;
}
.control {
  width: 240px;
}
</style>

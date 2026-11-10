<script setup lang="ts">
// 故障登记页：表单 + Zod 前端校验 + 提交（防重提）+ 成功跳转详情。
// 后端仍是最终裁判（非法输入返回 422/404），前端校验只为即时反馈、减少无效请求（规则 3.4）。
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'

import { useFaultMutations } from '../composables/useFaultMutations'
import { usePipelines } from '../composables/usePipelines'
import { faultCreateSchema } from '../schemas/fault'
import { FAULT_PRIORITY_OPTIONS } from '../types/fault'
import type { FaultCreatePayload, FaultPriority } from '../types/fault'

const router = useRouter()
const { data: pipelines, isLoading: pipelinesLoading } = usePipelines()
const { create } = useFaultMutations()
// create.isLoading 是嵌套在对象里的 Ref，模板不会自动解包；提成顶层别名，模板中才会解包成布尔值。
const submitting = create.isLoading

// 表单模型：pipeline_id 未选时为 undefined；occurred_at 由 el-date-picker 按 value-format 写成 ISO 字符串。
// priority 默认 normal（需求二.1）：两档单选均有合法值，不存在"未选"态。
const form = reactive<{
  pipeline_id: number | undefined
  location: string
  occurred_at: string
  symptom: string
  priority: FaultPriority
}>({
  pipeline_id: undefined,
  location: '',
  occurred_at: '',
  symptom: '',
  priority: 'normal',
})

// 字段级错误：Zod 校验失败时填充，绑定到对应 el-form-item 的 error 属性（红字提示）。
const fieldErrors = reactive<Record<string, string>>({})

function clearErrors() {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]
}

function onSubmit() {
  clearErrors()
  const result = faultCreateSchema.safeParse(form)
  if (!result.success) {
    // 按字段归并 Zod issues（每个字段只取第一条，避免同字段堆叠多条）
    for (const issue of result.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      if (!fieldErrors[key]) fieldErrors[key] = issue.message
    }
    return
  }
  // 防重提：mutate 期间 submitting 为 true，按钮 loading + disabled，重复点击无效。
  const payload: FaultCreatePayload = result.data
  create.mutate(payload, {
    onSuccess: (fault) => {
      // 登记成功 → 跳转到该故障详情页（成功 toast 与列表刷新已在 useFaultMutations 内统一处理）
      router.push({ name: 'fault-detail', params: { id: String(fault.id) } })
    },
  })
}

function onReset() {
  form.pipeline_id = undefined
  form.location = ''
  form.occurred_at = ''
  form.symptom = ''
  form.priority = 'normal'
  clearErrors()
}
</script>

<template>
  <section class="fault-create">
    <header class="create-header">
      <h2 class="create-title">新建故障</h2>
      <el-button link @click="router.push({ name: 'fault-list' })">
        <el-icon class="el-icon--left"><Back /></el-icon>返回列表
      </el-button>
    </header>

    <el-form label-width="100px" label-position="right" class="create-form" @submit.prevent>
      <el-form-item label="所属流水线" required :error="fieldErrors.pipeline_id">
        <el-select
          v-model="form.pipeline_id"
          placeholder="请选择流水线"
          filterable
          :loading="pipelinesLoading"
          class="form-control"
        >
          <el-option v-for="p in pipelines ?? []" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="故障位置" required :error="fieldErrors.location">
        <el-input
          v-model="form.location"
          placeholder="如：3 号工位传送带"
          maxlength="200"
          show-word-limit
          class="form-control"
        />
      </el-form-item>

      <el-form-item label="发生时间" required :error="fieldErrors.occurred_at">
        <el-date-picker
          v-model="form.occurred_at"
          type="datetime"
          placeholder="选择故障发生时间"
          value-format="YYYY-MM-DD[T]HH:mm:ss"
          class="form-control"
        />
      </el-form-item>

      <el-form-item label="故障现象" required :error="fieldErrors.symptom">
        <el-input
          v-model="form.symptom"
          type="textarea"
          :rows="4"
          placeholder="请描述故障现象（至少 5 个字）"
          maxlength="1000"
          show-word-limit
          class="form-control"
        />
      </el-form-item>

      <el-form-item label="优先级" required>
        <!-- 二选一用 radio 更直观；默认普通（schema 侧也有缺省兑底）。
             注：本机 element-plus 2.5.6 的 el-radio 只有 label prop（value prop 自 2.6 才引入，已核源码），
             选中值即 :label 绑定的值。 -->
        <el-radio-group v-model="form.priority">
          <el-radio v-for="opt in FAULT_PRIORITY_OPTIONS" :key="opt.value" :label="opt.value">
            {{ opt.label }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="onSubmit">提交登记</el-button>
        <el-button :disabled="submitting" @click="onReset">重置</el-button>
      </el-form-item>
    </el-form>
  </section>
</template>

<style scoped>
.fault-create {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
.create-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.create-title {
  margin: 0;
  /* 全局字阶 L1：页面标题 18px/600 */
  font-size: 18px;
  font-weight: 600;
}
.create-form {
  max-width: 640px;
}
.form-control {
  width: 100%;
}
</style>

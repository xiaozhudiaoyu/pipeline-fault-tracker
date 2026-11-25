<script setup lang="ts">
// 表单页：同时承载「新建」（无 id prop）与「编辑」（有 id prop，自动加载详情回填）。
// Zod 前端先校验（即时反馈），后端仍是最终裁判；提交期间按钮 loading 防重复点击。
import { computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useItemDetail } from '../composables/useItemDetail'
import { toUserMessage, useItemMutations } from '../composables/useItemMutations'
import { itemCreateSchema, itemUpdateSchema } from '../schemas/item'
import { ITEM_STATUS_OPTIONS } from '../types/item'
import type { ItemStatus } from '../types/item'

const props = defineProps<{ id?: string }>()
const router = useRouter()

const isEdit = computed(() => props.id !== undefined)
const itemId = computed(() => Number(props.id ?? 0))

// 编辑模式：加载详情用于回填（新建模式 enabled=false，不发请求）
const detailQuery = useItemDetail(itemId, isEdit)
const detail = computed(() => detailQuery.data.value)
const detailIsError = computed(() => detailQuery.isError.value)
const detailErrorMessage = computed(() =>
  detailQuery.error.value ? toUserMessage(detailQuery.error.value) : '加载失败',
)

// ---- 表单模型（description 空串=未填）----
const form = reactive({
  name: '',
  description: '',
  status: 'active' as ItemStatus,
})

// 字段错误：{ 字段名: 错误文案 }，供 el-form-item 的 :error 显示
const fieldErrors = reactive<Record<string, string>>({})

// 编辑模式：详情加载完成后回填表单
watch(detail, (d) => {
  if (isEdit.value && d) {
    form.name = d.name
    form.description = d.description ?? ''
    form.status = d.status
  }
})

const { create, update } = useItemMutations()

// ---- 校验：zod safeParse，失败把错误落到对应字段 ----
function validate(): boolean {
  for (const key of Object.keys(fieldErrors)) delete fieldErrors[key]

  const result = isEdit.value
    ? itemUpdateSchema.safeParse({ name: form.name, description: form.description, status: form.status })
    : itemCreateSchema.safeParse({ name: form.name, description: form.description })

  if (result.success) return true
  for (const issue of result.error.issues) {
    const key = String(issue.path[0] ?? 'name')
    fieldErrors[key] = issue.message
  }
  return false
}

const submitting = computed(() => create.isLoading.value || update.isLoading.value)

function onSubmit() {
  if (!validate()) return

  if (isEdit.value) {
    // 只发有改动的键由后端 exclude_unset 处理；空描述 = 不改（不发该键）
    update.mutate(
      {
        id: itemId.value,
        payload: {
          name: form.name.trim(),
          description: form.description.trim() || undefined,
          status: form.status,
        },
      },
      { onSuccess: (item) => router.push(`/items/${item.id}`) },
    )
  } else {
    create.mutate(
      { name: form.name.trim(), description: form.description.trim() || undefined },
      { onSuccess: (item) => router.push(`/items/${item.id}`) },
    )
  }
}
</script>

<template>
  <el-card>
    <el-page-header :content="isEdit ? '编辑' : '新建'" class="page-header" @back="router.back()" />

    <el-alert
      v-if="detailIsError"
      type="error"
      :closable="false"
      class="error-alert"
      :title="detailErrorMessage"
    />

    <el-form label-width="80px" style="max-width: 560px" @submit.prevent="onSubmit">
      <el-form-item label="名称" required :error="fieldErrors.name">
        <el-input v-model="form.name" placeholder="请输入名称（全表唯一）" maxlength="100" />
      </el-form-item>
      <el-form-item label="描述" :error="fieldErrors.description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="选填"
          maxlength="2000"
          show-word-limit
        />
      </el-form-item>
      <el-form-item v-if="isEdit" label="状态" :error="fieldErrors.status">
        <el-select v-model="form.status" style="width: 200px">
          <el-option v-for="opt in ITEM_STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" native-type="submit" :loading="submitting">
          {{ isEdit ? '保存修改' : '创建' }}
        </el-button>
        <el-button @click="router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.error-alert {
  margin-bottom: 16px;
}
</style>

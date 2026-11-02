<script setup lang="ts">
// 列表筛选栏：流水线 + 状态 + 优先级三个下拉，均可清空。
// 用 Vue 3.4 的 defineModel 与父组件（FaultListView）双向绑定；父层持有筛选状态并下发查询。
// 模型名用单词 pipeline / status / priority，避免 v-model:foo-bar 的 kebab/camel 大小写歧义。
// 流水线下拉数据来自 usePipelines（只读，见 api/pipelines.ts 注释）；状态/优先级选项来自 types/fault 常量。
import { usePipelines } from '../composables/usePipelines'
import { FAULT_PRIORITY_OPTIONS, FAULT_STATUS_OPTIONS } from '../types/fault'
import type { FaultPriority, FaultStatus } from '../types/fault'

const pipelineId = defineModel<number | undefined>('pipeline')
const status = defineModel<FaultStatus | undefined>('status')
const priority = defineModel<FaultPriority | undefined>('priority')

const { data: pipelines, isLoading, isError } = usePipelines()
</script>

<template>
  <div class="filter-bar">
    <el-select
      v-model="pipelineId"
      class="filter-item"
      placeholder="全部流水线"
      clearable
      filterable
      :loading="isLoading"
    >
      <el-option v-for="p in pipelines ?? []" :key="p.id" :label="p.name" :value="p.id" />
    </el-select>

    <el-select v-model="status" class="filter-item filter-item--status" placeholder="全部状态" clearable>
      <el-option v-for="opt in FAULT_STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
    </el-select>

    <!-- 优先级筛选（第二阶段）：清空 = 全部，可与流水线/状态组合（需求二.2） -->
    <el-select v-model="priority" class="filter-item filter-item--status" placeholder="全部优先级" clearable>
      <el-option v-for="opt in FAULT_PRIORITY_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
    </el-select>

    <span v-if="isError" class="filter-error">流水线下拉加载失败</span>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.filter-item {
  width: 240px;
}
.filter-item--status {
  width: 160px;
}
.filter-error {
  color: var(--el-color-danger, #f56c6c);
  font-size: 13px;
}
</style>

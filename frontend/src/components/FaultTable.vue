<script setup lang="ts">
// 故障表格：纯展示组件——接收数据 + 加载态，「查看详情」通过 emit 上抛 id，路由跳转由页面负责。
// 不持有查询状态（数据由 useFaultList 在 FaultListView 拉取后透传），便于复用与后续测试。
import StatusTag from './StatusTag.vue'
import PriorityTag from './PriorityTag.vue'
import { formatDateTime } from '../utils/format'
import type { Fault } from '../types/fault'

defineProps<{
  faults: Fault[]
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'detail', id: number): void
}>()
</script>

<template>
  <el-table v-loading="loading" :data="faults" style="width: 100%" empty-text="暂无故障记录" stripe border>
    <el-table-column prop="id" label="编号" width="80" />
    <el-table-column label="流水线" min-width="150" show-overflow-tooltip>
      <template #default="{ row }">{{ row.pipeline?.name ?? '—' }}</template>
    </el-table-column>
    <el-table-column prop="location" label="故障位置" min-width="150" show-overflow-tooltip />
    <el-table-column label="发生时间" min-width="170">
      <template #default="{ row }">{{ formatDateTime(row.occurred_at) }}</template>
    </el-table-column>
    <el-table-column prop="symptom" label="故障现象" min-width="220" show-overflow-tooltip />
    <!-- 列序与导出 CSV 口径一致：status 在前、priority 在后（第二阶段新增优先级列） -->
    <el-table-column label="状态" width="100" align="center">
      <template #default="{ row }">
        <StatusTag :status="row.status" />
      </template>
    </el-table-column>
    <el-table-column label="优先级" width="90" align="center">
      <template #default="{ row }">
        <PriorityTag :priority="row.priority" />
      </template>
    </el-table-column>
    <el-table-column label="操作" width="110" align="center" fixed="right">
      <template #default="{ row }">
        <el-button type="primary" link @click="emit('detail', row.id)">查看详情</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

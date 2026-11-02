<script setup lang="ts">
// 故障列表页：筛选（流水线 + 状态 + 优先级）+ 分页表格 + 错误提示。
// 数据流：filters（reactive）→ params（computed，规范化空值）→ useFaultList（TanStack Query，key 随 params 变化自动 refetch）。
// 组件拆分：FaultFilterBar / FaultTable 为受控纯展示组件，本页持有查询状态与路由跳转逻辑。
import { computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'

import FaultFilterBar from '../components/FaultFilterBar.vue'
import FaultTable from '../components/FaultTable.vue'
import { exportFaultsCsv } from '../api/faults'
import { useFaultList } from '../composables/useFaultList'
import type { FaultListParams, FaultPriority, FaultStatus } from '../types/fault'

const router = useRouter()

// 筛选 + 分页状态（size 默认 20，与后端一致；page 从 1 起）
const filters = reactive<{
  pipeline_id?: number
  status?: FaultStatus
  priority?: FaultPriority
  page: number
  size: number
}>({
  pipeline_id: undefined,
  status: undefined,
  priority: undefined,
  page: 1,
  size: 20,
})

// 规范化为空值安全的查询参数：clearable 下拉清空后可能是 '' 或 undefined，统一用 || undefined 收敛，
// 避免把空串发给后端（client 也会跳过空串，这里再收敛一层，保证 params 类型干净）。
const params = computed<FaultListParams>(() => ({
  pipeline_id: filters.pipeline_id || undefined,
  status: filters.status || undefined,
  priority: filters.priority || undefined,
  page: filters.page,
  size: filters.size,
}))

const { data, isFetching, isError, error } = useFaultList(params)

// 筛选条件变化时回到第一页（否则可能停在超出新结果范围的页码）
watch(
  [() => filters.pipeline_id, () => filters.status, () => filters.priority],
  () => {
    filters.page = 1
  }
)

const faults = computed(() => data.value?.items ?? [])
const total = computed(() => data.value?.total ?? 0)

// 后端地址（错误提示里展示，便于排查「服务没起 / 地址不对」）
const apiBase = import.meta.env.VITE_API_BASE_URL

const errorMessage = computed(() => {
  if (!isError.value || !error.value) return ''
  return `加载故障列表失败：${error.value.message}（请确认后端服务已在 ${apiBase} 启动）`
})

function goDetail(id: number) {
  router.push({ name: 'fault-detail', params: { id: String(id) } })
}

// 导出 CSV：携当前筛选条件（不含分页 —— 导出语义是"筛选出的全部行"，需求文档 D2）。
// 取 params.value 而非 filters：params 已把 clearable 清空后的 '' 收敛成 undefined，口径与列表查询一致。
function onExport() {
  const { pipeline_id, status, priority } = params.value
  exportFaultsCsv({ pipeline_id, status, priority })
}
</script>

<template>
  <section class="fault-list">
    <header class="list-header">
      <h2 class="list-title">故障列表</h2>
      <div class="header-actions">
        <el-button @click="onExport">导出 CSV</el-button>
        <el-button type="primary" @click="router.push({ name: 'fault-create' })">登记故障</el-button>
      </div>
    </header>

    <FaultFilterBar
      v-model:pipeline="filters.pipeline_id"
      v-model:status="filters.status"
      v-model:priority="filters.priority"
      class="list-block"
    />

    <el-alert
      v-if="isError"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="list-block"
    />

    <FaultTable :faults="faults" :loading="isFetching" class="list-block" @detail="goDetail" />

    <div class="list-pagination">
      <el-pagination
        v-model:current-page="filters.page"
        v-model:page-size="filters.size"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
      />
    </div>
  </section>
</template>

<style scoped>
.fault-list {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.list-title {
  margin: 0;
  font-size: 20px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.list-block {
  margin-bottom: 16px;
}
.list-pagination {
  display: flex;
  justify-content: flex-end;
}
</style>

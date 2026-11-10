<script setup lang="ts">
// 故障列表页：筛选（流水线 + 状态 + 优先级 + 负责人）+ 分页表格 + 导出 + 错误提示。
// 数据流：filters（reactive）→ params（computed，规范化空值）→ useFaultList（TanStack Query，key 随 params 变化自动 refetch）。
// 组件拆分：FaultFilterBar / FaultTable 为受控纯展示组件，本页持有查询状态与路由跳转逻辑。
// 负责人筛选（第三阶段）：下拉里的「未分派」哨兵值在本页换算成 { unassigned: true }，不直接发后端。
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import FaultFilterBar from '../components/FaultFilterBar.vue'
import FaultTable from '../components/FaultTable.vue'
import { exportFaultsCsv } from '../api/faults'
import { useFaultList } from '../composables/useFaultList'
import { UNASSIGNED_SENTINEL } from '../types/fault'
import type { FaultListParams, FaultPriority, FaultStatus } from '../types/fault'

const router = useRouter()

// 筛选 + 分页状态（size 默认 20，与后端一致；page 从 1 起）
const filters = reactive<{
  pipeline_id?: number
  status?: FaultStatus
  priority?: FaultPriority
  assignee_id?: number
  page: number
  size: number
}>({
  pipeline_id: undefined,
  status: undefined,
  priority: undefined,
  assignee_id: undefined,
  page: 1,
  size: 20,
})

// 规范化为空值安全的查询参数：clearable 下拉清空后可能是 '' 或 undefined，统一用 || undefined 收敛，
// 避免把空串发给后端（client 也会跳过空串，这里再收敛一层，保证 params 类型干净）。
// 哨兵换算：UNASSIGNED_SENTINEL 不是真实用户 id，转成 unassigned=true（两者互斥，后端同传时优先 unassigned）。
const params = computed<FaultListParams>(() => {
  const a = filters.assignee_id || undefined
  return {
    pipeline_id: filters.pipeline_id || undefined,
    status: filters.status || undefined,
    priority: filters.priority || undefined,
    assignee_id: a !== undefined && a !== UNASSIGNED_SENTINEL ? a : undefined,
    unassigned: a === UNASSIGNED_SENTINEL ? true : undefined,
    page: filters.page,
    size: filters.size,
  }
})

const { data, isFetching, isError, error } = useFaultList(params)

// 筛选条件变化时回到第一页（否则可能停在超出新结果范围的页码）
watch(
  [() => filters.pipeline_id, () => filters.status, () => filters.priority, () => filters.assignee_id],
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

// 导出 CSV：携当前筛选（不含分页 —— 导出语义是"筛选出的全部行"，需求文档 D2）。
// 取 params.value 而非 filters：params 已把清空收敛与未分派哨兵换算一次性做完，口径与列表查询一致。
// 第三阶段：导出改 fetch blob（携 Authorization 头），异步失败要给用户反馈，不再是点了即忘的直链。
const exporting = ref(false)
async function onExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    const { pipeline_id, status, priority, assignee_id, unassigned } = params.value
    await exportFaultsCsv({ pipeline_id, status, priority, assignee_id, unassigned })
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <section class="fault-list">
    <header class="list-header">
      <h2 class="list-title">故障列表</h2>
      <div class="header-actions">
        <el-button :loading="exporting" @click="onExport">导出 CSV</el-button>
        <el-button type="primary" @click="router.push({ name: 'fault-create' })">新建故障</el-button>
      </div>
    </header>

    <FaultFilterBar
      v-model:pipeline="filters.pipeline_id"
      v-model:status="filters.status"
      v-model:priority="filters.priority"
      v-model:assignee="filters.assignee_id"
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

    <!-- 表格区吃掉剩余高度（定高容器 .list-table + el-table height=100%）：
         页头/筛选/分页常显，行多时在表格内部滚动、表头固定 -->
    <div class="list-table">
      <FaultTable :faults="faults" :loading="isFetching" @detail="goDetail" />
    </div>

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
  /* 撑满 el-main 可用区（顶栏以下全部空间）：纵向 flex，表格区 flex:1 吸收剩余高度；
     el-main 定高（.app-shell 100vh + flex:1），百分比高度链有效 */
  height: 100%;
  display: flex;
  flex-direction: column;
}
.list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.list-title {
  margin: 0;
  /* 全局字阶 L1：页面标题 18px/600（显式字重，摆脱 h2 浏览器默认 bold） */
  font-size: 18px;
  font-weight: 600;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.list-block {
  margin-bottom: 16px;
}
.list-table {
  flex: 1;
  /* flex 子项内部滚动必备：允许收缩到内容高度以下，否则 min-height 默认 auto 会撑破容器 */
  min-height: 0;
  margin-bottom: 16px;
}
.list-pagination {
  display: flex;
  justify-content: flex-end;
}
</style>

<script setup lang="ts">
// 故障详情页：展示单条故障的全部字段 + 动作面板 + 处理时间线（第三阶段 M6）。
// id 来自路由参数（router props: true，字符串）；转数字后交给 useFaultDetail（其 enabled 守卫非法 id）。
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'

import StatusTag from '../components/StatusTag.vue'
import PriorityTag from '../components/PriorityTag.vue'
import FaultActionPanel from '../components/FaultActionPanel.vue'
import FaultTimelineList from '../components/FaultTimelineList.vue'
// 修改基础信息已并入 FaultActionPanel 的动作对话框，内嵌面板不再挂载（组件文件暂保留）
// import FaultEditPanel from '../components/FaultEditPanel.vue'
import { useFaultDetail } from '../composables/useFaultDetail'
import { formatDateTime } from '../utils/format'

const props = defineProps<{ id: string }>()
const router = useRouter()

// 路由参数是字符串；转数字（非法则为 NaN，useFaultDetail 的 enabled 会拦下不发请求）
const faultId = computed(() => Number(props.id))
const { data: fault, isFetching, isError, error } = useFaultDetail(faultId)

// 非法 ID（如 /faults/abc）：直接提示，不发请求
const invalidId = computed(() => !Number.isFinite(faultId.value) || faultId.value <= 0)

const apiBase = import.meta.env.VITE_API_BASE_URL
const errorMessage = computed(() => {
  if (!isError.value || !error.value) return ''
  return `加载故障详情失败：${error.value.message}（请确认后端服务已在 ${apiBase} 启动）`
})

// 窄屏（≤900px）已塌缩为单列，此时禁用右栏 el-affix：fixed 会盖住左侧内容（CSS 对 affix 无效，需 disabled 属性）
const isCompact = ref(false)
let compactMql: MediaQueryList | undefined
function syncCompact() {
  isCompact.value = window.matchMedia('(max-width: 900px)').matches
}
onMounted(() => {
  compactMql = window.matchMedia('(max-width: 900px)')
  syncCompact()
  compactMql.addEventListener('change', syncCompact)
})
onBeforeUnmount(() => compactMql?.removeEventListener('change', syncCompact))
</script>

<template>
  <section class="fault-detail">
    <!-- 仅「返回列表」按钮吸顶（el-affix 自动探测滚动容器 el-main，offset 为相对视口距离，75 避开全局顶栏） -->
    <header class="detail-header">
      <h2 class="detail-title">故障详情 #{{ props.id }}</h2>
      <el-affix :offset="75">
        <el-button link @click="router.push({ name: 'fault-list' })">
          <el-icon class="el-icon--left"><Back /></el-icon>返回列表
        </el-button>
      </el-affix>
    </header>

    <el-alert v-if="invalidId" title="无效的故障编号" type="warning" show-icon :closable="false" />

    <div v-else-if="isFetching && !fault" class="detail-loading">加载中…</div>

    <el-alert v-else-if="isError" :title="errorMessage" type="error" show-icon :closable="false" />

    <template v-else-if="fault">
      <div class="detail-body">
        <!-- 左栏：基础信息 + 修改基础信息 + 处理时间线 -->
        <div class="detail-main">
          <el-descriptions :column="2" border size="default" class="detail-desc">
            <el-descriptions-item label="编号">{{ fault.id }}</el-descriptions-item>
            <el-descriptions-item label="所属流水线">
              {{ fault.pipeline?.name ?? '—' }}（{{ fault.pipeline?.code ?? '—' }}）
            </el-descriptions-item>
            <el-descriptions-item label="故障位置">{{ fault.location }}</el-descriptions-item>
            <el-descriptions-item label="发生时间">{{ formatDateTime(fault.occurred_at) }}</el-descriptions-item>
            <el-descriptions-item label="故障现象" :span="2">{{ fault.symptom }}</el-descriptions-item>
            <el-descriptions-item label="当前状态">
              <StatusTag :status="fault.status" />
            </el-descriptions-item>
            <!-- 优先级（第二阶段，需求二.1 详情可查看）；顺序与列表/导出口径一致：状态在前、优先级在后 -->
            <el-descriptions-item label="优先级">
              <PriorityTag :priority="fault.priority" />
            </el-descriptions-item>
            <!-- 创建人/负责人（第三阶段，需求六.2）：旧数据为 null → 「历史数据」话术，不显示空白 -->
            <el-descriptions-item label="创建人">
              {{ fault.created_by ? `${fault.created_by.display_name}（${fault.created_by.username}）` : '历史数据/未关联账号' }}
            </el-descriptions-item>
            <el-descriptions-item label="负责人">
              {{ fault.assignee ? `${fault.assignee.display_name}（${fault.assignee.username}）` : '未指派' }}
            </el-descriptions-item>
            <el-descriptions-item label="处理说明" :span="2">{{ fault.handling_note || '—' }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDateTime(fault.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatDateTime(fault.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="完成时间" :span="2">{{ formatDateTime(fault.closed_at) }}</el-descriptions-item>
          </el-descriptions>

          <!-- 修改基础信息入口已移至右栏「处理操作」面板（原内嵌面板，保留备查） -->
          <!-- <FaultEditPanel :fault="fault" /> -->
          <FaultTimelineList :fault-id="faultId" />
        </div>

        <!-- 右栏：处理操作（同样用 el-affix 吸顶；offset 需高于标题条吸顶位置以错开，窄屏禁用） -->
        <el-affix :offset="112" :disabled="isCompact">
          <aside class="detail-side">
            <FaultActionPanel :fault="fault" />
          </aside>
        </el-affix>
      </div>
    </template>
  </section>
</template>

<style scoped>
.fault-detail {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.detail-title {
  margin: 0;
  /* 全局字阶 L1：页面标题 18px/600 */
  font-size: 18px;
  font-weight: 600;
}
.detail-loading {
  padding: 40px;
  color: #909399;
  text-align: center;
}
.detail-desc {
  margin-bottom: 16px;
}
/* 左右分栏：左栏内容自适应，右栏固定宽度吸顶；窄屏自动塌缩为单列 */
.detail-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 350px;
  gap: 24px;
  align-items: start;
}
.detail-main {
  min-width: 0;
}
.detail-side {
  padding: 16px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter, #ebeef5);
  border-radius: 4px;
}
/* 右栏已是独立卡片，去掉动作面板自带的顶部分隔线与上间距，避免重复边框 */
.detail-side :deep(.action-panel) {
  padding-top: 0;
  border-top: 0;
}
@media (max-width: 900px) {
  .detail-body {
    grid-template-columns: 1fr;
  }
}
</style>

<script setup lang="ts">
// 故障详情页：展示单条故障的全部字段 + 动作面板 + 处理时间线（第三阶段 M6）。
// id 来自路由参数（router props: true，字符串）；转数字后交给 useFaultDetail（其 enabled 守卫非法 id）。
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import StatusTag from '../components/StatusTag.vue'
import PriorityTag from '../components/PriorityTag.vue'
import FaultActionPanel from '../components/FaultActionPanel.vue'
import FaultTimelineList from '../components/FaultTimelineList.vue'
import FaultEditPanel from '../components/FaultEditPanel.vue'
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
</script>

<template>
  <section class="fault-detail">
    <header class="detail-header">
      <h2 class="detail-title">故障详情 #{{ props.id }}</h2>
      <el-button link @click="router.push({ name: 'fault-list' })">返回列表</el-button>
    </header>

    <el-alert v-if="invalidId" title="无效的故障编号" type="warning" show-icon :closable="false" />

    <div v-else-if="isFetching && !fault" class="detail-loading">加载中…</div>

    <el-alert v-else-if="isError" :title="errorMessage" type="error" show-icon :closable="false" />

    <template v-else-if="fault">
      <el-descriptions :column="1" border class="detail-desc">
        <el-descriptions-item label="编号">{{ fault.id }}</el-descriptions-item>
        <el-descriptions-item label="所属流水线">
          {{ fault.pipeline?.name ?? '—' }}（{{ fault.pipeline?.code ?? '—' }}）
        </el-descriptions-item>
        <el-descriptions-item label="故障位置">{{ fault.location }}</el-descriptions-item>
        <el-descriptions-item label="发生时间">{{ formatDateTime(fault.occurred_at) }}</el-descriptions-item>
        <el-descriptions-item label="故障现象">{{ fault.symptom }}</el-descriptions-item>
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
        <el-descriptions-item label="处理说明">{{ fault.handling_note || '—' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(fault.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDateTime(fault.updated_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatDateTime(fault.closed_at) }}</el-descriptions-item>
      </el-descriptions>

      <FaultEditPanel :fault="fault" />
      <FaultActionPanel :fault="fault" />
      <FaultTimelineList :fault-id="faultId" />
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
  margin-bottom: 24px;
}
</style>

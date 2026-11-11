<script setup lang="ts">
// 故障处理时间线（第三阶段 M6，需求四.1/六.2）：按时间倒序展示（最新操作在最上），每个动作「谁、何时、做了什么」。
// append-only 展示，无编辑入口——旧记录不可改是业务规则，界面上也不给机会。
//
// 数据来自 useFaultTimeline（queryKey ['fault-timelines', id]）；
// 动作面板提交成功后该 key 失效自动重拉，状态与时间线一致性由后端同事务保证（需求四.2）。
//
// 旧数据口径（需求六.2）：
//   · operator 为空（历史导入或账号已删）→ 显示「历史数据」；
//   · is_imported=true 的记录带「升级导入」标签，说明是二阶段 handling_note 迁移产物，非真实操作。
import { computed } from 'vue'

import { useFaultTimeline } from '../composables/useFaultTimeline'
import { formatDateTime } from '../utils/format'
import { FAULT_STATUS_META } from '../types/fault'
import { TIMELINE_ACTION_LABELS } from '../types/timeline'
import type { TimelineEntry } from '../types/timeline'

// 注意：模板绑定 `:fault-id="faultId"` 会自动解包顶层 ref，props 收到的是普通 number，
// 故这里接 number 再包回 computed 交给 useFaultTimeline（路由参数切换时自动重拉）。
const props = defineProps<{ faultId: number }>()

const { data: entries, isFetching, isError, error } = useFaultTimeline(computed(() => props.faultId))

// 后端按 created_at 正序返回（TL4 接口契约不变），展示层反转成倒序；
// 同秒多条动作反转后 id 大的在前，仍符合“越新越靠上”。
const items = computed<TimelineEntry[]>(() => [...(entries.value ?? [])].reverse())

// 状态值 → 中文标签（未知值兜底原样显示，防后端扩状态时渲染空白）
function statusLabel(value: string | null): string {
  if (!value) return ''
  return FAULT_STATUS_META[value as keyof typeof FAULT_STATUS_META]?.label ?? value
}

// 操作人显示：优先 operator_name（后端已做「当前姓名→快照」回退），空则历史数据话术
function operatorLabel(entry: TimelineEntry): string {
  return entry.operator_name || '历史数据/未关联账号'
}

// 被指派负责人显示：assignee 无姓名快照，账号已删（null）时占位「已注销账号」
function assigneeLabel(name: string | null): string {
  return name || '已注销账号'
}
</script>

<template>
  <div class="timeline-panel">
    <h3 class="panel-title">处理记录</h3>

    <div v-if="isFetching && items.length === 0" class="timeline-state">加载中…</div>
    <el-alert
      v-else-if="isError"
      :title="`处理记录加载失败：${error?.message ?? '未知错误'}`"
      type="warning"
      show-icon
      :closable="false"
    />
    <el-empty v-else-if="items.length === 0" description="暂无处理记录" :image-size="60" />

    <el-timeline v-else>
      <el-timeline-item
        v-for="entry in items"
        :key="entry.id"
        :timestamp="formatDateTime(entry.created_at)"
        placement="top"
      >
        <div class="entry-head">
          <span class="entry-action">{{ TIMELINE_ACTION_LABELS[entry.action] ?? entry.action }}</span>
          <el-tag v-if="entry.is_imported" size="small" type="info" disable-transitions>升级导入</el-tag>
          <span class="entry-operator">{{ operatorLabel(entry) }}</span>
        </div>

        <!-- 状态变化：from → to（指派/进展/优先级等不改状态的动作两端相同或为空，不渲染） -->
        <p v-if="entry.from_status !== entry.to_status" class="entry-flow">
          {{ statusLabel(entry.from_status) }} → {{ statusLabel(entry.to_status) }}
        </p>

        <!-- 指派/改派人员（需求：处理记录显示指派的人员）；assign 只展示新负责人，reassign 展示旧 → 新 -->
        <p v-if="entry.action === 'assign'" class="entry-flow">
          指派给：{{ assigneeLabel(entry.to_assignee_name) }}
        </p>
        <p v-else-if="entry.action === 'reassign'" class="entry-flow">
          改派：{{ assigneeLabel(entry.from_assignee_name) }} → {{ assigneeLabel(entry.to_assignee_name) }}
        </p>

        <p v-if="entry.note" class="entry-note">{{ entry.note }}</p>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<style scoped>
.timeline-panel {
  padding-top: 16px;
  margin-top: 24px;
  border-top: 1px solid var(--el-border-color, #dcdfe6);
}
.panel-title {
  margin: 0 0 16px;
  /* 全局字阶 L2：面板标题 16px，字重补齐 600 */
  font-size: 16px;
  font-weight: 600;
}
.timeline-state {
  padding: 24px;
  color: #909399;
  text-align: center;
}
.entry-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.entry-action {
  font-weight: 600;
}
.entry-operator {
  color: var(--el-text-color-secondary, #909399);
  font-size: 13px;
}
.entry-flow {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-regular, #606266);
}
.entry-note {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-primary, #303133);
  white-space: pre-wrap;
}
</style>

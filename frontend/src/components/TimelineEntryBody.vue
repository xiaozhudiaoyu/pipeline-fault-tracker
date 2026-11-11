<script setup lang="ts">
// 时间线单条记录的正文（从 FaultTimelineList 抽出，纵向 el-timeline 与横向排布共用同一份渲染）。
// 抽出理由：横/纵两种排布若各自复制一遍正文，字段口径（动作文案、状态流转、指派人员、说明）
// 就要在两处同步维护，极易漏改；这里只放「一条记录长什么样」，排布与轴线由父组件负责。
//
// 旧数据口径（需求六.2，随正文一并搬过来）：
//   · operator 为空（历史导入或账号已删）→ 显示「历史数据」；
//   · 被指派账号已删（无姓名快照）→ 占位「已注销账号」。
import { FAULT_STATUS_META } from '../types/fault'
import { TIMELINE_ACTION_LABELS } from '../types/timeline'
import type { TimelineEntry } from '../types/timeline'

defineProps<{ entry: TimelineEntry }>()

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
  <div class="entry-body">
    <div class="entry-head">
      <span class="entry-action">{{ TIMELINE_ACTION_LABELS[entry.action] ?? entry.action }}</span>
      <el-tag v-if="entry.is_imported" size="small" type="info" disable-transitions>升级导入</el-tag>
      <span v-else class="entry-operator">{{ operatorLabel(entry) }}</span>
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
  </div>
</template>

<style scoped>
/* 以下样式与类名自 FaultTimelineList 原样搬入（scoped 样式不跨组件生效，正文在哪渲染样式就跟到哪） */
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

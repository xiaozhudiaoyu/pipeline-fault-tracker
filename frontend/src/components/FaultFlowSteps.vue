<script setup lang="ts">
// 故障处理进度简易视图（第四阶段候选的"轻量版"，不引入 bpmn-js，见 process/_p4_bpmn_flow_viewer_memo.md 的降级实现）。
// 四态闭环（README 状态机）映射为五段步骤条：报修登记 → 待指派 → 处理中 → 待确认 → 已完成。
//
// 着色口径：
//   · 当前环节由 fault.status 决定（pending→待指派 / processing→处理中 /
//     awaiting_confirmation→待确认 / done→已完成），之前环节记已完成，之后灰置；
//   · 环节色板与 StatusTag 的 el-tag type 同源（FAULT_STATUS_META.tag）：
//     待处理=info 灰 / 处理中=warning 橙 / 待确认=primary 蓝 / 已完成=success 绿；
//   · 时间线里存在 return（退回处理）记录 → 处理中环节标红并计数（备忘方案的 highlight-back 简化版）；
//   · 数据复用 useFaultTimeline（queryKey ['fault-timelines', id]，与处理记录列表同缓存），
//     动作提交成功后该 key 失效，本组件随详情页一起自动重刷。
import { computed } from 'vue'
import { CircleCloseFilled, SuccessFilled } from '@element-plus/icons-vue'

import { useFaultTimeline } from '../composables/useFaultTimeline'
import { FAULT_STATUS_META } from '../types/fault'
import type { Fault, FaultStatus } from '../types/fault'

const props = defineProps<{ fault: Fault }>()

// 五段环节，与后端 FaultStatus 四态一一对应（首段"报修登记"为流程起点，恒已完成——
// 故障必然先登记才存在，时间线首条即 create 记录）
const STEPS: Array<{ label: string; status: FaultStatus | null }> = [
  { label: '报修登记', status: null },
  { label: FAULT_STATUS_META.pending.label, status: 'pending' },
  { label: FAULT_STATUS_META.processing.label, status: 'processing' },
  { label: FAULT_STATUS_META.awaiting_confirmation.label, status: 'awaiting_confirmation' },
  { label: FAULT_STATUS_META.done.label, status: 'done' },
]

// el-tag type → 本组件环节色类名（与 FAULT_STATUS_META.tag 同源，颜色不另起新色板）
const STATUS_CLASS: Record<'info' | 'warning' | 'primary' | 'success', string> = {
  info: 's-info',
  warning: 's-warning',
  primary: 's-primary',
  success: 's-success',
}

// 非法 id 守卫与 useFaultDetail 一致（本组件仅在详情加载成功后挂载，正常都会发请求）
const faultId = computed(() => props.fault.id)
const { data: entries } = useFaultTimeline(faultId)

// 当前环节下标：status → STEPS 位置（未知状态兜底回第一段，不渲染空图）
const currentIndex = computed(() => {
  const idx = STEPS.findIndex((s) => s.status === props.fault.status)
  return idx === -1 ? 0 : idx
})

// 退回次数（需求四闭环里的 return 动作；历史导入记录 is_imported 不含 return，无需排除）
const returnCount = computed(
  () => (entries.value ?? []).filter((e) => e.action === 'return').length,
)

// 处理中环节是否处于"退回待重处理"状态：有退回记录且当前还停在处理中
const hasReturned = computed(() => returnCount.value > 0)

function stepClass(index: number): string {
  if (index === 1 && hasReturned.value && currentIndex.value === 1) return 'is-back'
  if (index < currentIndex.value) return 'is-done'
  if (index === currentIndex.value) return index === STEPS.length - 1 ? 'is-done' : 'is-current'
  return 'is-todo'
}

// 当前环节的颜色类：按该环节自身状态对应的 el-tag type 取色（与 StatusTag 一致）
function stepStatusClass(index: number): string {
  const status = STEPS[index].status
  if (!status) return ''
  return STATUS_CLASS[FAULT_STATUS_META[status].tag]
}

// 连线颜色跟随其左侧环节：已完成/当前段之后连线点亮
function lineClass(index: number): string {
  return index < currentIndex.value ? 'is-done' : ''
}
</script>

<template>
  <div class="flow-steps">
    <!-- <h3 class="panel-title">处理进度</h3> -->

    <div class="steps">
      <template v-for="(step, i) in STEPS" :key="step.label">
        <div class="step" :class="[stepClass(i), stepClass(i) === 'is-current' ? stepStatusClass(i) : '']">
          <span class="dot">
            <!-- UI 图标（项目惯例：插槽式 <el-icon>）：已完成绿勾 / 退回红叉，灰置与当前环节无图标 -->
            <el-icon v-if="stepClass(i) === 'is-done'" :size="14"><SuccessFilled /></el-icon>
            <el-icon v-else-if="stepClass(i) === 'is-back'" :size="14"><CircleCloseFilled /></el-icon>
          </span>
          <span class="label">{{ step.label }}</span>
          <span v-if="i === 1 && hasReturned" class="back-tag">已退回 {{ returnCount }} 次</span>
        </div>
        <span v-if="i < STEPS.length - 1" class="line" :class="lineClass(i)"></span>
      </template>
    </div>

    <!-- <p class="flow-hint">
      当前环节：<strong>{{ STEPS[currentIndex].label }}</strong>
      <template v-if="hasReturned">（处理环节存在退回记录）</template>
    </p> -->
  </div>
</template>

<style scoped>
/* 位于 FaultActionPanel「处理操作」标题下方：上方间距由标题 margin 控制，本块只留底部分隔线 */
.flow-steps {
  margin-bottom: 18px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color, #dcdfe6);
}
.panel-title {
  margin: 0 0 16px;
  /* 全局字阶 L2：面板标题 16px，字重补齐 600 */
  font-size: 16px;
  font-weight: 600;
}
.steps {
  display: flex;
  align-items: flex-start;
  /* 连线与圆圈间隙（用户要求贴紧一些，仅此处收窄，其余不动） */
  gap: 2px;
}
.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 64px;
}
/* 连线占余量均分，窄屏自动压缩 */
.line {
  flex: 1;
  height: 1px;
  margin-top: 9px;
  background: var(--el-border-color, #dcdfe6);
}
.line.is-done {
  background: var(--el-color-success, #67c23a);
}
.dot {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--el-border-color, #dcdfe6);
  background: #fff;
  color: #fff;
  line-height: 1;
  .el-icon {
    font-size: 20px !important;
  }
}
.label {
  color: var(--el-text-color-secondary, #909399);
  white-space: nowrap;
}
.back-tag {
  font-size: 13px;
  color: var(--el-color-danger, #f56c6c);
  white-space: nowrap;
}
/* 已完成：绿底白勾（SuccessFilled 图标继承 dot 前景色） */
.step.is-done .dot {
  border-color: var(--el-color-success, #67c23a);
  background: var(--el-color-success, #67c23a);
  color: #fff;
}
.step.is-done .label {
  color: var(--el-text-color-primary, #303133);
}
/* 进行中的当前环节：外圈脉冲动效（done 走 is-done 分支、未开始走 is-todo，均不动画；
   退回态 is-back 同属未完成的活动环节，一并加动效）；脉冲环颜色取 --pulse-color，
   由下方 s-* / is-back 规则各自定义（不借 currentcolor，避免干扰图标前景色） */
.step.is-current .dot::after,
.step.is-back .dot::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  border: 2px solid var(--pulse-color, transparent);
  animation: flow-pulse 1.6s ease-out infinite;
}
@keyframes flow-pulse {
  0% {
    transform: scale(1);
    opacity: 0.7;
  }
  70%,
  100% {
    transform: scale(1.65);
    opacity: 0;
  }
}
/* 系统级“减少动态效果”偏好下停掉脉冲（仅保留静态光环） */
@media (prefers-reduced-motion: reduce) {
  .step.is-current .dot::after,
  .step.is-back .dot::after {
    animation: none;
  }
}
/* 当前环节：描边圈 + 同色光环（初版样式，仅颜色跟 el-tag type 走；s-* 类由 stepStatusClass 挂上）。
   光环色先 rgb() 同色硬编码兜底、再 color-mix 降透明度覆盖（旧浏览器不认识 color-mix 保留前一条） */
.step.is-current.s-info .dot {
  border-color: var(--el-color-info, #909399);
  --pulse-color: var(--el-color-info, #909399);
  box-shadow: 0 0 0 3px rgb(144 147 153 / 40%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-info, #909399) 15%, transparent);
}
.step.is-current.s-warning .dot {
  border-color: var(--el-color-warning, #e6a23c);
  --pulse-color: var(--el-color-warning, #e6a23c);
  box-shadow: 0 0 0 3px rgb(230 162 60 / 40%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-warning, #e6a23c) 15%, transparent);
}
.step.is-current.s-primary .dot {
  border-color: var(--el-color-primary, #409eff);
  --pulse-color: var(--el-color-primary, #409eff);
  box-shadow: 0 0 0 3px rgb(64 158 255 / 40%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-primary, #409eff) 15%, transparent);
}
.step.is-current.s-success .dot {
  border-color: var(--el-color-success, #67c23a);
  --pulse-color: var(--el-color-success, #67c23a);
  box-shadow: 0 0 0 3px rgb(103 194 58 / 40%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-success, #67c23a) 15%, transparent);
}
.step.is-current .label {
  font-weight: 600;
}
.step.is-current.s-info .label {
  color: var(--el-color-info, #909399);
}
.step.is-current.s-warning .label {
  color: var(--el-color-warning, #e6a23c);
}
.step.is-current.s-primary .label {
  color: var(--el-color-primary, #409eff);
}
.step.is-current.s-success .label {
  color: var(--el-color-success, #67c23a);
}
/* 退回重处理：红底白叉（danger 色，与动作面板「退回处理」按钮同为警示口径） */
.step.is-back .dot {
  border-color: var(--el-color-danger, #f56c6c);
  background: var(--el-color-danger, #f56c6c);
  /* color 给白叉用，脉冲环单独走 --pulse-color */
  color: #fff;
  --pulse-color: var(--el-color-danger, #f56c6c);
}
.step.is-back .label {
  color: var(--el-color-danger, #f56c6c);
  font-weight: 600;
}
.flow-hint {
  margin: 12px 0 0;
  color: var(--el-text-color-regular, #606266);
}
@media (max-width: 900px) {
  .step {
    min-width: 52px;
  }
}
</style>

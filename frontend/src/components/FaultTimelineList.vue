<script setup lang="ts">
// 故障处理时间线（第三阶段 M6，需求四.1/六.2）：按时间倒序展示（最新操作在最上），每个动作「谁、何时、做了什么」。
// append-only 展示，无编辑入口——旧记录不可改是业务规则，界面上也不给机会。
//
// 数据来自 useFaultTimeline（queryKey ['fault-timelines', id]）；
// 动作面板提交成功后该 key 失效自动重拉，状态与时间线一致性由后端同事务保证（需求四.2）。
//
// 旧数据口径（需求六.2）：
//   · operator 为空（历史导入或账号已删）→ 显示「历史数据」；
//   · is_imported=true 的记录带「升级导入」标签，说明是旧库遗留、非当下真实操作。
//   · 旧库升级来的故障（P3 前登记）没有任何时间线；此处**纯展示层合成**补记录（见 synthEntries）：
//     缺真实 create → 补一条「登记」（适用任何状态）；done 且缺真实 submit → 再补一条带
//     handling_note 的「提交处理结果」。合成不入库：CSV 导出、直接调 /timelines 接口仍看不到它。
//
// 横/纵排布切换：el-timeline 只支持纵向，横向另用自定义 flex 排布；
// 两种排布共用 TimelineEntryBody 渲染条目正文，字段口径只维护一份。
// 方向状态由父视图持有（v-model:orientation，沿用 FaultFilterBar 的 defineModel 写法）：
// 横向记录会向右逃逸到右栏下方，而 el-affix 浮起后默认 z-index=100 会盖住它们，
// 需父视图拿同一个值同时禁用右栏吸顶。
// 开关已持久化（用户后来改的主意，不再是局部状态）：读写与存储都在父视图（utils/prefs），本组件只管读写 model。
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import TimelineEntryBody from './TimelineEntryBody.vue'
import { useFaultTimeline } from '../composables/useFaultTimeline'
import { formatDateTime } from '../utils/format'
import { DEFAULT_ORIENTATION } from '../utils/prefs'
import type { Fault } from '../types/fault'
import type { TimelineAction, TimelineEntry, TimelineOrientation } from '../types/timeline'

// 注意：模板绑定 `:fault-id="faultId"` 会自动解包顶层 ref，props 收到的是普通 number，
// 故这里接 number 再包回 computed 交给 useFaultTimeline（路由参数切换时自动重拉）。
// fault：详情数据，仅用于旧 done 记录的展示层合成（父视图已持有，不额外发请求）。
const props = defineProps<{ faultId: number; fault?: Fault | null }>()

const { data: entries, isFetching, isError, error } = useFaultTimeline(computed(() => props.faultId))

// 历史遗留数据的展示层合成（需求六.3）：旧库升级来的故障（P3 前登记）没有任何时间线记录，
// 而它确实发生过。合成不入库，只为让「处理记录」不空、并保留真实字段可见：
//   · 登记记录：只要真实时间线里没有 create 就补一条（P3 后新建的必有 create，不命中）——
//     任何状态的遗留数据都有最早那条「登记」，且后续真实动作产生的记录不会让它消失；
//   · 结案说明：仅 done 且无真实 submit 时，把 handling_note 呈现为一条「提交处理结果」，
//     created_at 取 closed_at（真实完成时刻，缺失回退 updated_at/created_at）。
// operator 置 null → 正文自动兑为「历史数据/未关联账号」；from/to_status 置 null 不渲染流转（不编造状态变化）。
// 关键：判据用「缺该动作」而非「时间线为空」——遗留数据被接手后 timeline 会长出真实记录，
// 用空判定会让合成的登记凭空消失、时间线看起来从一半开始；按动作缺失判定则登记稳定保留、真实记录依次接续。
const hasRealAction = (action: TimelineAction): boolean =>
  (entries.value ?? []).some((e) => e.action === action)

const synthEntries = computed<TimelineEntry[]>(() => {
  const f = props.fault
  // 时间线尚未加载完（entries 为 undefined）不合成，避免加载中先闪一条再消失。
  if (!f || entries.value === undefined) return []
  // 负数 id 哨兵，与真实时间线自增正 id 不撞 key；两条合成用不同个位区分。
  const shell = (
    id: number,
    action: TimelineAction,
    createdAt: string,
    note: string | null,
  ): TimelineEntry => ({
    id,
    fault_id: f.id,
    action,
    operator_id: null,
    operator_name: null,
    from_status: null,
    to_status: null,
    from_assignee_id: null,
    to_assignee_id: null,
    from_assignee_name: null,
    to_assignee_name: null,
    note,
    is_imported: true,
    created_at: createdAt,
    attachments: [], // 合成记录不挂图（真实附图只属于真实时间线行）
  })
  const list: TimelineEntry[] = []
  if (!hasRealAction('create')) list.push(shell(-f.id * 10 - 1, 'create', f.created_at, null))
  if (f.status === 'done' && f.handling_note && !hasRealAction('submit')) {
    list.push(shell(-f.id * 10 - 2, 'submit', f.closed_at ?? f.updated_at ?? f.created_at, f.handling_note))
  }
  return list
})

// 排布方向：默认值与持久化初值统一出自 utils/prefs（当前默认横向）。
// 开关直接 v-model 绑这个 model，子组件局部渲染与 is-horizontal 类均无需再包一层。
// default 只在父视图漏绑 v-model 时兜底，取同一个常量避免两处各写一套。
// 上移到 items 之前：items 的顺序判定依赖本值（computed 依赖须先声明）。
const orientation = defineModel<TimelineOrientation>('orientation', { default: DEFAULT_ORIENTATION })

// 后端按 created_at 正序返回（TL4 接口契约不变）。合成记录按事件真实时间归位：登记最早
// 排最前；done 的结案说明排最后（done 无真实记录，与合成相接无冲突），再接真实记录，
// 得到「按时间正序」的基线，再由排布方向决定是否倒序：
//   · 纵向：倒序展示，最新在最上；
//   · 横向：正序展示，最新在最右（用户要求横向不倒序）。
const items = computed<TimelineEntry[]>(() => {
  const real = entries.value ?? []
  const chron = [...synthEntries.value, ...real]
  return orientation.value === 'vertical' ? chron.reverse() : chron
})

// 横向定位到最新：最新记录排在最右，而容器默认停在最左 → 需把 scrollLeft 拉到最右。
// 触发时机：① 方向切到横向；② 数据变化（新记录到达/切换故障）且当前横向；③ 首次挂载（默认横向 + 命中缓存）。
const hScrollRef = ref<HTMLElement | null>(null)
function scrollHorizontalToEnd() {
  const el = hScrollRef.value
  if (el) el.scrollTo({ left: el.scrollWidth, behavior: 'smooth' })
}
watch(
  () => [orientation.value, items.value.length],
  async () => {
    if (orientation.value !== 'horizontal') return
    // 等横向容器渲染并布局完成后再取 scrollWidth，否则测不到真实宽度
    await nextTick()
    scrollHorizontalToEnd()
  },
)
onMounted(async () => {
  if (orientation.value !== 'horizontal') return
  await nextTick()
  scrollHorizontalToEnd()
})
</script>

<template>
  <div class="timeline-panel" :class="{ 'is-horizontal': orientation === 'horizontal' }">
    <div class="panel-head">
      <h3 class="panel-title">处理记录</h3>
      <!-- 排布方向开关（不持久）；本机 element-plus 2.5.6 的 el-radio-button 只有 label prop
           作选中值（value prop 自 2.6 才引入，已核源码），与项目内三处 el-radio 写法一致 -->
      <el-radio-group v-model="orientation" size="small">
        <el-radio-button label="vertical">纵向</el-radio-button>
        <el-radio-button label="horizontal">横向</el-radio-button>
      </el-radio-group>
    </div>

    <div v-if="isFetching && items.length === 0" class="timeline-state">加载中…</div>
    <el-alert
      v-else-if="isError"
      :title="`处理记录加载失败：${error?.message ?? '未知错误'}`"
      type="warning"
      show-icon
      :closable="false"
    />
    <el-empty v-else-if="items.length === 0" description="暂无处理记录" :image-size="60" />

    <!-- 纵向：保持 el-timeline 原生渲染（轴线/节点/时间戳由组件负责） -->
    <el-timeline v-else-if="orientation === 'vertical'">
      <el-timeline-item
        v-for="entry in items"
        :key="entry.id"
        :timestamp="formatDateTime(entry.created_at)"
        placement="top"
        type="primary"
        hollow
      >
        <TimelineEntryBody :entry="entry" />
      </el-timeline-item>
    </el-timeline>

    <!-- 横向：自定义 flex 横排 + 横向滚动；每条一个固定宽列，顶部自己画轴线（el-timeline 无横向模式）。
         滚动条悬停显隐样式已全局化为工具类 .scrollbar-hover-show（见 styles/main.css，方案 A） -->
    <div v-else ref="hScrollRef" class="timeline-horizontal scrollbar-hover-show">
      <div v-for="entry in items" :key="entry.id" class="h-entry">
        <div class="h-axis">
          <span class="h-dot"></span>
          <span class="h-line"></span>
        </div>
        <p class="h-time">{{ formatDateTime(entry.created_at) }}</p>
        <TimelineEntryBody :entry="entry" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-panel {
  padding-top: 16px;
  margin-top: 24px;
  border-top: 1px solid var(--el-border-color, #dcdfe6);
}
/* 横向模式：向右逃逸「右栏宽度 + 栏间距」（--side-bleed 由 FaultDetailView 声明，
   窄屏单列时为 0），占满详情页容器宽度；纵向模式不命中此规则，渲染路径一行不变 */
.timeline-panel.is-horizontal {
  margin-right: calc(-1 * var(--side-bleed, 0px));
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 12px;
}
.panel-title {
  margin: 0;
  /* 全局字阶 L2：面板标题 16px，字重补齐 600 */
  font-size: 16px;
  font-weight: 600;
}
.timeline-state {
  padding: 24px;
  color: #909399;
  text-align: center;
}
/* 横向排布：条目不等宽会被长说明拉开，定宽 240px + 横向滚动；
   轴线观感对齐 el-timeline（白底蓝边圆点 + 灰色尾线，末条不画尾线） */
.timeline-horizontal {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  overflow-x: auto;
  padding-bottom: 8px;
  /* 滚动条双轨规则（webkit ::-webkit-scrollbar 系列 + Firefox scrollbar-width/scrollbar-color，含 hover 显隐）
     已整段搬至全局工具类 .scrollbar-hover-show（styles/main.css），本容器模板上挂该类名 */
}
.h-entry {
  flex: 0 0 240px;
}
.h-axis {
  display: flex;
  align-items: center;
  gap: 6px;
}
.h-dot {
  flex: none;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--el-color-primary, #409eff);
  background: #fff;
  box-sizing: border-box;
}
.h-line {
  flex: 1;
  height: 2px;
  background: var(--el-border-color, #dcdfe6);
}
.h-entry:last-child .h-line {
  display: none;
}
.h-time {
  margin: 6px 0 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #909399);
}
</style>

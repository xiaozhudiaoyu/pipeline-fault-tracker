<script setup lang="ts">
// 故障详情页：展示单条故障的全部字段 + 动作面板 + 处理时间线（第三阶段 M6）。
// id 来自路由参数（router props: true，字符串）；转数字后交给 useFaultDetail（其 enabled 守卫非法 id）。
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Back } from '@element-plus/icons-vue'

import StatusTag from '../components/StatusTag.vue'
import PriorityTag from '../components/PriorityTag.vue'
import FaultActionPanel from '../components/FaultActionPanel.vue'
import FaultTimelineList from '../components/FaultTimelineList.vue'
import FaultAttachmentGallery from '../components/FaultAttachmentGallery.vue'
// 修改故障信息已并入 FaultActionPanel 的动作对话框，内嵌面板不再挂载（组件文件暂保留）
// import FaultEditPanel from '../components/FaultEditPanel.vue'
import { useFaultDetail } from '../composables/useFaultDetail'
import { formatDateTime } from '../utils/format'
import { getTimelineOrientation, setTimelineOrientation } from '../utils/prefs'
import type { TimelineOrientation } from '../types/timeline'

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

// 处理记录排布方向（由本视图持有，子组件 v-model:orientation 读写）：
// 横向时记录会向右逃逸到右栏下方，而 el-affix 浮起后默认 z-index=100 会盖住它们，
// 所以横向一并关掉右栏吸顶（与窄屏 isCompact 走同一出口 affixOff）。
// 已改为持久（用户决定，原「不持久」作废）：初值从 localStorage 读、切换即写回（见 utils/prefs），
// 跳不同故障与刷新都保持上次方向。无存储值时的默认取 prefs.ts 的 DEFAULT_ORIENTATION（现为横向），
// 默认值只在那一处定义，子组件 defineModel 的兜底也引用同一个常量。
const timelineOrientation = ref<TimelineOrientation>(getTimelineOrientation())
watch(timelineOrientation, (value) => setTimelineOrientation(value))

// 窄屏（≤900px）已塌缩为单列，此时也要关掉右栏吸顶：fixed 会盖住左侧内容。
// 两者统一靠下面的 affixOff 标记类生效（:disabled 在 2.5.6 不存在，旧写法一直没起作用）
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

// 右栏是否取消吸顶。注意：本机 element-plus 2.5.6 的 ElAffix 没有 disabled prop
//（已核源码 affix.mjs：props 仅 zIndex / target / offset / position，affix2.mjs 的 update()
// 也无 disabled 分支），传 :disabled 只会当无效属性落到根 div 上、吸顶照跑（旧的窄屏禁用
// 其实一直没生效）。真能关掉的做法：挂标记类 + 下方 CSS 把内部 .el-affix--fixed 改成 static。
const affixOff = computed(() => isCompact.value || timelineOrientation.value === 'horizontal')
</script>

<template>
  <section class="fault-detail">
    <!-- 仅「返回列表」按钮吸顶（el-affix 自动探测滚动容器 el-main，offset 为相对视口距离，75 避开全局顶栏） -->
    <header class="detail-header">
      <h2 class="detail-title">故障详情 #{{ props.id }}</h2>
      <el-affix :offset="75" :class="{ 'is-affix-off': affixOff }">
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
        <!-- 左栏：基础信息 + 修改故障信息 + 处理时间线 -->
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

          <!-- 现场图片（第四阶段）：有附件才渲染，无图整块隐藏。删除权限由组件内部镜像后端判定 -->
          <FaultAttachmentGallery :fault="fault" />

          <!-- 修改故障信息入口已移至右栏「处理操作」面板（原内嵌面板，保留备查） -->
          <!-- <FaultEditPanel :fault="fault" /> -->
          <!-- 处理进度已搬入右栏顶部（处理操作上方），左栏只留处理记录 -->
          <FaultTimelineList v-model:orientation="timelineOrientation" :fault-id="faultId" :fault="fault" />
        </div>

        <!-- 右栏：处理操作（el-affix 吸顶；offset 需高于标题条吸顶位置以错开）。
             窄屏或处理记录切横向时挂 is-affix-off 关掉吸顶，避开 fixed 面板遮挡逃逸出来的记录
             （不能用 :disabled，2.5.6 无此 prop，详见上方 affixOff 注释） -->
        <el-affix :offset="112" :class="{ 'is-affix-off': affixOff }">
          <aside class="detail-side">
            <!-- 处理进度步骤条已内置于 FaultActionPanel 标题下方，此处不再单独挂载 -->
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
/* 左右分栏：左栏内容自适应，右栏固定宽度吸顶；窄屏自动塌缩为单列。
   右栏宽度与栏间距声明为变量：横向排布的处理记录靠 --side-bleed 向右逃逸占满容器宽度，
   两处必须同源，改右栏宽度时不必记着同步子组件里的数字 */
.detail-body {
  --side-width: 500px;
  --side-gap: 24px;
  --side-bleed: calc(var(--side-width) + var(--side-gap));
  display: grid;
  grid-template-columns: minmax(0, 1fr) var(--side-width);
  gap: var(--side-gap);
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
/* 关掉吸顶：el-affix 浮起时会给内层挂 .el-affix--fixed（源码 ns.m('fixed')）并写 position: fixed，
   这里按回 static。特异度 3 类 + 1 属性高于 theme-chalk 的单类，无需 !important；
   内联的 top / zIndex 在 static 下不生效，rootStyle 占位高度等于内容高度，不会留空洞 */
.el-affix.is-affix-off :deep(.el-affix--fixed) {
  position: static;
}
@media (max-width: 900px) {
  .detail-body {
    grid-template-columns: 1fr;
    /* 单列布局右侧已无栏位，逃逸量归零，否则横向记录会溢出白卡片 */
    --side-bleed: 0px;
  }
}
</style>

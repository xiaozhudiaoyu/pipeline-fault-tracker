<script setup lang="ts">
// 状态标签：把 FaultStatus 映射为带颜色的 el-tag + 中文文案。
// 映射表集中在 types/fault.ts 的 FAULT_STATUS_META，列表页 / 详情页 / 状态推进面板共用，避免各处重复写。
import { computed } from 'vue'

import { FAULT_STATUS_META } from '../types/fault'
import type { FaultStatus } from '../types/fault'

const props = defineProps<{ status: FaultStatus }>()

// 未知状态兜底（理论上后端只返回三种，这里防御脏数据导致读取 undefined 报错）
const meta = computed(() => FAULT_STATUS_META[props.status] ?? { label: props.status, tag: 'info' as const })
</script>

<template>
  <el-tag :type="meta.tag" disable-transitions>{{ meta.label }}</el-tag>
</template>

<script setup lang="ts">
// 优先级标签：把 FaultPriority 映射为带颜色的 el-tag + 中文文案（同 StatusTag 手法）。
// 映射表集中在 types/fault.ts 的 FAULT_PRIORITY_META，目前仅列表页使用，仍走同一份元数据避免散落。
import { computed } from 'vue'

import { FAULT_PRIORITY_META } from '../types/fault'
import type { FaultPriority } from '../types/fault'

const props = defineProps<{ priority: FaultPriority }>()

// 未知取值兜底（理论上后端只返回两种，防御脏数据导致读取 undefined 报错）
const meta = computed(() => FAULT_PRIORITY_META[props.priority] ?? { label: props.priority, tag: 'info' as const })
</script>

<template>
  <el-tag :type="meta.tag" disable-transitions>{{ meta.label }}</el-tag>
</template>

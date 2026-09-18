<script setup lang="ts">
// 故障详情页（脚手架占位）。
// 路由 /faults/:id 通过 props: true 注入 id（字符串）。
// t6「业务页」接入后实现：展示全部字段 + 状态推进面板（按当前状态动态启用按钮，done 全禁用）。
defineProps<{ id: string }>()
</script>

<template>
  <section class="placeholder">
    <h2 class="placeholder-title">故障详情 #{{ id }}</h2>
    <p class="placeholder-hint">
      脚手架占位页 —— 详情字段与状态推进将在业务页阶段实现。
    </p>
  </section>
</template>

<style scoped>
.placeholder {
  padding: 24px;
  background: #fff;
  border-radius: 8px;
}
.placeholder-title {
  margin: 0 0 12px;
  font-size: 20px;
}
.placeholder-hint {
  margin: 0;
  color: #909399;
}
</style>

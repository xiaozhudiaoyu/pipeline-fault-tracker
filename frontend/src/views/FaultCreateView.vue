<script setup lang="ts">
// 故障登记页（脚手架占位）。
// t6「业务页」接入后实现：Zod 前端校验（流水线必选 / location≥2字 / occurred_at 有效 / symptom≥5字）、
// 提交防重（按钮 :loading）、成功后跳详情或列表。
</script>

<template>
  <section class="placeholder">
    <h2 class="placeholder-title">登记故障</h2>
    <p class="placeholder-hint">
      脚手架占位页 —— 表单与校验将在业务页阶段实现。
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

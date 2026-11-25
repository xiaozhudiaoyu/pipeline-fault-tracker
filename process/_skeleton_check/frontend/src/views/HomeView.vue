<script setup lang="ts">
// 占位首页：演示「前端 → 后端」联调链路——调用 /api/health 显示后端连通状态。
// 业务接入后：删除本页替换为真实页面（并同步更新 router/index.ts 与 App.vue 导航）。
import { ref } from 'vue'

import { request, toUserMessage } from '../api/client'

const backendStatus = ref<'checking' | 'ok' | 'error'>('checking')
const errorMessage = ref('')

async function checkHealth() {
  backendStatus.value = 'checking'
  errorMessage.value = ''
  try {
    await request<{ status: string }>('/api/health')
    backendStatus.value = 'ok'
  } catch (err) {
    backendStatus.value = 'error'
    errorMessage.value = toUserMessage(err)
  }
}

checkHealth()
</script>

<template>
  <el-card>
    <el-page-header content="首页" class="page-header" />
    <p class="hint">技术框架已就绪。这是占位首页，业务页面从此处开始生长。</p>
    <el-space wrap>
      <el-button type="primary" :loading="backendStatus === 'checking'" @click="checkHealth">
        检查后端连通性
      </el-button>
      <el-tag v-if="backendStatus === 'ok'" type="success">后端已连通</el-tag>
      <el-tag v-else-if="backendStatus === 'error'" type="danger">后端不可达</el-tag>
    </el-space>
    <p v-if="backendStatus === 'error'" class="error-text">{{ errorMessage }}</p>
  </el-card>
</template>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.hint {
  color: var(--el-text-color-secondary, #909399);
}
.error-text {
  color: var(--el-color-danger, #f56c6c);
}
</style>

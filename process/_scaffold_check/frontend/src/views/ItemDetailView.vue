<script setup lang="ts">
// 详情页：加载单条记录并展示全部字段；提供编辑入口与返回。
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useItemDetail } from '../composables/useItemDetail'
import { toUserMessage } from '../composables/useItemMutations'
import { ITEM_STATUS_META } from '../types/item'
import { formatDateTime } from '../utils/format'

const props = defineProps<{ id: string }>()
const router = useRouter()

const itemId = computed(() => Number(props.id))
const query = useItemDetail(itemId)

const item = computed(() => query.data.value)
const isLoading = computed(() => query.isLoading.value)
const isError = computed(() => query.isError.value)
const errorMessage = computed(() => (query.error.value ? toUserMessage(query.error.value) : '加载失败'))
</script>

<template>
  <el-card>
    <el-page-header content="详情" class="page-header" @back="router.push('/')" />

    <div v-loading="isLoading">
      <el-alert v-if="isError" type="error" :closable="false" class="error-alert" :title="errorMessage" />

      <el-descriptions v-if="item" :column="1" border>
        <el-descriptions-item label="编号">{{ item.id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ item.name }}</el-descriptions-item>
        <el-descriptions-item label="描述">{{ item.description ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="ITEM_STATUS_META[item.status].tag">{{ ITEM_STATUS_META[item.status].label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(item.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDateTime(item.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <div v-if="item" class="actions">
        <el-button type="primary" @click="router.push(`/items/${item.id}/edit`)">编辑</el-button>
        <el-button @click="router.push('/')">返回列表</el-button>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.page-header {
  margin-bottom: 16px;
}
.error-alert {
  margin-bottom: 16px;
}
.actions {
  margin-top: 16px;
}
</style>

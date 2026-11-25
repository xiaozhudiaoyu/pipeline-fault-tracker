<script setup lang="ts">
// 列表页：状态筛选 + 分页表格 + 行点击进详情 + 删除。
import { computed, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import { useItemList } from '../composables/useItemList'
import { useItemMutations } from '../composables/useItemMutations'
import { ITEM_STATUS_META, ITEM_STATUS_OPTIONS } from '../types/item'
import type { Item, ItemStatus } from '../types/item'
import { formatDateTime } from '../utils/format'

const router = useRouter()

// ---- 筛选与分页状态 ----
const filterStatus = ref<ItemStatus | undefined>(undefined)
const page = ref(1)
const size = 10

// params 为 computed：vue-query 会自动追踪其变化（筛选/翻页即重新请求）。
const params = computed(() => ({
  status: filterStatus.value,
  page: page.value,
  size,
}))

const query = useItemList(params)
const list = computed(() => query.data.value?.items ?? [])
const total = computed(() => query.data.value?.total ?? 0)
const isLoading = computed(() => query.isLoading.value)
const isError = computed(() => query.isError.value)
const errorMessage = computed(() => (query.error.value instanceof Error ? query.error.value.message : '加载失败'))

const { remove } = useItemMutations()

// ---- 交互 ----
function openDetail(row: Item) {
  router.push(`/items/${row.id}`)
}

function onEdit(row: Item) {
  router.push(`/items/${row.id}/edit`)
}

async function onDelete(row: Item) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」吗？此操作不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  remove.mutate(row.id)
}

function onStatusFilterChange() {
  page.value = 1 // 换筛选条件回到第一页
}

// el-table 插槽的 row 为 any，经函数参数收窄为 ItemStatus 后再索引状态元数据。
function statusMeta(status: ItemStatus) {
  return ITEM_STATUS_META[status]
}
</script>

<template>
  <el-card>
    <div class="toolbar">
      <el-select
        v-model="filterStatus"
        placeholder="全部状态"
        clearable
        style="width: 160px"
        @change="onStatusFilterChange"
      >
        <el-option v-for="opt in ITEM_STATUS_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-button type="primary" @click="router.push('/items/new')">新建</el-button>
    </div>

    <el-alert
      v-if="isError"
      type="error"
      :closable="false"
      class="error-alert"
      :title="errorMessage"
    />

    <el-table :data="list" v-loading="isLoading" @row-click="openDetail" class="clickable-table">
      <el-table-column prop="id" label="编号" width="80" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).tag">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button link type="primary" @click.stop="onEdit(row)">编辑</el-button>
          <el-button link type="danger" @click.stop="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      class="pagination"
      :page-size="size"
      :total="total"
      layout="total, prev, pager, next"
      background
    />
  </el-card>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}
.error-alert {
  margin-bottom: 16px;
}
.clickable-table :deep(.el-table__row) {
  cursor: pointer;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>

<script setup lang="ts">
// 故障详情「现场图片」图库（第四阶段）：展示某条故障的附件缩略图，支持点击放大与删除。
//
// 为什么不用裸 <img :src="attachment.url">？后端回放端点要带 Authorization 头，
// 而 <img>/<el-image> 的 src 直连不会附带该头 → 401。故统一经 api/attachments.fetchAttachmentBlob
// 拉二进制 blob，再 createObjectURL 成本地地址渲染；组件卸载 / 附件变化时 revoke 释放内存。
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Delete } from '@element-plus/icons-vue'

import { fetchAttachmentBlob } from '../api/attachments'
import { useAttachmentDelete } from '../composables/useFaultAttachments'
import { currentUser, isAdmin } from '../composables/useAuth'
import { formatBytes, formatDateTime } from '../utils/format'
import type { Attachment, Fault } from '../types/fault'

const props = defineProps<{ fault: Fault }>()

// attachmentId -> objectURL。加载完成后按 id 命中即渲染，未命中（加载中/失败）显示占位。
const urls = ref<Record<number, string>>({})
const loading = ref(false)

function revokeAll() {
  for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
  urls.value = {}
}

async function loadBlobs() {
  revokeAll() // 先释放上一批（切换故障 / 删除后 refetch 都会走到这里）
  const list = props.fault.attachments ?? []
  if (list.length === 0) return
  loading.value = true
  try {
    const entries = await Promise.all(
      list.map(async (a): Promise<[number, string] | null> => {
        try {
          const blob = await fetchAttachmentBlob(a)
          return [a.id, URL.createObjectURL(blob)]
        } catch {
          return null // 单张拉取失败不阻断其余，缩略图位置显示占位
        }
      }),
    )
    const map: Record<number, string> = {}
    for (const e of entries) if (e) map[e[0]] = e[1]
    urls.value = map
  } finally {
    loading.value = false
  }
}

// 附件数组引用变化（详情 refetch 会产出新数组）即重载。
watch(() => props.fault.attachments, loadBlobs, { immediate: true })
onBeforeUnmount(revokeAll)

// 可放大预览的地址列表（过滤掉尚未加载/失败的），与缩略图一一对应同一顺序。
const previewList = computed(() =>
  (props.fault.attachments ?? []).map((a) => urls.value[a.id]).filter((u): u is string => Boolean(u)),
)

// 删除权限镜像后端 crud（pending + 创建人/admin）；后端仍是最终裁判，前端只决定按钮显隐。
const canDelete = computed(
  () =>
    props.fault.status === 'pending' &&
    (isAdmin.value || (currentUser.value != null && props.fault.created_by?.id === currentUser.value.id)),
)
const remove = useAttachmentDelete(() => props.fault.id)
function onDelete(a: Attachment) {
  remove.mutate(a.id)
}
</script>

<template>
  <section v-if="(fault.attachments?.length ?? 0) > 0" class="att-gallery">
    <h3 class="att-title">现场图片（{{ fault.attachments.length }}）</h3>
    <div class="att-grid">
      <div v-for="a in fault.attachments" :key="a.id" class="att-card">
        <el-image
          :src="urls[a.id]"
          :preview-src-list="previewList"
          :initial-index="previewList.indexOf(urls[a.id])"
          fit="cover"
          class="att-thumb"
          preview-teleported
        >
          <template #error>
            <div class="att-placeholder">{{ loading ? '加载中…' : '无法显示' }}</div>
          </template>
        </el-image>
        <div class="att-meta">
          <span class="att-name" :title="a.original_name">{{ a.original_name }}</span>
          <span class="att-sub">{{ formatBytes(a.size_bytes) }} · {{ formatDateTime(a.created_at) }}</span>
          <span v-if="a.uploader_name" class="att-sub">上传人：{{ a.uploader_name }}</span>
        </div>
        <el-button
          v-if="canDelete"
          class="att-del"
          link
          type="danger"
          :loading="remove.isLoading.value"
          :icon="Delete"
          @click="onDelete(a)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.att-gallery {
  margin-top: 20px;
}
.att-title {
  margin: 0 0 12px;
  /* 全局字阶 L2：区块小标题 */
  font-size: 15px;
  font-weight: 600;
}
.att-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.att-card {
  position: relative;
  width: 148px;
  padding: 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
}
.att-thumb {
  width: 100%;
  height: 110px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  cursor: zoom-in;
}
.att-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.att-meta {
  display: flex;
  flex-direction: column;
  margin-top: 6px;
  gap: 2px;
}
.att-name {
  font-size: 12px;
  /* 单行省略，长文件名不撑破卡片 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.att-sub {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.att-del {
  position: absolute;
  top: 4px;
  right: 4px;
  padding: 2px;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 4px;
}
</style>

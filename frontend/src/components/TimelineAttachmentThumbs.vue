<script setup lang="ts">
// 时间线单条记录的随附图片（第四阶段追加：追加进展/提交结果可附图）。
// 只读缩略图：时间线 append-only、附图不可删除（方案裁定），故不接删除逻辑，仅展示 + 点击放大。
// 取图口径同 FaultAttachmentGallery：后端回放端点要带 Authorization 头，裸 <img src> 带不了会 401，
// 故经 fetchAttachmentBlob 拉 blob → createObjectURL 渲染，卸载 / 附件变化时 revoke 释放内存。
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { fetchAttachmentBlob } from '../api/attachments'
import type { Attachment } from '../types/fault'

const props = defineProps<{ attachments: Attachment[] }>()

// attachmentId -> objectURL。加载完成后按 id 命中即渲染，未命中（加载中/失败）显示占位。
const urls = ref<Record<number, string>>({})

function revokeAll() {
  for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
  urls.value = {}
}

async function loadBlobs() {
  revokeAll() // 先释放上一批（时间线 refetch 会产出新的附件数组）
  const list = props.attachments
  if (list.length === 0) return
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
}

// 附件数组引用变化即重载（immediate 覆盖首屏已有附图的情况）。
watch(() => props.attachments, loadBlobs, { immediate: true })
onBeforeUnmount(revokeAll)

// 可放大预览的地址列表（过滤未加载/失败的），与缩略图一一对应同一顺序。
const previewList = computed(() =>
  props.attachments.map((a) => urls.value[a.id]).filter((u): u is string => Boolean(u)),
)
</script>

<template>
  <div v-if="attachments.length > 0" class="tl-thumbs">
    <el-image
      v-for="a in attachments"
      :key="a.id"
      :src="urls[a.id]"
      :preview-src-list="previewList"
      :initial-index="previewList.indexOf(urls[a.id])"
      fit="cover"
      class="tl-thumb"
      preview-teleported
    >
      <template #error>
        <div class="tl-thumb-placeholder">无法显示</div>
      </template>
    </el-image>
  </div>
</template>

<style scoped>
.tl-thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.tl-thumb {
  width: 64px;
  height: 64px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  cursor: zoom-in;
}
.tl-thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>

// 图片附件接口封装（第四阶段）：对应后端 routers/attachments.py。
//
// 为什么不走通用 request？上传是 multipart、回放是二进制，都不是 JSON——见 client.requestRaw 注释。
// 三个函数都经 requestRaw，共享同一套 Authorization 注入 / 401 登出 / 非 2xx → ApiError。
import { requestRaw } from './client'
import type { Attachment } from '../types/fault'

// POST /api/faults/{id}/attachments —— 上传一张图片（multipart 字段名固定 file），成功 201 返回元数据。
// 类型/大小/张数由后端最终裁决（422），前端 FaultCreateView 的 before-upload 只作即时反馈。
export async function uploadAttachment(faultId: number, file: File): Promise<Attachment> {
  const fd = new FormData()
  fd.append('file', file)
  const resp = await requestRaw(`/api/faults/${faultId}/attachments`, { method: 'POST', body: fd })
  return (await resp.json()) as Attachment
}

// POST /api/timelines/{id}/attachments —— 向一条时间线（追加进展/提交结果）上传一张附图。
// 两步式第二步：前端先调动作拿 timeline_id 再逐张调本函数（multipart 字段名固定 file）。
// 权限由后端裁决（仅本条时间线操作人或 admin），失败仅提示、不回滚动作。
export async function uploadTimelineAttachment(timelineId: number, file: File): Promise<Attachment> {
  const fd = new FormData()
  fd.append('file', file)
  const resp = await requestRaw(`/api/timelines/${timelineId}/attachments`, { method: 'POST', body: fd })
  return (await resp.json()) as Attachment
}

// GET /api/attachments/{id} —— 拉图片二进制。裸 <img src> 带不了 Bearer 头会 401，
// 故返回 blob 交调用方 createObjectURL 渲染（见 components/FaultAttachmentGallery.vue）。
export async function fetchAttachmentBlob(attachment: Attachment, signal?: AbortSignal): Promise<Blob> {
  const resp = await requestRaw(attachment.url, { signal })
  return await resp.blob()
}

// DELETE /api/attachments/{id} —— 删除附件（后端裁决 pending + 创建人/admin，204 无响应体）。
export async function deleteAttachment(attachmentId: number): Promise<void> {
  await requestRaw(`/api/attachments/${attachmentId}`, { method: 'DELETE' })
}

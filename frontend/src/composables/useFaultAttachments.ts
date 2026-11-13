// 图片附件删除 mutation（第四阶段，详情页 FaultAttachmentGallery 使用）。
// 删除走 DELETE /api/attachments/{id}（后端裁决 pending + 创建人/admin，403/409/404 由后端定夺）。
// 成功后详情缓存失效：附件元数据内嵌在 Fault 里，refetch 即刷新图库。
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'

import { deleteAttachment } from '../api/attachments'
import { toUserMessage } from './useFaultMutations'

// 传 getter 而非固定值：详情页切换故障时组件实例复用，需按当前 fault.id 失效对应缓存。
export function useAttachmentDelete(getFaultId: () => number) {
  const queryClient = useQueryClient()
  return useMutation<void, Error, number>({
    mutationFn: (attachmentId) => deleteAttachment(attachmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fault', getFaultId()] })
      queryClient.invalidateQueries({ queryKey: ['faults'] })
      ElMessage.success('图片已删除')
    },
    onError: (err) => {
      ElMessage.error(toUserMessage(err))
    },
  })
}

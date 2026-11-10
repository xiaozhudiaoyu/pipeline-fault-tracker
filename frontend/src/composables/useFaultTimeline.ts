// 故障时间线查询（TanStack Query v4，第三阶段 M6）。
// queryKey 约定 ['fault-timelines', id]——与详情 ['fault', id] 区分，
// useFaultActions 动作成功后按该 key 失效（一次动作 = 一条新时间线，需求四.2 同事务保证两者一致）。
import { useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'
import type { Ref } from 'vue'

import { fetchTimelines } from '../api/faults'
import type { TimelineEntry } from '../types/timeline'

export function useFaultTimeline(id: Ref<number>) {
  // 与 useFaultDetail 相同的 enabled 守卫：非法 id（NaN/0/负数）不发请求
  const enabled = computed(() => Number.isFinite(id.value) && id.value > 0)
  return useQuery<TimelineEntry[], Error>({
    queryKey: ['fault-timelines', id],
    queryFn: ({ signal }) => fetchTimelines(id.value, signal),
    enabled,
  })
}

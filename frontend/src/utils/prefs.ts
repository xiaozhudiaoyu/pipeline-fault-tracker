// 前端界面偏好持久化：目前只有「故障详情页处理记录排布方向」一项。
//
// 与 utils/token.ts 同款写法：独立小模块 + pft_ 前缀 key + 纯函数 get/set，
// 状态仍由视图持有，本模块只负责「初值从存储读、变更后写回存储」。
//
// 两点约定：
//   · 存储是浏览器级，不区分登录账号（同机换账号登录仍沿用上次的方向）；
//   · 读取一律做白名单校验：只认已知取值，脏值（手工改过存储 / 将来加新方向后回滚）
//     一律回落默认值，绝不让视图拿到非法状态。
import type { TimelineOrientation } from '../types/timeline'

const ORIENTATION_KEY = 'pft_timeline_orientation'

// 无存储值时的默认方向（用户定为横向）。
// 导出供 FaultTimelineList 的 defineModel default 复用，避免同一个默认值两处各写一遍。
export const DEFAULT_ORIENTATION: TimelineOrientation = 'horizontal'

export function getTimelineOrientation(): TimelineOrientation {
  try {
    const saved = localStorage.getItem(ORIENTATION_KEY)
    return saved === 'vertical' || saved === 'horizontal' ? saved : DEFAULT_ORIENTATION
  } catch {
    // 隐私模式 / 禁用站点存储时 localStorage 本身会抛异常，不能因此白屏
    return DEFAULT_ORIENTATION
  }
}

export function setTimelineOrientation(value: TimelineOrientation): void {
  try {
    localStorage.setItem(ORIENTATION_KEY, value)
  } catch {
    // 写失败（配额满 / 禁用存储）只丢持久化，不影响当前页面的显示
  }
}

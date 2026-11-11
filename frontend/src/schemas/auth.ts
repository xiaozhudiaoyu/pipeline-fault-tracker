// Zod 前端校验（第三阶段）：登录表单 + 闭环动作输入 + 用户管理表单。
// 约束口径逐一对照后端 backend/app/schemas.py（规则 3.4），后端仍是最终裁判。
import { z } from 'zod'

// 登录表单（后端 LoginRequest 只要求非空；这里保持同等宽松，业务失败由 401 message 提示）
export const loginSchema = z.object({
  username: z.string({ required_error: '请输入用户名' }).trim().min(1, '请输入用户名'),
  password: z.string({ required_error: '请输入密码' }).min(1, '请输入密码'),
})
export type LoginInput = z.infer<typeof loginSchema>

// 闭环动作文本字段的上限单一来源（逐条对照后端 backend/app/schemas.py：
// progress.note / submit.result_note = 2000，reassign.reason / return.reason / confirm.reason = 500）。
// 为何抽出来：对话框的 maxlength 与下方 zod 的 .max() 必须同一个数，
// 两处各写一遍数字已踩过坑（显示计数到 2000 才拦，但理由实际只允许 500 字）。
export const TEXT_LIMITS = {
  progressNote: 2000,
  resultNote: 2000,
  reason: 500,
} as const

// 进展说明（后端 FaultProgressIn.note：strip 后 ≥2，≤2000）
export const progressNoteSchema = z
  .string({ required_error: '请填写进展内容' })
  .trim()
  .min(2, '进展内容至少 2 个字')
  .max(TEXT_LIMITS.progressNote, `进展内容最多 ${TEXT_LIMITS.progressNote} 字`)

// 处理结果说明（后端 FaultSubmitIn.result_note：strip 后 ≥5，≤2000）
export const resultNoteSchema = z
  .string({ required_error: '请填写处理结果说明' })
  .trim()
  .min(5, '处理结果说明至少 5 个字')
  .max(TEXT_LIMITS.resultNote, `处理结果说明最多 ${TEXT_LIMITS.resultNote} 字`)

// 改派/退回/代确认理由（后端 reason：strip 后 ≥2，≤500；代确认 reason 可空由调用方按角色分支控制）
export const reasonSchema = z
  .string({ required_error: '请填写理由' })
  .trim()
  .min(2, '理由至少 2 个字')
  .max(TEXT_LIMITS.reason, `理由最多 ${TEXT_LIMITS.reason} 字`)

// 新建账号（后端 UserCreate：username 3~50 唯一，密码 ≥6，display_name 1~100）
export const userCreateSchema = z.object({
  username: z
    .string({ required_error: '请输入登录名' })
    .trim()
    .min(3, '登录名至少 3 个字符')
    .max(50, '登录名最多 50 个字符'),
  password: z
    .string({ required_error: '请输入初始密码' })
    .min(6, '密码至少 6 位')
    .max(200, '密码最多 200 位'),
  display_name: z
    .string({ required_error: '请输入展示名称' })
    .trim()
    .min(1, '展示名称不能为空')
    .max(100, '展示名称最多 100 个字符'),
  role: z.enum(['user', 'handler', 'admin'], {
    errorMap: () => ({ message: '请选择角色' }),
  }),
})
export type UserCreateInput = z.infer<typeof userCreateSchema>

// 重置密码（后端 UserResetPasswordIn：≥6）
export const resetPasswordSchema = z
  .string({ required_error: '请输入新密码' })
  .min(6, '密码至少 6 位')
  .max(200, '密码最多 200 位')

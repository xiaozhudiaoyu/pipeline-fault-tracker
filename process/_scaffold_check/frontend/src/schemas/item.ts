// Zod 前端校验：与后端 ItemCreate / ItemUpdate 的约束保持一致。
// 前端先校验给出即时反馈，后端仍是最终裁判（非法输入后端返回 422）。
import { z } from 'zod'

// 创建表单校验（对应后端 ItemCreate 的约束：name 1~100、description 最长 2000）
export const itemCreateSchema = z.object({
  name: z
    .string({ required_error: '请填写名称' })
    .trim()
    .min(1, '名称不能为空')
    .max(100, '名称最多 100 个字'),
  description: z.string().trim().max(2000, '描述最多 2000 字'),
})
export type ItemCreateInput = z.infer<typeof itemCreateSchema>

// 编辑表单校验（对应后端 ItemUpdate：name 1~100、description 最长 2000；status 枚举）
export const itemUpdateSchema = z.object({
  name: z
    .string({ required_error: '请填写名称' })
    .trim()
    .min(1, '名称不能为空')
    .max(100, '名称最多 100 个字'),
  description: z.string().trim().max(2000, '描述最多 2000 字'),
  status: z.enum(['active', 'archived']),
})
export type ItemUpdateInput = z.infer<typeof itemUpdateSchema>

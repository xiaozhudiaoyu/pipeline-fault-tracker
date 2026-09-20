// Zod 前端校验：与后端 FaultCreate / FaultTransition 的约束保持一致（规则 3.4）。
// 前端先校验给出即时反馈，后端仍是最终裁判（非法输入后端返回 422/400/409）。
import { z } from 'zod'

// 登记故障表单校验（对应后端 FaultCreate 的约束：pipeline_id>=1、location 2~200 且首字符非空白、
// symptom 5~1000、occurred_at 不晚于当前时间（容忍 60s 时钟偏移））
export const faultCreateSchema = z.object({
  pipeline_id: z
    .number({ invalid_type_error: '请选择所属流水线', required_error: '请选择所属流水线' })
    .int('流水线 ID 必须是整数')
    .min(1, '请选择所属流水线'),
  location: z
    .string({ required_error: '请填写故障发生位置' })
    .trim()
    .min(2, '故障位置至少 2 个字')
    .max(200, '故障位置最多 200 个字')
    .refine((v) => !/^\s/.test(v), { message: '故障位置首字符不能为空白' }),
  occurred_at: z
    .string({ required_error: '请选择故障发生时间' })
    .min(1, '请选择故障发生时间')
    .refine((v) => !Number.isNaN(Date.parse(v)), { message: '发生时间格式无效' })
    .refine((v) => Date.parse(v) <= Date.now() + 60_000, { message: '发生时间不得晚于当前时间' }),
  symptom: z
    .string({ required_error: '请描述故障现象' })
    .trim()
    .min(5, '故障现象至少 5 个字')
    .max(1000, '故障现象最多 1000 个字'),
})
export type FaultCreateInput = z.infer<typeof faultCreateSchema>

// 状态流转校验（对应后端 FaultTransition + crud 业务规则：目标为 done 时 handling_note 必填；
// 说明一旦提供（非空）strip 后不得少于 5 字）
export const faultTransitionSchema = z
  .object({
    target_status: z.enum(['pending', 'processing', 'done']),
    handling_note: z
      .string()
      .trim()
      .max(2000, '处理说明最多 2000 字')
      .optional()
      .nullable(),
  })
  .superRefine((val, ctx) => {
    // 与后端 HandlingNoteRequiredError 一致：目标为 done 时 handling_note 必填
    if (val.target_status === 'done' && (!val.handling_note || val.handling_note.trim().length === 0)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['handling_note'],
        message: '完成处理时必须填写处理说明',
      })
    }
    // 与后端 field_validator 一致：非空说明 strip 后至少 5 字（空串/null 放行，语义是"本次不改"）
    const note = val.handling_note?.trim()
    if (note && note.length < 5) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['handling_note'],
        message: '处理说明一旦填写，至少 5 个字',
      })
    }
  })
export type FaultTransitionInput = z.infer<typeof faultTransitionSchema>

// 修改基础信息校验（对应后端 FaultUpdate：location 2~200 且首字符非空白、symptom 5~1000、
// handling_note 一旦填写（非空）strip 后≥ 5 字）。表单模型三字段均为字符串，
// handling_note 留空表示「本次不改」，由调用方决定不发该键（done 时锁定，不渲染该字段）。
export const faultUpdateSchema = z
  .object({
    location: z
      .string({ required_error: '请填写故障发生位置' })
      .trim()
      .min(2, '故障位置至少 2 个字')
      .max(200, '故障位置最多 200 个字')
      .refine((v) => !/^\s/.test(v), { message: '故障位置首字符不能为空白' }),
    symptom: z
      .string({ required_error: '请描述故障现象' })
      .trim()
      .min(5, '故障现象至少 5 个字')
      .max(1000, '故障现象最多 1000 个字'),
    handling_note: z.string().trim().max(2000, '处理说明最多 2000 字'),
  })
  .superRefine((val, ctx) => {
    // 与后端 field_validator 一致：非空说明 strip 后至少 5 字（空串放行，语义是「本次不改」）
    const note = val.handling_note.trim()
    if (note.length > 0 && note.length < 5) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['handling_note'],
        message: '处理说明一旦填写，至少 5 个字',
      })
    }
  })
export type FaultUpdateInput = z.infer<typeof faultUpdateSchema>

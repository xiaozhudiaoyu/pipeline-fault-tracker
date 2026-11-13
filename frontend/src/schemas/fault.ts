// Zod 前端校验：与后端 FaultCreate / FaultUpdate 的约束保持一致（规则 3.4）。
// 前端先校验给出即时反馈，后端仍是最终裁判（非法输入后端返回 422/400/409）。
import { z } from 'zod'

// 故障文本字段上限单一来源（仿 schemas/auth.ts 的 TEXT_LIMITS，逐条对照后端 backend/app/schemas.py：
// location ≤200、symptom ≤1000）。zod 的 .max() 与各组件输入框的 maxlength 必须共引这里的同一个数，
// 避免字面量多处各写一遍导致漂移（动作文本侧已踩过该坑，见 auth.ts 头注释）。
export const FAULT_TEXT_LIMITS = {
  location: 200,
  symptom: 1000,
} as const

// 图片附件限制（第四阶段）：与后端 backend/app/config.py 的 attachment_max_bytes /
// attachment_max_per_fault 逐字同源（5 MB / 10 张）。el-upload 的 before-upload 与提示文案
// 均共引本常量，避免“输入上限与校验上限两处硬编码不一致”的旧坑（字数限制侧已踩过）。
// 改后端默认值时务必同步这里，否则前端拦得住、后端拦不住（或反之）。
export const FAULT_ATTACHMENT_LIMITS = {
  maxBytes: 5 * 1024 * 1024, // 5 MB，对齐后端 5_242_880
  maxPerFault: 10,
  accept: '.png,.jpg,.jpeg', // 仅供文件选择器过滤；真实类型以后端文件头判定为准
} as const

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
    .max(FAULT_TEXT_LIMITS.location, `故障位置最多 ${FAULT_TEXT_LIMITS.location} 个字`)
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
    .max(FAULT_TEXT_LIMITS.symptom, `故障现象最多 ${FAULT_TEXT_LIMITS.symptom} 个字`),
  // 优先级（第二阶段）：表单单选一档，未选时序列为 normal（与后端 FaultCreate 缺省一致）。
  // 注：本机 zod 3.22 的 z.enum 不支持 error 参数（v4 写法），非法取值用默认英文消息，
  // 实际触发不了——选项来自 FAULT_PRIORITY_OPTIONS 单选框。
  priority: z.enum(['normal', 'urgent']).default('normal'),
})
export type FaultCreateInput = z.infer<typeof faultCreateSchema>

// （第三阶段 D5）旧 faultTransitionSchema 已随 /transition 端点与 StatusTransitionPanel 一并废除，
// 各动作的文本输入校验见 schemas/auth.ts（progressNoteSchema 等）。

// 修改故障信息校验（第四阶段扩展，对应后端 crud.update_fault 现应用 location / symptom / occurred_at）。
// handling_note / priority 仍不在 PATCH 通道；现场图片删除（remove_attachment_ids）由组件维护 Set直接下发，不经本 schema。
export const faultUpdateSchema = z.object({
  location: z
    .string({ required_error: '请填写故障发生位置' })
    .trim()
    .min(2, '故障位置至少 2 个字')
    .max(FAULT_TEXT_LIMITS.location, `故障位置最多 ${FAULT_TEXT_LIMITS.location} 个字`)
    .refine((v) => !/^\s/.test(v), { message: '故障位置首字符不能为空白' }),
  // 发生时间：表单预填当前值（恒非空），仅改动时下发；口径同登记（不晚于当前 60s 容忍）。
  occurred_at: z
    .string({ required_error: '请选择故障发生时间' })
    .min(1, '请选择故障发生时间')
    .refine((v) => !Number.isNaN(Date.parse(v)), { message: '发生时间格式无效' })
    .refine((v) => Date.parse(v) <= Date.now() + 60_000, { message: '发生时间不得晚于当前时间' }),
  symptom: z
    .string({ required_error: '请描述故障现象' })
    .trim()
    .min(5, '故障现象至少 5 个字')
    .max(FAULT_TEXT_LIMITS.symptom, `故障现象最多 ${FAULT_TEXT_LIMITS.symptom} 个字`),
})
export type FaultUpdateInput = z.infer<typeof faultUpdateSchema>

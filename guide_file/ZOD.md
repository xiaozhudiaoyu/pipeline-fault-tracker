# Zod v3 完整使用文档

> 适用版本：`zod@3.22.5`，即本项目 `frontend/package.json` 锁定的 `~3.22.0`。
> 本文所有 API 名称、方法链、错误结构均已对照 `node_modules/zod/lib/*.d.ts` 类型定义核实；项目实例均取自本仓库真实代码（[schemas/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts)）。
> Zod 是 **TypeScript 优先**的运行时校验库：先声明 schema，再由此**静态推断** TS 类型，一份定义同时得到"运行时校验 + 编译期类型"。

---

## 目录

1. [核心概念](#一核心概念)
2. [安装与基本用法](#二安装与基本用法)
3. [基础类型](#三基础类型)
4. [对象与数组](#四对象与数组)
5. [联合、枚举与字面量](#五联合枚举与字面量)
6. [可选、可空与默认值](#六可选可空与默认值)
7. [数据转换 transform / coerce / pipe](#七数据转换-transform--coerce--pipe)
8. [自定义校验 refine / superRefine](#八自定义校验-refine--superrefine)
9. [解析与错误处理](#九解析与错误处理)
10. [类型推断 z.infer](#十类型推断-zinfer)
11. [复用与组合](#十一复用与组合)
12. [本项目实战范式](#十二本项目实战范式)
13. [常见坑与最佳实践](#十三常见坑与最佳实践)
14. [附：API 速查表](#十四附api-速查表)

---

## 一、核心概念

### 1.1 它解决什么问题

前端拿到的数据（表单输入、接口响应、URL 参数、localStorage）在运行时都是 `unknown`，TS 的类型只在编译期存在、运行时不保证。Zod 让你用**一份 schema** 同时得到：

- **运行时校验**：`schema.parse(data)` 验证数据是否合法，不合法抛出结构化错误。
- **静态类型**：`z.infer<typeof schema>` 自动推断出对应的 TS 类型，无需手写 interface 再和校验逻辑保持同步。

> 本项目定位（见 [schemas/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 头注释）：**前端先校验给出即时反馈，后端仍是最终裁判**。Zod 负责前者——在提交前拦下非法输入、把错误标红到对应字段；非法数据即便绕过前端，后端仍会返回 422/400/409。

### 1.2 三个基本动作

```ts
import { z } from 'zod'

// 1. 声明 schema
const schema = z.object({ name: z.string().min(2) })

// 2. 校验（parse 抛错 / safeParse 返回结果对象）
const result = schema.safeParse({ name: 'A' })

// 3. 推断类型
type Input = z.infer<typeof schema>   // { name: string }
```

### 1.3 parse vs safeParse

| 方法 | 失败行为 | 适用 |
|---|---|---|
| `parse(data)` | **抛出** `ZodError` | 确信数据合法、或想用 try/catch；也用于"失败即中断"的场景。 |
| `safeParse(data)` | **返回** `{ success, data \| error }`，不抛错 | 表单校验等"需要拿到错误逐字段提示"的场景（本项目用的就是这个）。 |

`safeParse` 返回类型（出处：`types.d.ts` 的 `SafeParseReturnType`）：

```ts
type SafeParseReturnType<Input, Output> =
  | { success: true;  data: Output }        // 成功：data 是校验+转换后的结果
  | { success: false; error: ZodError<Input> } // 失败：error.issues 是错误列表
```

> 另有异步版 `parseAsync` / `safeParseAsync`（别名 `spa`），当 schema 含异步 `refine`/`transform` 时使用。

---

## 二、安装与基本用法

### 2.1 安装

本项目已安装（见 [package.json](file:///e:/python项目/pipeline-fault-tracker/frontend/package.json)）：

```jsonc
"dependencies": {
  "zod": "~3.22.0"
}
```

新项目安装：

```powershell
npm install zod@~3.22.0
```

> Zod 无运行时依赖（`package.json` 的 `dependencies` 为空），纯 TypeScript 实现。

### 2.2 导入

```ts
import { z } from 'zod'        // 推荐：命名空间对象
// 或 import * as z from 'zod'
// 或 import { z } from 'zod/v4'  ← 不要这样，v3 无此子路径
```

出处：`lib/index.d.ts` 同时提供 `export { z }` 与 `export default z`，三种导入方式都可用，本项目统一用 `import { z } from 'zod'`。

### 2.3 项目里的位置

本项目把 schema 集中放在 [src/schemas/](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts)，与"纯类型定义" [src/types/](file:///e:/python项目/pipeline-fault-tracker/frontend/src/types/fault.ts) 分开：

- `types/fault.ts`：接口响应契约（`Fault` / `FaultList` 等，对应后端 `schemas.py` 的**输出**）。
- `schemas/fault.ts`：表单**输入**校验（`faultCreateSchema` / `faultTransitionSchema`），并用 `z.infer` 导出输入类型。

> 约定：**校验逻辑（schema）与展示类型（interface）分文件**，schema 只管"进来的数据合不合法"，interface 描述"后端返回长什么样"。

---

## 三、基础类型

### 3.1 原始类型

```ts
z.string()      // string
z.number()      // number
z.bigint()      // bigint
z.boolean()     // boolean
z.date()        // Date
z.symbol()      // symbol
z.undefined()   // undefined
z.null()        // null
z.any()         // any（不校验）
z.unknown()     // unknown（不校验，但类型安全）
z.never()       // never（永远失败）
z.nan()         // NaN
z.void()        // void
```

### 3.2 字符串校验链

`ZodString` 的方法（出处：`types.d.ts` 第 171-228 行），**全部返回 `ZodString`，可链式调用**：

| 方法 | 说明 |
|---|---|
| `.min(n, msg?)` | 最小长度 |
| `.max(n, msg?)` | 最大长度 |
| `.length(n, msg?)` | 精确长度 |
| `.email(msg?)` | 邮箱格式 |
| `.url(msg?)` | URL 格式 |
| `.uuid(msg?)` | UUID |
| `.cuid()` / `.cuid2()` / `.ulid()` | 各类 ID |
| `.emoji()` | emoji |
| `.ip(options?)` | IP（可指定 `version: 'v4' \| 'v6'`） |
| `.datetime(options?)` | ISO 8601 datetime（可设 `precision` / `offset`） |
| `.regex(re, msg?)` | 正则匹配 |
| `.includes(s, options?)` | 包含子串（可设 `position`） |
| `.startsWith(s, msg?)` / `.endsWith(s, msg?)` | 前缀/后缀 |
| `.trim()` | **转换**：去首尾空格（注意：这是 transform，不是校验） |
| `.toLowerCase()` / `.toUpperCase()` | **转换**：大小写 |
| `.nonempty(msg?)` | ⚠️ 已 `@deprecated`，改用 `.min(1)` |

> `msg` 参数可以是字符串，也可以是 `{ message: string }` 对象（`errorUtil.ErrMessage`）。

本项目 [faultCreateSchema](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 的字符串字段：

```ts
location: z
  .string({ required_error: '请填写故障发生位置' })
  .trim()                       // 先去空格，再按去空格后的长度校验
  .min(2, '故障位置至少 2 个字')
  .max(200, '故障位置最多 200 个字'),
symptom: z
  .string({ required_error: '请描述故障现象' })
  .trim()
  .min(5, '故障现象至少 5 个字'),
```

> **顺序要点**：`.trim()` 放在 `.min()` 前，校验的是**去空格后**的长度；若先 `.min()` 后 `.trim()`，则按原始长度校验。本项目统一先 trim 再校验。

### 3.3 数字校验链

`ZodNumber` 的方法（出处：`types.d.ts` 第 255-286 行）：

| 方法 | 说明 |
|---|---|
| `.min(n, msg?)` / `.gte(n, msg?)` | ≥ n |
| `.max(n, msg?)` / `.lte(n, msg?)` | ≤ n |
| `.gt(n, msg?)` | > n |
| `.lt(n, msg?)` | < n |
| `.int(msg?)` | 必须整数 |
| `.positive(msg?)` | > 0 |
| `.negative(msg?)` | < 0 |
| `.nonnegative(msg?)` | ≥ 0 |
| `.nonpositive(msg?)` | ≤ 0 |
| `.multipleOf(n, msg?)` / `.step(n, msg?)` | n 的倍数 |
| `.finite(msg?)` | 有限数（非 Infinity/NaN） |
| `.safe(msg?)` | 安全整数范围 |

本项目的数字字段：

```ts
pipeline_id: z
  .number({ invalid_type_error: '请选择所属流水线', required_error: '请选择所属流水线' })
  .int('流水线 ID 必须是整数')
  .min(1, '请选择所属流水线'),
```

### 3.4 自定义错误消息（创建参数）

每个基础类型的 `create` 都接受 `RawCreateParams`（出处：`types.d.ts` 第 25-30 行）：

```ts
z.number({
  invalid_type_error: '类型不对时显示',   // 传了值但类型不匹配（如传了字符串）
  required_error: '缺失时显示',           // 值为 undefined（必填项没填）
  description: '字段描述',                // 元信息，可用于生成文档
})
```

> `invalid_type_error` vs `required_error` 的区别：前者是"填了但类型错"，后者是"压根没填（undefined）"。本项目对 `pipeline_id` 两者都设成同一句"请选择所属流水线"，因为下拉框未选时既可能是 undefined 也可能类型不符。

---

## 四、对象与数组

### 4.1 对象 z.object

```ts
const schema = z.object({
  id: z.number(),
  name: z.string(),
  tags: z.array(z.string()),
})
type T = z.infer<typeof schema>   // { id: number; name: string; tags: string[] }
```

**未知键处理策略**（出处：`ZodObject` 的 `strip`/`passthrough`/`strict`/`catchall`）：

| 方法 | 行为 |
|---|---|
| `.strip()`（默认） | **静默丢弃** schema 未声明的键。 |
| `.passthrough()` | **保留**未声明的键。 |
| `.strict(msg?)` | 出现未声明键时**报错**（`unrecognized_keys`）。 |
| `.catchall(schema)` | 未声明的键用给定 schema 校验后保留。 |

```ts
z.object({ a: z.number() }).strict()
  .parse({ a: 1, b: 2 })   // ❌ 抛错：b 是未识别键
z.object({ a: z.number() }).passthrough()
  .parse({ a: 1, b: 2 })   // ✅ 返回 { a: 1, b: 2 }
```

> 本项目两个 schema 都用默认 `strip`，表单多余字段（如果有）会被丢弃，只保留声明的字段。

### 4.2 数组 z.array

```ts
z.array(z.number())             // number[]
z.number().array()              // 等价写法
z.array(z.string()).min(1)      // 非空数组
z.array(z.string()).nonempty()  // 同上（类型层面保证至少一个元素）
z.array(z.string()).max(10)     // 最多 10 个
z.array(z.string()).length(3)   // 恰好 3 个
```

数组元素访问：`schema.element`（取出元素 schema）。

### 4.3 元组 z.tuple

固定长度、每位类型不同的数组：

```ts
const point = z.tuple([z.number(), z.number()])   // [number, number]
point.parse([1, 2])      // ✅
point.parse([1, 2, 3])   // ❌ 长度不符
```

### 4.4 记录 z.record

键为字符串、值同类型的字典：

```ts
z.record(z.number())                    // Record<string, number>
z.record(z.enum(['a', 'b']), z.number()) // 键限定为 'a'|'b'
```

> 本项目 [types/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/types/fault.ts) 里的 `FAULT_STATUS_META: Record<FaultStatus, ...>` 是手写 interface（描述后端输出），未用 Zod；若要在运行时校验这类字典，可用 `z.record`。

---

## 五、联合、枚举与字面量

### 5.1 枚举 z.enum

限定为一组字符串字面量：

```ts
const statusSchema = z.enum(['pending', 'processing', 'done'])
type Status = z.infer<typeof statusSchema>   // 'pending' | 'processing' | 'done'

statusSchema.parse('pending')   // ✅
statusSchema.parse('unknown')   // ❌ invalid_enum_value
```

`.options` 可取出枚举值数组；`z.nativeEnum(TS枚举)` 用于校验 TS 的 `enum`。

本项目 [faultTransitionSchema](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts)：

```ts
target_status: z.enum(['pending', 'processing', 'done']),
```

> 与 [types/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/types/fault.ts) 的 `FaultStatus = 'pending' | 'processing' | 'done'` 保持一致（镜像后端 `models.FaultStatus`）。

### 5.2 字面量 z.literal

单个精确值：

```ts
z.literal('admin')
z.literal(42)
z.literal(true)
```

### 5.3 联合 z.union / .or

"或"关系，按顺序尝试每个分支：

```ts
z.union([z.string(), z.number()])    // string | number
z.string().or(z.number())            // 等价写法
```

### 5.4 可辨识联合 z.discriminatedUnion

当各分支有一个共同的"判别字段"时，用它比 `union` **性能更好、错误更精准**：

```ts
const schema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('text'), value: z.string() }),
  z.object({ type: z.literal('num'),  value: z.number() }),
])
schema.parse({ type: 'num', value: '1' })
// ❌ 直接报 value 类型错，而不是把两个分支的错误都列出来
```

> 本项目暂未用到联合/可辨识联合（表单字段类型固定），此节作为需要"多形态数据"时的范式参考。

---

## 六、可选、可空与默认值

### 6.1 optional / nullable / nullish

| 方法 | 含义 | 推断类型 |
|---|---|---|
| `.optional()` | 允许 `undefined` | `T \| undefined` |
| `.nullable()` | 允许 `null` | `T \| null` |
| `.nullish()` | 允许 `undefined` 和 `null`（= optional + nullable） | `T \| null \| undefined` |

```ts
z.string().optional()   // string | undefined
z.string().nullable()   // string | null
z.string().nullish()    // string | null | undefined
```

### 6.2 default

提供默认值，输入为 `undefined` 时用默认值填充（输出类型不再含 `undefined`）：

```ts
const schema = z.object({ page: z.number().default(1) })
schema.parse({})            // { page: 1 }
z.infer<typeof schema>      // { page: number }（注意：不是 number | undefined）
```

### 6.3 catch

校验失败时不抛错，回退到给定值：

```ts
z.number().catch(0).parse('abc')   // 0（而非抛错）
z.number().catch((ctx) => {        // 也可用函数，拿到 error 与 input
  console.log(ctx.error)
  return 0
})
```

### 6.4 项目实例：optional + nullable 组合

本项目 [faultTransitionSchema](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 的 `handling_note`：

```ts
handling_note: z.string().trim().max(2000, '处理说明最多 2000 字').optional().nullable(),
```

> 语义：处理说明可以**不填**（`undefined`，对应"本次不改说明"）也可以**显式传 null**，两种都合法；但若填了字符串，会先 trim 再校验 ≤2000 字。这与后端 `FaultTransition` 的 `handling_note?: string | null` 契约一致（见 [types/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/types/fault.ts)）。
>
> 注意 `.optional().nullable()` 与 `.nullish()` 等价，本项目写成前者是为了可读性（明确表达"既可不传也可为 null"两层含义）。

---

## 七、数据转换 transform / coerce / pipe

校验通过后，Zod 还能**转换**数据。`parse`/`safeParse` 返回的 `data` 是**转换后**的结果。

### 7.1 transform

```ts
const schema = z.string().transform((val) => val.toUpperCase())
schema.parse('abc')   // 'ABC'

// 带类型标注
z.string().transform((val): number => val.length)
```

`.trim()` / `.toLowerCase()` / `.toUpperCase()` 本质就是内置的 transform。

### 7.2 coerce —— 强制类型转换

`z.coerce.*` 会先用 `typeof` 强转再校验（出处：`types.d.ts` 第 1014 行的 `coerce` 命名空间，支持 `string`/`number`/`boolean`/`bigint`/`date`）：

```ts
z.coerce.number().parse('42')      // 42（字符串转数字）
z.coerce.string().parse(42)        // '42'
z.coerce.boolean().parse('')       // false（!!'' ）
z.coerce.date().parse('2026-01-01') // Date 对象
```

> 表单里的数字输入框、URL 查询参数常是字符串，`z.coerce.number()` 很实用。**但本项目未用 coerce**：`pipeline_id` 来自 `el-select`（已是 number），`page/size` 来自 `el-pagination`（已是 number），无需强转；且业务要求"类型不对就该报错"，用普通 `z.number()` + `invalid_type_error` 更严格。

### 7.3 pipe

把前一个 schema 的输出喂给后一个，常用于"先转换再校验"或"先校验再转换"：

```ts
// 先把字符串转数字，再校验是否为正整数
z.string().pipe(z.coerce.number().int().positive())

// 等价于先 transform 再校验
```

### 7.4 preprocess

在校验**之前**对原始输入做预处理：

```ts
z.preprocess(
  (val) => (typeof val === 'string' ? val.trim() : val),  // 预处理
  z.string().min(1)                                        // 再校验
)
```

> 本项目用 `.trim()`（字符串内置 transform）达到类似效果，未单独用 `preprocess`。

---

## 八、自定义校验 refine / superRefine

当内置校验器不够用（如跨字段依赖、自定义格式），用 `refine` / `superRefine`。

### 8.1 refine —— 单条件断言

```ts
schema.refine(check, message?)
```

- `check: (arg) => boolean | Promise<boolean>`：返回 `true` 通过。
- `message`：字符串，或 `{ message, path?, params? }` 对象。

本项目 [occurred_at](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 校验日期格式：

```ts
occurred_at: z
  .string({ required_error: '请选择故障发生时间' })
  .min(1, '请选择故障发生时间')
  .refine((v) => !Number.isNaN(Date.parse(v)), { message: '发生时间格式无效' }),
```

> `refine` 返回的是 `ZodEffects` 包装类型，仍可继续链式调用其它 `ZodType` 方法。多个 `refine` 可串联，逐个执行。

带参数的错误对象：

```ts
z.string().refine((v) => v.startsWith('A'), {
  message: '必须以 A 开头',
  path: ['fieldName'],   // 自定义错误归属路径
  params: { extra: 'info' },  // 附加信息，会出现在 issue.params
})
```

### 8.2 superRefine —— 多条件 / 跨字段

`superRefine` 拿到一个 `RefinementCtx`（出处：`types.d.ts` 第 8-11 行），可 `addIssue` **多次**、并指定 `path`，适合跨字段校验：

```ts
schema.superRefine((val, ctx) => {
  ctx.addIssue({
    code: z.ZodIssueCode.custom,
    path: ['fieldA'],        // 错误挂到哪个字段
    message: '...',
    fatal: false,            // 可选：是否致命（致命则中止后续校验）
  })
})
```

`RefinementCtx`：

```ts
type RefinementCtx = {
  addIssue: (arg: IssueData) => void
  path: (string | number)[]   // 当前节点路径
}
```

本项目 [faultTransitionSchema](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 的跨字段校验（目标为 done 时说明必填）：

```ts
export const faultTransitionSchema = z
  .object({
    target_status: z.enum(['pending', 'processing', 'done']),
    handling_note: z.string().trim().max(2000, '处理说明最多 2000 字').optional().nullable(),
  })
  .superRefine((val, ctx) => {
    // 与后端 HandlingNoteRequiredError 一致：目标为 done 时 handling_note 必填
    if (val.target_status === 'done' && (!val.handling_note || val.handling_note.trim().length === 0)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['handling_note'],          // 错误精确挂到 handling_note 字段
        message: '完成处理时必须填写处理说明',
      })
    }
  })
```

> 关键：`superRefine` 挂在 `z.object(...)` **之后**，能同时拿到 `target_status` 和 `handling_note` 两个字段做联合判断；`path: ['handling_note']` 让前端能把这条错误标红到"处理说明"输入框（见 [StatusTransitionPanel.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/components/StatusTransitionPanel.vue) 的 `noteError`）。

### 8.3 refine vs superRefine 选型

| 场景 | 用 |
|---|---|
| 单个布尔条件、错误挂当前字段 | `refine` |
| 跨字段依赖、一次加多条错误、自定义 path | `superRefine` |
| 异步校验（如查后端是否重名） | `refine(async ...)` + `safeParseAsync` |

---

## 九、解析与错误处理

### 9.1 safeParse 结果消费

本项目两个提交入口都用 `safeParse` + 遍历 `issues` 做字段级标红。[FaultCreateView.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/views/FaultCreateView.vue)：

```ts
function onSubmit() {
  clearErrors()
  const result = faultCreateSchema.safeParse(form)
  if (!result.success) {
    // 按字段归并 Zod issues（每个字段只取第一条，避免同字段堆叠多条）
    for (const issue of result.error.issues) {
      const key = String(issue.path[0] ?? 'form')
      if (!fieldErrors[key]) fieldErrors[key] = issue.message
    }
    return
  }
  const payload: FaultCreatePayload = result.data   // 成功：data 是校验+trim 后的结果
  create.mutate(payload, { /* ... */ })
}
```

要点：
- `result.success` 为 `false` 时，`result.error` 是 `ZodError`，`result.error.issues` 是错误数组。
- `issue.path[0]` 取出错的**顶层字段名**（如 `'location'`），用作 `fieldErrors` 的 key 绑定到对应 `el-form-item`。
- `result.data` 是**校验并转换后**的数据（`.trim()` 已生效），可直接作为提交 payload。

### 9.2 ZodError 结构

`ZodError`（出处：`ZodError.d.ts` 第 135-150 行）继承 `Error`：

| 成员 | 类型 | 说明 |
|---|---|---|
| `issues` | `ZodIssue[]` | 错误列表（核心）。 |
| `errors` | `ZodIssue[]` | `issues` 的别名 getter。 |
| `message` | `string` | getter，`issues` 的 JSON 串。 |
| `format()` | `ZodFormattedError` | **树形**结构，按字段嵌套，每层有 `_errors`。 |
| `flatten()` | `{ formErrors, fieldErrors }` | **扁平**结构，按顶层字段归并消息。 |
| `isEmpty` | `boolean` | 是否无错误。 |
| `addIssue` / `addIssues` | `Function` | 手动追加错误。 |

单条 `ZodIssue`（出处：`ZodError.d.ts` 第 119-122 行）：

```ts
type ZodIssue = {
  code: ZodIssueCode      // 错误类型，如 'invalid_type' / 'too_small' / 'custom'
  path: (string | number)[] // 出错字段路径，如 ['location'] 或 ['items', 0, 'name']
  message: string         // 人类可读消息
  fatal?: boolean
  // ...各 code 特有的附加字段（expected/received/minimum/maximum 等）
}
```

`ZodIssueCode` 全部取值（出处：`ZodError.d.ts` 第 12-29 行）：
`invalid_type`、`invalid_literal`、`custom`、`invalid_union`、`invalid_union_discriminator`、`invalid_enum_value`、`unrecognized_keys`、`invalid_arguments`、`invalid_return_type`、`invalid_date`、`invalid_string`、`too_small`、`too_big`、`invalid_intersection_types`、`not_multiple_of`、`not_finite`。

### 9.3 format() —— 树形错误

```ts
const result = schema.safeParse(data)
if (!result.success) {
  console.log(result.error.format())
  // {
  //   _errors: [],
  //   location: { _errors: ['故障位置至少 2 个字'] },
  //   symptom:  { _errors: ['故障现象至少 5 个字'] },
  // }
}
```

`format` 还能传 mapper 自定义每个 issue 的转换：`format((issue) => issue.message.toUpperCase())`。

### 9.4 flatten() —— 扁平错误

```ts
result.error.flatten()
// {
//   formErrors: [],                              // 非字段级错误（如 superRefine 挂到根）
//   fieldErrors: {                               // 按顶层字段归并
//     location: ['故障位置至少 2 个字'],
//     symptom: ['故障现象至少 5 个字'],
//   }
// }
```

> `flatten()` 很适合"一次性拿到所有字段错误"直接铺到表单；本项目选择手动遍历 `issues`（[9.1](#91-safeparse-结果消费)），因为要"每字段只取第一条"并控制归并逻辑，手动遍历更灵活。

### 9.5 全局错误消息定制（errorMap）

可注册全局 errorMap 统一改写默认英文消息（如中文化）：

```ts
import { z } from 'zod'
z.setErrorMap((issue, ctx) => {
  if (issue.code === z.ZodIssueCode.invalid_type) {
    return { message: `${issue.expected} 类型不正确` }
  }
  return { message: ctx.defaultError }
})
```

也可在单个 schema 上局部定制：`z.string({ errorMap: (issue, ctx) => ({ message: '...' }) })`。

> 本项目**未用全局 errorMap**，而是在每个字段上直接写中文 `message` / `required_error` / `invalid_type_error`，更直观、定位更清晰。

---

## 十、类型推断 z.infer

### 10.1 z.infer —— 从 schema 推输出类型

```ts
const schema = z.object({ id: z.number(), name: z.string() })
type T = z.infer<typeof schema>   // { id: number; name: string }
```

`z.infer` 是 `TypeOf` 的别名（出处：`types.d.ts` 第 16、19 行），取的是 schema 的 `_output` 类型（即 transform 之后的类型）。

本项目 [schemas/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 导出两个推断类型：

```ts
export type FaultCreateInput = z.infer<typeof faultCreateSchema>
// { pipeline_id: number; location: string; occurred_at: string; symptom: string }

export type FaultTransitionInput = z.infer<typeof faultTransitionSchema>
// { target_status: 'pending'|'processing'|'done'; handling_note?: string | null }
```

> 好处：schema 改了（如加个字段、改个校验），推断类型自动跟着变，不用手改 interface，杜绝"校验与类型不同步"。

### 10.2 z.input vs z.output

当 schema 含 `transform` / `default` / `coerce` 时，**输入类型与输出类型可能不同**：

```ts
const schema = z.object({ page: z.number().default(1) })

type In  = z.input<typeof schema>    // { page?: number | undefined }（输入可缺）
type Out = z.output<typeof schema>   // { page: number }（输出必有）
// z.infer 等价于 z.output
```

| 函数 | 取哪个类型 | 用途 |
|---|---|---|
| `z.infer<S>` / `z.output<S>` | `_output` | parse 之后的数据类型（最常用）。 |
| `z.input<S>` | `_input` | parse 之前的入参类型（含 transform/default 时与 output 不同）。 |

> 本项目表单 schema 无 `default`/`transform` 改变类型（`.trim()` 是 string→string），所以 input 与 output 基本一致，统一用 `z.infer`。

---

## 十一、复用与组合

### 11.1 对象 schema 的变换

`ZodObject` 提供一组变换方法（出处：`types.d.ts` 第 490-551 行），**都返回新 schema，不改原 schema**：

| 方法 | 作用 |
|---|---|
| `.pick({ a: true, b: true })` | 只保留指定字段 |
| `.omit({ a: true })` | 剔除指定字段 |
| `.partial()` | 所有字段变可选（`T → T?`） |
| `.partial({ a: true })` | 仅指定字段变可选 |
| `.required()` | 所有字段变必填（去掉 optional） |
| `.required({ a: true })` | 仅指定字段变必填 |
| `.extend({ c: z.number() })` | 新增/覆盖字段 |
| `.merge(otherObjectSchema)` | 合并两个 object schema |
| `.keyof()` | 把字段名变成 `z.enum` |
| `.shape` | 取出原始字段定义对象（`ZodRawShape`） |

```ts
const base = z.object({ id: z.number(), name: z.string(), pwd: z.string() })

base.pick({ id: true, name: true })   // 只要 id/name（如列表展示）
base.omit({ pwd: true })              // 去掉 pwd（如对外输出）
base.partial()                        // 全部可选（如 PATCH 更新体）
base.extend({ age: z.number() })      // 加字段
```

> `.deepPartial()` 已 `@deprecated`，嵌套对象递归变可选请谨慎使用。

### 11.2 典型复用场景

```ts
// 创建体 → 更新体（全部可选 + 去掉不可改的 id）
const createSchema = z.object({ id: z.number(), name: z.string(), email: z.string() })
const updateSchema = createSchema.omit({ id: true }).partial()

// 列表项 → 详情（复用字段再扩展）
const listItem = z.object({ id: z.number(), title: z.string() })
const detail = listItem.extend({ content: z.string(), createdAt: z.string() })
```

> 本项目两个 schema（create / transition）字段差异大、无复用关系，故各自独立定义，未用 pick/omit/extend。若将来新增"编辑故障"表单，可基于 `faultCreateSchema.partial()` 派生。

### 11.3 schema 组合

```ts
// 交叉（同时满足两个 schema）
z.intersection(schemaA, schemaB)
schemaA.and(schemaB)

// 联合（满足其一）
z.union([schemaA, schemaB])
schemaA.or(schemaB)

// 懒加载（递归类型，如树形结构）
const category = z.object({
  name: z.string(),
  children: z.lazy(() => z.array(category)),   // 自引用必须用 lazy
})
```

---

## 十二、本项目实战范式

### 12.1 整体数据流

```
用户填表（reactive form）
   │  点击提交
   ▼
schema.safeParse(form)
   ├─ success=false → 遍历 error.issues → 按 issue.path[0] 填 fieldErrors → el-form-item 标红
   └─ success=true  → result.data（已 trim）作为 payload
         │
         ▼
   useFaultMutations.create/transition.mutate(payload)
         │  （后端仍是最终裁判，非法返回 422/400/409 → onError → ElMessage）
         ▼
   成功 → invalidate/setQueryData 刷缓存 + 跳转/toast
```

### 12.2 校验规则与后端对齐

本项目 Zod schema 的每条规则都**镜像后端约束**（见 [schemas/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts) 注释），形成"前端即时反馈 + 后端最终裁判"双保险：

| 前端 Zod 规则 | 对应后端 | 绕过前端的后果 |
|---|---|---|
| `pipeline_id` int & ≥1 | `FaultCreate.pipeline_id >= 1` | 422 参数校验 |
| `location` 2~200 字 | `FaultCreate.location` 长度约束 | 422 |
| `symptom` ≥5 字 | `FaultCreate.symptom >= 5` | 422 |
| `occurred_at` 可被 `Date.parse` | 后端 datetime 解析 | 422 |
| done 时 `handling_note` 必填 | `HandlingNoteRequiredError` | 400 `handling_note_required` |
| `target_status` ∈ 枚举 | `FaultTransition` | 422 / 409 `invalid_transition` |

### 12.3 字段级错误绑定

校验错误通过 `issue.path[0]` 映射到表单字段，绑定到 Element Plus 的 `el-form-item :error`：

```ts
// FaultCreateView.vue
const fieldErrors = reactive<Record<string, string>>({})
for (const issue of result.error.issues) {
  const key = String(issue.path[0] ?? 'form')
  if (!fieldErrors[key]) fieldErrors[key] = issue.message   // 每字段只取第一条
}
```

```vue
<el-form-item label="故障位置" required :error="fieldErrors.location">
  <el-input v-model="form.location" />
</el-form-item>
```

> `superRefine` 里 `path: ['handling_note']` 的跨字段错误，同样会被这套机制归到 `handling_note`，标红到"处理说明"框（见 [StatusTransitionPanel.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/components/StatusTransitionPanel.vue) 的 `noteError`）。

---

## 十三、常见坑与最佳实践

### 13.1 坑点清单

| # | 坑 | 现象 | 规避 |
|---|---|---|---|
| 1 | `.trim()` 与 `.min()` 顺序 | 先 min 后 trim 会按原始长度校验，空格算进字数 | 先 `.trim()` 再 `.min()`（见 [3.2](#32-字符串校验链)） |
| 2 | 用 `parse` 不设 try/catch | 校验失败直接抛 `ZodError` 中断流程 | 表单场景用 `safeParse`（见 [1.3](#13-parse-vs-safeparse)） |
| 3 | `issue.path` 当成字符串 | `path` 是数组（`(string\|number)[]`），直接当 string 用会错 | 取 `path[0]` 或用 `path.join('.')`（见 [9.1](#91-safeparse-结果消费)） |
| 4 | 以为前端校验能替代后端 | 绕过前端（直接调 API）非法数据入库 | 后端必须独立校验，前端只为 UX（见 [12.2](#122-校验规则与后端对齐)） |
| 5 | `z.infer` 用在含 default 的 schema 上以为字段可选 | default 字段输出类型是必有（非 optional） | 入参类型用 `z.input`，输出用 `z.infer`（见 [10.2](#102-zinput-vs-zoutput)） |
| 6 | 递归类型不用 lazy | 直接自引用导致"初始化前访问"报错 | 自引用字段用 `z.lazy(() => ...)`（见 [11.3](#113-schema-组合)） |
| 7 | `nonempty()` 已废弃 | 控制台/类型提示 deprecated | 字符串用 `.min(1)`，数组用 `.nonempty()` 仍可（见 [3.2](#32-字符串校验链)） |
| 8 | 枚举值与后端不同步 | 前端 `z.enum` 漏了某个状态，合法值被拦 | 枚举镜像后端定义，集中到 types 常量（见 [5.1](#51-枚举-zenum)） |

### 13.2 最佳实践

- **schema 集中管理**：放 `src/schemas/`，与展示类型 `src/types/` 分开（见 [2.3](#23-项目里的位置)）。
- **校验规则对齐后端**：每条规则注明对应的后端约束，前端只做即时反馈，后端是最终裁判。
- **用 `safeParse` 做表单**：拿 `error.issues` 逐字段标红，`data` 作为提交 payload（已含 trim 等转换）。
- **错误消息中文化**：直接在字段上写 `message` / `required_error` / `invalid_type_error`，比全局 errorMap 更直观。
- **跨字段校验用 `superRefine` + `path`**：把错误精确挂到目标字段，复用同一套字段标红机制。
- **用 `z.infer` 导出类型**：避免手写 interface 与 schema 不同步。
- **复用派生 schema**：更新体用 `create.omit({id}).partial()` 派生，减少重复定义。

---

## 十四、附：API 速查表

### 14.1 z 命名空间工厂（出处：`types.d.ts` 第 1056 行导出）

| 分类 | 工厂 |
|---|---|
| 原始 | `string` `number` `bigint` `boolean` `date` `symbol` `null` `undefined` `nan` `void` `never` `any` `unknown` |
| 对象/数组 | `object` `strictObject` `array` `tuple` `record` `map` `set` |
| 联合/枚举 | `union` `discriminatedUnion` `enum` `nativeEnum` `literal` `intersection` |
| 包装 | `optional` `nullable` `pipeline` `promise` `lazy` |
| 函数 | `function`（校验入参/返回） |
| 实例 | `instanceof` |
| 预处理 | `preprocess` |
| 转换 | `transformer` / `effect`（`ZodEffects`） |
| 强转 | `coerce.string` `coerce.number` `coerce.boolean` `coerce.bigint` `coerce.date` |

### 14.2 通用方法（所有 schema 都有，出处：`ZodType` 第 44-95 行）

| 方法 | 说明 |
|---|---|
| `parse` / `safeParse` | 同步解析（抛错 / 返回结果） |
| `parseAsync` / `safeParseAsync`(`spa`) | 异步解析（含异步 refine/transform 时） |
| `refine` / `superRefine` / `refinement` | 自定义校验 |
| `transform` | 转换输出 |
| `optional` / `nullable` / `nullish` | 可选/可空 |
| `default` / `catch` | 默认值 / 失败回退 |
| `array` / `promise` | 包成数组 / Promise |
| `or` / `and` | 联合 / 交叉 |
| `pipe` | 管道 |
| `describe` | 加描述元信息 |
| `brand` | 品牌类型（名义类型区分） |
| `readonly` | 输出只读 |
| `isOptional` / `isNullable` | 运行时判断是否可选/可空 |

### 14.3 ZodError 速查（出处：`ZodError.d.ts`）

| 成员 | 说明 |
|---|---|
| `issues` / `errors` | 错误数组（`ZodIssue[]`） |
| `format()` | 树形错误（`_errors` 嵌套） |
| `flatten()` | 扁平错误（`formErrors` + `fieldErrors`） |
| `message` | issues 的 JSON 串 |
| `addIssue` / `addIssues` | 手动追加 |
| `ZodIssueCode` | 错误码枚举（16 种，见 [9.2](#92-zoderror-结构)） |

---

## 参考

- 官方文档：https://zod.dev
- 类型出处（本项目已安装）：
  - `frontend/node_modules/zod/lib/types.d.ts`（schema 类型与方法）
  - `frontend/node_modules/zod/lib/ZodError.d.ts`（错误结构）
- 项目内实例：
  - [schemas/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/schemas/fault.ts)（`z.object` / `z.number` / `z.string` / `z.enum` / `.refine` / `.superRefine` / `z.infer`）
  - [FaultCreateView.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/views/FaultCreateView.vue)（`safeParse` + 字段级标红）
  - [StatusTransitionPanel.vue](file:///e:/python项目/pipeline-fault-tracker/frontend/src/components/StatusTransitionPanel.vue)（跨字段 `superRefine` 错误消费）
  - [types/fault.ts](file:///e:/python项目/pipeline-fault-tracker/frontend/src/types/fault.ts)（与 schema 对齐的后端契约类型）

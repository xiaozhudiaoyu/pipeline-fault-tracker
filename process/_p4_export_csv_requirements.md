# P4 需求文档：故障记录导出 CSV

> 阶段二计划 P4「需求全流程演练」选定功能（用户选定，2026-09-30）。
> 流程：本文档（需求 + 接口边界）先评审 → 后实现 → P1 风格测试 → 约定式小步提交（用户执行）。
> 本文档为 process/ 内部文档，不入交付仓库正式文档体系（与既有 _*_plan.md 同待遇）。

## 1. 需求三要素（规则 2.1）

### 1.1 参考标杆（参照哪个现有实现）

- **后端**：`GET /api/faults` 列表端点（`backend/app/routers/faults.py::list_faults`）——筛选参数形态（`pipeline_id`/`status` 可选查询参数）、错误结构（`ErrorOut`）、crud 分层（router 只收发、业务在 crud）全部照抄该范例；
- **前端**：`frontend/src/api/faults.ts` 既有五个封装函数 + `FaultFilterBar.vue` 的筛选状态（导出复用列表页当前筛选条件）；
- **测试**：`backend/tests/test_api_faults.py` 既有 ASGI 集成测试写法（httpx + 依赖覆盖）。

### 1.2 目标范围

**允许改动**：

- `backend/app/crud.py`（新增导出查询函数）、`backend/app/routers/faults.py`（新增导出端点）；
- `frontend/src/api/faults.ts`（新增导出触发函数）、`frontend/src/views/FaultListView.vue` 及 `frontend/src/components/FaultFilterBar.vue`（加"导出 CSV"按钮）；
- `backend/tests/`（新增测试文件）。

**明确不许动**：

- `models.py`/`schemas.py` 既有模型与迁移文件（导出是只读功能，不改表结构、不改既有响应 schema）；
- 既有五个端点的行为与签名；
- `main.py` 的 lifespan/异常处理器注册（无新增异常类型时）。

### 1.3 具体约束

- 不引入任何新依赖（后端用标准库 `csv` + FastAPI `StreamingResponse`；前端用原生 Blob/anchor 下载）——不触发规则 2.5；
- Python 3.14 / FastAPI 既有版本语法（`X | None` 等跟随现状）；
- 前端 Node 16 兼容（不用新语法）；
- 路由注册顺序：`/export` 必须注册在 `/{fault_id}` **之前**，否则 "export" 被当作 fault_id 匹配（422）——这是本功能最经典的坑，实现与测试都要覆盖。

## 2. 功能描述

列表页提供"导出 CSV"入口：把**当前筛选条件下**（流水线、状态；不含分页，导出全部匹配行）的故障记录导出为 CSV 文件下载。

- 排序与列表一致：`occurred_at` 倒序；
- 时间列（occurred_at/created_at/closed_at）格式 **`YYYY-MM-DD HH:mm:ss`**，与前端列表页展示一致（formatDateTime），Excel 可直接识别；空值导空串。
  （修订 2026-09-30：初版定为 ISO 8601，实现后用户反馈"导出的时间格式不对"——带 "T" 的 ISO 在 Excel 里是纯文本且与页面所见不一致，改为展示同形格式）；
- 导出列（10 列，含冗余流水线编码/名称便于离线阅读）：
  `id, pipeline_code, pipeline_name, location, occurred_at, symptom, status, handling_note, created_at, closed_at`
- 文件编码 UTF-8 **带 BOM**（`utf-8-sig`），保证 Excel 直接双击打开中文不乱码；
- 文件名 `faults_YYYYMMDDHHMMSS.csv`（UTC 时间戳，经 `Content-Disposition` 下发）；
- 安全上限：单次导出最多 **10000 行**，超出仍只导前 10000 行（当前数据量远达不到，属防御性约束）。

## 3. 验收标准（正常 / 异常 / 边界）

**正常**：

1. 无筛选条件导出 → 200，`Content-Type: text/csv`，含表头 + 全部记录行，`occurred_at` 倒序；
2. 带 `pipeline_id`/`status` 筛选导出 → 只含匹配行，口径与列表接口一致；
3. 浏览器下载得到的文件 Excel 打开中文不乱码（BOM 生效）；
4. 前端列表页点击"导出 CSV"→ 触发下载，携带当前筛选条件。

**异常**：

5. 非法 `status`（如 `xxx`）→ 422，响应体为统一 `ErrorOut` 结构；
6. 非法 `pipeline_id`（如 `0`）→ 422 同上；
7. `GET /api/faults/export` 不被 `/{fault_id}` 路由吞掉（回归断言）。

**边界**：

8. 库中零条记录 → 200，CSV 只含表头行（**不视为错误**，见 4.2 决策）；
9. 含逗号/引号/换行的 `symptom`、`handling_note` → CSV 转义正确（`csv` 模块保证）；
10. 行数达到 10000 上限时截断（测试用 mock/构造验证上限逻辑存在即可，不真造一万行）。

## 4. 接口边界（先评审后动手）

### 4.1 端点定义

| 项 | 内容 |
|---|---|
| 端点 | `GET /api/faults/export` |
| 查询参数 | `pipeline_id: int \| None`（ge=1）、`status: FaultStatus \| None` —— 与列表接口完全同形；**无 page/size** |
| 成功响应 | 200，`Content-Type: text/csv; charset=utf-8`；`Content-Disposition: attachment; filename=faults_<ts>.csv`；body 为 CSV 文本流 |
| 实现方式 | `StreamingResponse` + 生成器逐行产出（计划中"流式处理"练习点）：首行表头，之后每行一条记录，避免全量字符串拼接占用内存 |
| 响应模型 | 无 `response_model`（非 JSON）；Swagger 用 `responses={200: {"content": {"text/csv": {}}}}` 标注 |

### 4.2 关键决策点（评审确认项）

- **D1 空结果 → 200 表头 only**（备选：400 export_empty）。取 200：导出是查询的投影，空集是合法结果，前端无需为此写专门错误分支；
- **D2 筛选导出全量匹配行而非"当前页"**：用户直觉是"导出我看到筛选出的这些"，分页是 UI 概念不进导出；
- **D3 前端触发方式 → 构造 URL + 隐藏 `<a>` click**（备选：fetch 拿 Blob 再 objectURL）。取前者：零额外代码、浏览器原生处理下载与文件名；代价是后端 422 时用户看到 JSON 而非弹窗提示——参数合法性已由前端筛选组件保证（下拉/数字输入），实际触发不了 422，可接受；
- **D4 不做导出历史/审计、不做列选择、不做异步大文件导出**（见非目标）。

### 4.3 错误码表

| HTTP | code | 触发条件 |
|---|---|---|
| 422 | validation_error（既有统一结构） | `status` 非法枚举值 / `pipeline_id` < 1 或非整数 |

无 404（空结果不是 404）、无 409（只读操作无状态冲突）、无新增 500 路径。

## 5. 非目标

- 导出 Excel/xlsx、PDF 等其他格式；
- 自定义导出列 / 列顺序；
- 异步导出、大文件分片、导出任务历史；
- 权限控制（本项目当前无认证体系，JWT 是 P4 另一候选未选）；
- 前端测试（阶段二非目标，Vitest 未引入）；
- 数据库结构或既有接口的任何变更。

## 6. 测试计划（P1 风格，进 CI）

新增 `backend/tests/test_api_export.py`（验收标准以 docstring 留在测试内，对应上文 1–10 编号）：

- API 集成层：1/2/5/6/7/8/9（httpx ASGITransport + 既有 conftest 会话覆盖）；
- crud 单元层：导出查询函数的筛选口径与上限截断（10）；
- 边界断言：Content-Type / Content-Disposition / BOM 头字节（3 的后端部分）。

前端验证走手工冒烟（规则 4.1：附验证步骤）：起 dev → 筛选 → 点导出 → Excel 打开核对。

## 7. 提交拆分预告（规则 5.1，用户执行）

1. `feat(backend): 故障记录导出 CSV 端点 + crud 查询`（含测试）；
2. `feat(frontend): 列表页导出 CSV 按钮（携带当前筛选）`。

前后端分两次提交，功能内聚、diff 可独立回溯。

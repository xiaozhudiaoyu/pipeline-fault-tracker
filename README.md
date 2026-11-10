# 流水线故障记录系统（Pipeline Fault Tracker）

> 用于记录和跟踪流水线故障的小型 Web 应用，支持从故障登记、处理跟进到处理完成的基本业务闭环。
> 本项目为 `python_learn` 学习计划的综合小测试。

## 一、技术栈

| 层 | 技术 | 版本（实际验证） |
|---|---|---|
| 前端框架 | Vue 3 + TypeScript | Vue ^3.4（实测 3.4.38）、TS ^5.3（实测 5.3.3） |
| 构建工具 | Vite | ^4.5（实测 4.5.14，Node 16 兼容） |
| 路由 | Vue Router | ^4.2（实测 4.2.5） |
| 数据请求 | TanStack Query (vue-query) | ^4.36（实测 4.36.2） |
| 前端校验 | Zod | ^3.22（实测 3.22.5） |
| UI 组件库 | Element Plus | ^2.5（实测 2.5.6） |
| 后端框架 | FastAPI | ≥0.115（实测 0.141.1） |
| 数据校验 | Pydantic 2 | ≥2.9（实测 2.13.5） |
| ORM | SQLAlchemy 2 | ≥2.0（实测 2.0.54） |
| 数据库 | SQLite | 内置（自动建表） |
| 运行时 | Python 3.14.7 / Node v16.20.2 / npm 8.3.0 | Windows 10 22H2 |

> **版本选择说明**：本机 Node 为 v16.20.2（已于 2023-09 EOL），Vite 5 / TanStack Query v5 / Element Plus 2.7+ 均要求 Node ≥18，故锁定 Vite 4.5 + TanStack Query v4 + Element Plus 2.5 组合。若升级至 Node 20 LTS，可同步升级上述依赖。

## 二、项目结构

```
pipeline-fault-tracker/
├── backend/          # FastAPI + SQLAlchemy 2 + SQLite
│   ├── app/
│   │   ├── main.py / config.py / database.py / models.py
│   │   ├── schemas.py / crud.py / exceptions.py
│   │   └── routers/{pipelines.py, faults.py}
│   ├── seed.py       # 模拟数据脚本
│   ├── pyproject.toml / uv.lock   # 依赖声明（uv 工作流）
│   └── .env.example
├── frontend/         # Vue 3 + TS + Vite + Element Plus
│   ├── src/{api, schemas, types, composables, views, components, router, styles, utils}
│   ├── package.json / package-lock.json
│   ├── vite.config.ts / tsconfig.json
│   └── .env.example
├── DEPENDENCIES.md   # 依赖变更台账
└── README.md         # 本文件
```

## 三、环境准备

> 以下步骤在 **Windows 10 22H2 / PowerShell 5.1** 下实际验证通过。

| 组件 | 要求版本 | 验证命令 |
|---|---|---|
| Python | ≥ 3.11（本项目验证于 3.14.7） | `python --version` |
| uv | ≥ 0.4（本项目验证于 0.12.8，虚拟环境管理工具） | `uv --version` |
| Node.js | ≥ 16（本项目验证于 v16.20.2） | `node --version` |
| npm | ≥ 8 | `npm --version` |
| Git | ≥ 2.20 | `git --version` |

## 四、后端安装与启动

```powershell
cd backend

# 1. 安装依赖（uv sync 按 uv.lock 精确复现；.venv 不存在时自动创建）
uv sync

# 2. 复制配置示例（按需修改端口、DB 路径）
Copy-Item .env.example .env

# 3. 初始化数据库（自动建表 + 写入模拟数据）
.venv\Scripts\python.exe seed.py

# 4. 启动服务（默认 http://127.0.0.1:8000）
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

验证：浏览器打开 `http://127.0.0.1:8000/docs`，应看到 Swagger UI 与全部接口。

## 五、前端安装与启动

```powershell
cd frontend

# 1. 安装依赖（按锁文件精确复现）
npm ci

# 2. 复制配置示例
Copy-Item .env.example .env

# 3. 启动开发服务器（默认 http://127.0.0.1:5173）
npm run dev
```

验证：浏览器打开 `http://127.0.0.1:5173`（`localhost:5173` 亦可，两者均在后端 CORS 白名单），应看到故障列表页（含 seed 写入的模拟数据）。

## 六、基本验证步骤（业务闭环）

1. **列表页**：默认按发生时间倒序展示故障；可用"流水线""状态""优先级"下拉筛选（三者可组合，清空即全部）；列表展示优先级标签（紧急红/普通灰）。
2. **登记故障**：点击"登记故障"→ 填写流水线 / 发生位置 / 发生时间 / 故障现象，并可选优先级（普通/紧急，默认普通）→ 提交；表单有 Zod 前端校验，提交期间按钮 loading 禁用防重复点击。
3. **查看详情**：点击列表任一行进入详情页，展示全部字段（含优先级）、当前状态。
4. **修改优先级**（详情页"修改基础信息"面板的优先级下拉）：改后保存只更新优先级，**不改变处理状态**；成功/失败均有 ElMessage 提示，提交期间按钮禁用。非法取值（直连 API）返回 422 且不落库。
5. **推进状态**（详情页“状态推进”面板按当前状态只渲染合法目标）：
   - 待处理 → 处理中：处理说明可选 → 提交；成功后详情即时刷新，右上角 ElMessage 提示“状态已更新”。
   - 待处理 / 处理中 → 已完成：处理说明**必填**；留空提交时后端返回 400 `handling_note_required`，前端对应字段标红。
   - 已完成（终态）：面板锁定、不再渲染流转表单，提示“该故障已完成（终态），按业务规则不可再流转。”；若绕过前端直接调 API，后端返回 409 `invalid_transition`。（优先级不受终态锁定限制，done 后仍可改。）
6. **导出 CSV**：列表页"导出 CSV"按当前筛选（含优先级）导出全部匹配行，表头含 `priority` 列。
7. **刷新持久化**：刷新页面或重启后端服务，数据与优先级仍在（SQLite 文件落盘）。

## 七、后端接口一览

> 完整交互式文档见 `http://127.0.0.1:8000/docs`（Swagger UI）。所有路径以 `/api` 为前缀；错误响应统一为 `{ code, message, details[] }`。

| 方法 | 路径 | 说明 | 主要错误码 |
|---|---|---|---|
| GET | `/api/pipelines` | 流水线列表（按 code 升序；前端登记/筛选下拉数据源，只读） | — |
| POST | `/api/pipelines` | 新建流水线（前端未接入，供直接调用/扩展） | 409 `pipeline_code_duplicate` |
| GET | `/api/faults` | 故障列表（`pipeline_id`/`status`/`priority` 筛选、`page`/`size` 分页，按发生时间倒序） | 422 参数校验 |
| GET | `/api/faults/export` | 导出 CSV（复用列表筛选口径含 `priority`，不分页，上限 10000 行，UTF-8 带 BOM） | 422 参数校验 |
| GET | `/api/faults/{id}` | 故障详情 | 404 `fault_not_found` |
| POST | `/api/faults` | 登记故障（201 + `Location` 头；occurred_at 不晚于当前时间、symptom 5~1000 字、location 首字符非空白；priority 可选 normal/urgent、默认 normal） | 404 `pipeline_not_found` / 422 |
| PATCH | `/api/faults/{id}` | 修改基础信息（location/symptom/handling_note/priority，部分更新；改 priority 不改状态；前端详情页已接入） | 404 / 409 `handling_note_locked`（done 后说明锁定） / 422 |
| PATCH | `/api/faults/{id}/transition` | 推进状态（pending ↔ processing → done；handling_note 一旦提供 strip 后 ≥5 字） | 400 `handling_note_required` / 404 / 409 `invalid_transition` / 422 |

## 八、配置说明

| 文件 | 作用 |
|---|---|
| `backend/.env.example` | 后端配置模板（DB 路径、CORS 白名单、端口） |
| `frontend/.env.example` | 前端配置模板（`VITE_API_BASE_URL`） |

## 九、依赖管理

- 后端：`pyproject.toml`（声明，`[project].dependencies`）+ `uv.lock`（锁定，`uv lock` 生成，`uv sync` 复现）。
- 前端：`package.json`（声明）+ `package-lock.json`（锁定，`npm install` 生成，`npm ci` 复现）。
- 变更历史与证据见 [DEPENDENCIES.md](./DEPENDENCIES.md)。

## 十、数据库迁移（Alembic）

- 迁移目录 `backend/alembic/`，配置 `backend/alembic.ini`（保持 ASCII-only，中文 Windows 下避免编码坑）。
- **连接串与 app 同源**：`env.py` 从 `app.config.settings` 取 `database_url`，ini 里的 `sqlalchemy.url` 仅是占位；故迁移命令须在 `backend/` 下执行。临时验证可用环境变量 `DATABASE_URL` 覆盖指向其他库文件。
- **SQLite 库文件父目录自动创建**（需求五.4）：把 `DATABASE_URL` 指到带子目录的路径（如 `sqlite:///./data/fault_tracker.db`）时，新解压的项目里还没有该目录，以前 `upgrade head` 会直接报 `unable to open database file`。现在 `app/database.py` 的 `ensure_sqlite_dir()` 会在建 engine 与跑迁移（`env.py` 也调它）前 `mkdir(parents=True)` 兜住，**无需手工建目录**；内存库 `:memory:` 与 PostgreSQL 不涉及此路径。
- **常用命令**（在 `backend/` 下，`.venv\Scripts\python.exe -m alembic ...`）：

  | 命令 | 作用 |
  |---|---|
  | `upgrade head` | 升级到最新版本 |
  | `downgrade -1` | 回退一个版本 |
  | `stamp <rev>` | 给现有库打标记（只写版本号，不执行迁移；老库接入时用） |
  | `history` | 查看迁移链 |
  | `revision -m "..."` | 生成新迁移脚本（`--autogenerate` 自动对比模型与库差异） |

- **`alembic_version` 表的作用**：只有一列一行，记录当前库已应用到哪个版本号；`upgrade`/`downgrade` 靠它判断需要执行哪些迁移脚本，执行后同步更新。
- **现有迁移**：
  - `843f28b00698` baseline —— 手写基线，照抄现有库真实 DDL（autogenerate 对已存在且一致的库产不出 CREATE）；现有库用 `stamp` 打标，空库可由此从零重建。
  - `a74bf448a946` —— 给 `pipeline_faults.occurred_at` 建索引 `ix_pipeline_faults_occurred_at`（列表页倒序排序/时间筛选的查询热点），与 models.py 的 `index=True` 一致。
  - `b3e19c4d7a52` （第二阶段）—— 给 `pipeline_faults` 加 `priority` 列（normal/urgent，默认普通）。旧库升级时采“加列带 server_default='normal'”让存量行自动回填，随后用 `batch_alter_table` 摘掉默认值（SQLite 不支持 `ALTER COLUMN ... DROP DEFAULT`，必须走 batch；PG 上自动退化为普通 ALTER，双方言都能跑）。

### 10.1 空库初始化（全新环境，无旧数据）

> 适用：第一次搭建、或拿到一个空目录。下面命令均在 `backend/` 下执行。

```powershell
cd backend
uv sync                                   # 装依赖（.venv 不存在时自动创建）
Copy-Item .env.example .env               # 配置模板（默认 DATABASE_URL=sqlite:///./fault_tracker.db）
# 确保目标库文件不存在（或是全新空文件）；若已有一份旧库想保留，走 10.2
.venv\Scripts\python.exe -m alembic upgrade head   # 空库从零建到最新结构（含 priority 列）
.venv\Scripts\python.exe seed.py                    # （可选）写入模拟数据
```

`upgrade head` 会依次跑完基线 + 索引 + priority 三个迁移，空库一次到位；此时库内已有 `alembic_version=b3e19c4d7a52`。

### 10.2 旧库升级（已有自动建表产生、无 alembic_version 表的库）

> 适用：上一版项目用 `Base.metadata.create_all()` 自动建表、表里已有故障记录，想接入迁移并升到含优先级的新结构。**不得通过删库/清数据/重录完成**（需求三.3）。

```powershell
cd backend
# 1. 先备份旧库（升级前必做，回退手段）
Copy-Item fault_tracker.db ..\process\fault_tracker.db.bak-p2-<日期>
# 2. 打标：告诉 alembic “此库已在加 priority 前的版本”，只写版本号、不动数据
.venv\Scripts\python.exe -m alembic stamp a74bf448a946
# 3. 升到最新：仅执行差量（加 priority 列），已有故障统一回填 normal
.venv\Scripts\python.exe -m alembic upgrade head
```

升级后验证（不启服务，直接查库）：`pipeline_faults` 多出 `priority` 列且全为 `normal`；原有记录的编号、处理状态、处理说明逐字段不变。若需回退：`alembic downgrade -1` 删列，或用备份文件覆盖回去（数据类变更需单独回数据，代码回退不等于数据恢复）。

> 注：若旧库本身已经是本项目的开发库（已带 `alembic_version=a74bf448a946`，如仓库里的 `fault_tracker.db`），则跳过 `stamp`，直接 `upgrade head` 即可。

> 迁移验证脚本（process/ 不入库）：`verify_p2_migration.py`（空库初始化 + fixture 旧库升级 + downgrade/重升）、`verify_p2_legacy_drill.py`（当前开发库副本的真实升级演练）。

## 十一、已知限制

- 无认证 / 权限系统（需求未要求）。
- 后端测试为分层回归（tests/ 下 schemas/crud/API 三层，`uv run pytest` 执行），列表页操作等界面态验证依赖人工按第六章步骤走查。
- SQLite 单文件数据库，不适用于高并发生产环境。

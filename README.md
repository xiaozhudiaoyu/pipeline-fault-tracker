# 流水线故障记录系统（Pipeline Fault Tracker）

> 用于记录和跟踪流水线故障的小型 Web 应用，支持从故障登记、处理跟进到处理完成的基本业务闭环。
> 本项目为 `python_learn` 学习计划的综合小测试。

## 一、技术栈

| 层 | 技术 | 版本（实际验证） |
|---|---|---|
| 前端框架 | Vue 3 + TypeScript | ^3.4 |
| 构建工具 | Vite | ^4.5（Node 16 兼容） |
| 路由 | Vue Router | ^4.2 |
| 数据请求 | TanStack Query (vue-query) | ^4.36 |
| 前端校验 | Zod | ^3.22 |
| UI 组件库 | Element Plus | ^2.5 |
| 后端框架 | FastAPI | ^0.115 |
| 数据校验 | Pydantic 2 | ^2.9 |
| ORM | SQLAlchemy 2 | ^2.0 |
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
│   ├── requirements.txt / requirements.lock.txt
│   └── .env.example
├── frontend/         # Vue 3 + TS + Vite + Element Plus
│   ├── src/{api, schemas, types, composables, views, components, router, styles}
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
| Node.js | ≥ 16（本项目验证于 v16.20.2） | `node --version` |
| npm | ≥ 8 | `npm --version` |
| Git | ≥ 2.20 | `git --version` |

## 四、后端安装与启动

```powershell
cd backend

# 1. 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. 安装依赖（按锁文件精确复现）
pip install -r requirements.lock.txt

# 3. 复制配置示例（按需修改端口、DB 路径）
Copy-Item .env.example .env

# 4. 初始化数据库（自动建表 + 写入模拟数据）
python seed.py

# 5. 启动服务（默认 http://127.0.0.1:8000）
uvicorn app.main:app --reload --port 8000
```

验证：浏览器打开 `http://127.0.0.1:8000/docs`，应看到 Swagger UI 与全部接口。

## 五、前端安装与启动

```powershell
cd frontend

# 1. 安装依赖（按锁文件精确复现）
npm ci

# 2. 复制配置示例
Copy-Item .env.example .env

# 3. 启动开发服务器（默认 http://localhost:5173）
npm run dev
```

验证：浏览器打开 `http://localhost:5173`，应看到故障列表页（含 seed 写入的模拟数据）。

## 六、基本验证步骤（业务闭环）

1. **列表页**：默认按发生时间倒序展示故障；可用"流水线""状态"下拉筛选。
2. **登记故障**：点击"登记故障"→ 填写流水线 / 发生位置 / 发生时间 / 故障现象 → 提交；表单有 Zod 前端校验，提交期间按钮 loading 禁用防重复点击。
3. **查看详情**：点击列表任一行进入详情页，展示全部字段与当前状态。
4. **推进状态**：
   - 待处理 → 处理中：填写处理说明（可选）→ 提交。
   - 处理中 → 已完成：处理说明**必填** → 提交；完成后状态推进面板禁用，提示"已完成不可变更"。
   - 已完成 → 任何状态：后端返回 422，前端 ElMessage 报错。
5. **刷新持久化**：刷新页面或重启后端服务，数据仍在（SQLite 文件落盘）。

## 七、配置说明

| 文件 | 作用 |
|---|---|
| `backend/.env.example` | 后端配置模板（DB 路径、CORS 白名单、端口） |
| `frontend/.env.example` | 前端配置模板（`VITE_API_BASE_URL`） |

## 八、依赖管理

- 后端：`requirements.txt`（声明）+ `requirements.lock.txt`（锁定，`pip freeze` 生成）。
- 前端：`package.json`（声明）+ `package-lock.json`（锁定，`npm install` 生成，`npm ci` 复现）。
- 变更历史与证据见 [DEPENDENCIES.md](./DEPENDENCIES.md)。

## 九、已知限制

- 无认证 / 权限系统（需求未要求）。
- 无单元测试 / CI（需求未要求；如需补充请单独说明）。
- SQLite 单文件数据库，不适用于高并发生产环境。

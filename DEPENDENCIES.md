# 依赖变更台账（Pipeline Fault Tracker）

> 记录本项目 `backend/.venv` 与 `frontend/node_modules` 的依赖变化。
> 每条均标注证据来源（`dist-info` 时间戳、`pip freeze`、`npm ls`、`package-lock.json`、git 提交），不做推断。
> 维护约定：每次增删依赖后补一节；刷新锁文件时同步更新「时间线总览」。
> 风格参照 `python_learn/DEPENDENCIES.md`（规则 2.6 / 5.3）。

## 一、时间线总览

| 日期时间 | 事件 | 包数变化 | 证据 |
|---|---|---|---|
| _待首次安装后填写_ | backend：`pip install -r requirements.txt`（FastAPI / SQLAlchemy 2 / Pydantic 2 / uvicorn 链） | 0 → N | `dist-info` 时间戳 + `pip freeze` |
| _待首次安装后填写_ | frontend：`npm install`（Vue 3.4 / Vite 4.5 / Element Plus 2.5 / TanStack Query v4 / Zod 3 链） | 0 → M | `package-lock.json` + `npm ls --depth=0` |

## 二、版本锁定决策（2026-09-18）

### 背景

本机 Node 为 **v16.20.2**（2023-09 EOL），无法支撑 Vite 5 / TanStack Query v5 / Element Plus 2.7+（均要求 Node ≥18）。经用户确认，采用 **Node 16 兼容版本组合**，不升级 Node。

### 锁定清单（frontend）

| 包 | 锁定版本范围 | 理由 |
|---|---|---|
| vue | ^3.4（<3.5） | Vue 3.5 起倾向 Node 18+ |
| vite | ^4.5（<5.0） | Vite 5 要求 Node ^18 \|\| >=20 |
| @vitejs/plugin-vue | ^4.6 | 配套 Vite 4 |
| vue-router | ^4.2 | Vue 3 配套 |
| element-plus | ^2.5（<2.7） | 2.7+ 要求 Node 18+ |
| @tanstack/vue-query | ^4.36（<5.0） | v5 要求 Node ≥18 |
| zod | ^3.22 | 纯 TS，无 Node 版本硬约束 |
| typescript | ^5.3 | Vite 4 配套 |
| vue-tsc | ^1.8 | Vue 3.4 配套 |

### 锁定清单（backend）

| 包 | 锁定版本范围 | 理由 |
|---|---|---|
| fastapi | 最新稳定 | Python 3.14 兼容（python_learn 已验证） |
| uvicorn[standard] | 最新稳定 | 含 watchfiles / httptools，`--reload` 硬需求 |
| sqlalchemy | >=2.0 | 需求文档指定 SQLAlchemy 2 |
| pydantic | >=2.0 | 需求文档指定 Pydantic 2 |
| pydantic-settings | 最新稳定 | 从 .env 读配置 |
| python-dotenv | 最新稳定 | pydantic-settings 传递依赖，显式声明 |

> 具体版本号在首次 `pip install` / `npm install` 后，由 `pip freeze` 与 `package-lock.json` 固化，并回填到本台账与 `requirements.lock.txt`。

## 三、待补章节（安装后填写）

- [ ] backend 首批安装：包数、`dist-info` 时间戳、`pip freeze` 快照、`pip check` 结果
- [ ] frontend 首批安装：包数、`npm ls --depth=0` 快照、`package-lock.json` 提交哈希
- [ ] 锁文件生成：`requirements.lock.txt` / `package-lock.json` 的生成命令与提交
- [ ] 后续任何增删：按 python_learn 台账风格逐节记录

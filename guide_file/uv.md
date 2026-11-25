# uv 完整使用文档

> 适用版本：**uv 0.12.8**（本机 2026-09-22 实测，`uv --version` 可自查；本文子命令清单以该版本 `uv --help` 为准）。
> 定位：uv 全工作流教程 + 本项目 `pipeline-fault-tracker` 的 uv 实战（D4 迁移成果）。WSL 内用法见 [wsl.md](wsl.md)。
> 可信度标注：「实测」= 本项目 D4 迁移与日常使用中验证；其余为 uv 官方文档行为。
> 与计划对应：[process/_next_week_plan.md](../process/_next_week_plan.md) 的 D4「环境管理：用 uv 重建 backend 环境」。

---

## 目录

1. [核心概念](#一核心概念)
2. [安装与升级](#二安装与升级)
3. [虚拟环境管理 uv venv](#三虚拟环境管理-uv-venv)
4. [pip 兼容接口 uv pip](#四pip-兼容接口-uv-pip)
5. [项目工作流 pyprojecttoml--uvlock](#五项目工作流-pyprojecttoml--uvlock)
6. [Python 版本管理 uv python](#六python-版本管理-uv-python)
7. [工具安装 uv tool / uvx](#七工具安装-uv-tool--uvx)
8. [缓存与清理 uv cache](#八缓存与清理-uv-cache)
9. [本项目实战（D4 成果解读）](#九本项目实战d4-成果解读)
10. [坑点汇总](#十坑点汇总)
11. [命令速查表](#十一命令速查表)

---

## 一、核心概念

### 1.1 uv 是什么

uv 是 Astral（Ruff 作者）用 Rust 写的 **Python 包与环境管理器**，一个二进制覆盖传统工具链的多个角色：

| 传统工具 | uv 对应 |
|---|---|
| `python -m venv` + 手动装 Python | `uv venv` + `uv python install` |
| `pip install` / `pip freeze` | `uv pip`（兼容接口） |
| `requirements.txt` + 手写锁定 | `pyproject.toml` 声明 + `uv.lock` 锁定 |
| `poetry` / `pipenv` 的工作流 | `uv init` / `uv add` / `uv sync` / `uv run` |
| `pipx` | `uv tool` / `uvx` |

### 1.2 解决什么问题

- **快**：Rust 实现 + 并行下载 + 全局缓存，实测安装 24 项依赖比 pip 快一个量级；
- **锁文件跨平台**：`uv.lock` 同时锁定 Linux / Windows / macOS 三平台解析结果（含 `uvloop` 这类 Linux-only extra），同一份锁在 Windows 与 WSL 里 `uv sync` 得到一致环境——这正是本项目 D4→D5 迁移到 uv 的动机；
- **一个工具管全生命周期**：装 Python、建环境、装依赖、跑命令、锁版本，不需要记忆多套工具语法。

### 1.3 uv vs pip+venv vs poetry

| | pip + venv | poetry | uv |
|---|---|---|---|
| 速度 | 慢 | 中 | 快（Rust/并行） |
| 锁文件 | 需手动 pip freeze | poetry.lock（单平台倾向） | uv.lock（跨平台原生） |
| 环境管理 | 手动 | 内置 | 内置 + 可下载 Python |
| 安装方式 | Python 自带 | pip 安装 | 独立二进制 |
| 本项目选型 | D4 之前 | 未用 | **D4 起（本项目标准）** |

---

## 二、安装与升级

### 2.1 Windows（PowerShell）

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装到 `%USERPROFILE%\.local\bin`，重开终端生效。

### 2.2 Linux / WSL（bash，本项目实测）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"   # 当前终端立即生效（重开终端可免）
```

### 2.3 升级与自管理

```powershell
uv self update       # 升级 uv 自身
```

### 2.4 验证（实测输出）

```
$ uv --version
uv 0.12.8 (68209e5c6 2026-08-31 x86_64-pc-windows-msvc)
```

---

## 三、虚拟环境管理 `uv venv`

### 3.1 创建

```powershell
uv venv .venv                 # 在项目内创建 .venv
uv venv .venv --python 3.12   # 指定 Python 版本（不存在会自动下载）
uv venv --python pypy3.10     # 指定解释器实现
```

### 3.2 激活（可选）

```powershell
.venv\Scripts\activate        # Windows PowerShell
```

```bash
source .venv/bin/activate     # Linux / WSL
```

### 3.3 免激活哲学：优先用 `uv run`

uv 工作流下**无需激活**：`uv run` 自动在项目环境里执行命令（见 5.5）。本项目实测两种方式等价：

```bash
uv run uvicorn app.main:app --reload              # uv 方式（推荐，免激活）
.venv/bin/python -m uvicorn app.main:app --reload # 等价的传统方式
```

---

## 四、pip 兼容接口 `uv pip`

> 迁移期与临时操作使用；新项目优先用第五节的项目工作流。

```powershell
uv pip install fastapi             # 装包（写入当前环境）
uv pip install -r requirements.lock.txt   # 按 pip freeze 锁文件精确复现（D4 实测）
uv pip freeze > out.txt            # 导出当前环境
uv pip check                       # 依赖完整性校验（D4 实测通过）
uv pip list                        # 列出环境内包
uv pip uninstall fastapi           # 卸载
uv pip compile requirements.in     # 生成锁文件（pip-tools 的 compile 角色）
```

**本项目 D4 实测**：`uv pip install -r requirements.lock.txt` 装 24 项，与旧 pip 锁逐项一致，`uv pip check` 通过——这是从 pip 迁到 uv 的第一阶段验证（后续再迁到 pyproject 工作流）。

---

## 五、项目工作流 `pyproject.toml` + `uv.lock`

### 5.1 `uv init` 创建项目

```powershell
uv init my-project           # 生成 pyproject.toml、.python-version、README 等
```

### 5.2 `uv add` / `uv remove` 增删依赖

```powershell
uv add fastapi                       # 加到 [project].dependencies 并同步锁文件
uv add --dev pytest                  # 加到 [dependency-groups].dev
uv add "fastapi>=0.115"              # 带版本约束
uv remove fastapi                    # 移除
```

**纪律**：加依赖只用 `uv add`（自动改声明 + 锁文件 + 环境），不要手改 pyproject.toml 再手动 sync（易造成声明与锁文件不一致）。

### 5.3 `uv lock` 锁定

```powershell
uv lock                              # 解析依赖并写 uv.lock
uv lock --upgrade-package watchfiles # 单包升级（规则 3.5：一次只升一个）
```

`uv.lock` 内容解读（本项目实测经验）：

- 条目数 ≠ `pip freeze` 行数——uv 用连字符规范化包名、含项目自身条目、纳入跨平台 extra（如 `uvloop` 仅在 Linux 装）；
- 比对两套锁文件时**逐项映射**，不要直接比条数（D4 迁移时 26 vs 24 的差异就是这样逐项查清的）。

### 5.4 `uv sync` 同步环境

```powershell
uv sync                  # 按 uv.lock 精确复现（.venv 不存在自动创建；实测）
uv sync --frozen         # 不重新解析，锁文件不一致时直接报错（CI 推荐）
uv sync --dev            # 含 dev 依赖组
```

### 5.5 `uv run` 在项目环境内执行

```powershell
uv run python script.py          # 跑脚本
uv run uvicorn app.main:app --reload   # 本项目 backend 启动（Windows/WSL 通用，实测）
uv run -- python -c "..."        # -- 后的参数原样传给命令
```

### 5.6 `uv tree` 依赖树

```powershell
uv tree                    # 展示项目依赖树（谁引入谁）
uv tree --depth 2

# 1. 进入你的项目后端目录（Linux 路径）
cd /home/xiaozhu/pipeline-fault-tracker/backend

# 2. 确认 pyproject.toml 存在
ls -a

# 3. 再执行 uv 命令
uv tree
```

### 5.7 `uv export` 导出锁文件

```powershell
uv export --format requirements-txt -o requirements.txt   # 供非 uv 环境使用
```

---

## 六、Python 版本管理 `uv python`

```powershell
uv python install 3.12        # 安装托管 Python（免官网下载，实测失败兜底用）
uv python list                # 列出已装与可装的 Python
uv python pin 3.12            # 写入 .python-version（本项目此文件内容为 3.14）
uv python find                # 解析当前项目用哪个 Python
uv python uninstall 3.12      # 卸载
```

**用途**：`uv sync` 时按 `.python-version` 找解释器；系统没有对应版本时 uv 自动下载托管 Python，无需手动装。

---

## 七、工具安装 `uv tool` / `uvx`

```powershell
uv tool install ruff          # 全局安装 CLI 工具（隔离环境）
uv tool list                  # 列出已装工具
uv tool uninstall ruff
uvx ruff check .              # 临时运行（用完即弃，不落盘）
```

**纪律**（规则 2.5）：临时排障工具优先用 `uvx`（不残留）；常驻工具用 `uv tool install` 并登记台账。

---

## 八、缓存与清理 `uv cache`

```powershell
uv cache dir                  # 缓存目录位置
uv cache clean                # 清空缓存
uv cache prune                # 只清未引用的缓存
```

全局选项：`--offline`（离线模式）、`--no-cache`、`--verbose, -v`、`--project <目录>`（非项目目录下指定项目）。

---

## 九、本项目实战（D4 成果解读）

### 9.1 项目文件结构

| 文件 | 作用 |
|---|---|
| `backend/pyproject.toml` | 依赖声明（下界范围）+ uv 配置 |
| `backend/uv.lock` | 跨平台锁定（Windows 与 WSL 同一份） |
| `backend/.python-version` | 锁定 Python 3.14 |

### 9.2 `backend/pyproject.toml` 关键配置解读（代码已证实）

```toml
[project]
requires-python = ">=3.11"
dependencies = ["fastapi>=0.115", "uvicorn[standard]>=0.30", ...]

[tool.uv]
package = false        # 应用项目：不构建、不分发
constraint-dependencies = ["watchfiles==1.2.0"]
```

- **只写下界、精确版本交给锁文件**：声明保持可读，`uv lock`/`uv sync` 保证复现；
- **`package = false`**：本项目是应用不是库，跳过打包语义；
- **`constraint-dependencies` 钉死 watchfiles==1.2.0**：迁移时 `uv lock` 把传递依赖抬到 1.3.0，为保持「迁移零漂移」钉回原版本（实测 `Updated watchfiles v1.3.0 -> v1.2.0`）；将来升级 watchfiles 时移除该约束单独走一次提交（规则 3.5）。

### 9.3 迁移过程要点（D4 实测）

1. 删旧 `.venv` → `uv venv` → `uv pip install -r requirements.lock.txt`，24 项逐项一致，`uv pip check` 通过；
2. 迁移到 pyproject 工作流后，`uv.lock` 与旧 pip 锁逐项映射比对（连字符规范化 / 项目条目 / uvloop Linux-only 三类差异），仅 watchfiles 有实质漂移并钉回；
3. 里程碑打附注标签：`pre-uv-migration`（迁移前 80068fd）、`post-uv-migration`（迁移后 22eb762），供 git 历史回溯；
4. **位置选择**：pyproject.toml 放 `backend/` 下而非仓库根——根目录 `.gitignore` 有对 `/pyproject.toml`、`/uv.lock` 的忽略规则，放 backend/ 规避（`git check-ignore` 实测为空）。

### 9.4 日常命令（Windows 与 WSL 完全一致）

```bash
cd backend && uv sync                                  # 装依赖（按锁复现）
cd backend && uv run uvicorn app.main:app --reload     # 起服务（8000）
cd backend && uv run alembic upgrade head              # 数据库迁移
cd backend && uv pip check                             # 环境体检
```

---

## 十、坑点汇总

| # | 现象 | 原因 | 规避 |
|---|---|---|---|
| 1 | `uv sync` 卡在构建 watchfiles | watchfiles==1.2.0（2022 年）无 Python 3.14 轮子 | uv 会尝试自动构建（实测 Windows/WSL 均一次通过）；失败则 `uv python install 3.12` 降版本 |
| 2 | `uv.lock` 条数与 pip 锁对不上 | 连字符规范化 + 项目自身条目 + 跨平台 extra | 逐项映射比对，不比条数 |
| 3 | 迁移时传递依赖被偷偷升级 | `uv lock` 按当前 PyPI 解析 | `[tool.uv] constraint-dependencies` 钉回；升级单独走提交 |
| 4 | 「接口 200」误判为新环境跑通 | 旧进程仍占着 8000 端口在响应 | 先查端口归属，或换端口启动并在自己服务日志里确认收到请求（D4 实测踩过） |
| 5 | 手改 pyproject.toml 后锁文件失同步 | 声明与锁文件是两份文件 | 依赖增删一律 `uv add` / `uv remove` |
| 6 | PowerShell 中文路径传参乱码 | 编码问题（与本项目 WSL 部署同源） | 先 `cd` 再用相对路径，详见 [wsl.md](wsl.md) 3.5 |
| 7 | 不激活 venv 也能跑？ | `uv run` 自动定位项目环境 | 两者等价；CI/脚本场景统一用 `uv run` |

---

## 十一、命令速查表

### 高频命令

```powershell
uv --version                  # 版本
uv venv .venv                 # 建环境
uv sync                       # 按锁同步（本项目装依赖标准动作）
uv add fastapi / uv remove fastapi     # 增删依赖
uv lock --upgrade-package <包>         # 单包升级
uv run <命令>                 # 环境内执行（本项目起服务标准动作）
uv pip check                  # 依赖体检
uv python install 3.12        # 装 Python
uv tool install <工具> / uvx <工具>    # 工具安装 / 临时运行
uv cache clean                # 清缓存
uv self update                # 升 uv
```

### 本项目速查

| 场景 | 命令 |
|---|---|
| 装 backend 依赖 | `cd backend && uv sync` |
| 起 backend | `cd backend && uv run uvicorn app.main:app --reload` |
| 数据库迁移 | `cd backend && uv run alembic upgrade head` |
| 环境体检 | `cd backend && uv pip check` |
| 验证服务 | `curl.exe -s http://localhost:8000/api/faults`（Windows）/ `curl -s http://127.0.0.1:8000/api/faults`（WSL） |

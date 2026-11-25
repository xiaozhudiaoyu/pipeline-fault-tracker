# GitHub Actions 完整使用文档（通用教程手册 + 项目实战）

> 适用版本：以 **GitHub Actions 官方文档**（docs.github.com/actions，2026-09）为基准整理；文中常用 action 的主版本均为**当轮逐一核实**：`actions/checkout@v7`、`actions/setup-node@v6`、`actions/setup-python@v5`、`actions/cache@v4`、`astral-sh/setup-uv@v9.0.0`（核实来源见 4.3 节表格）。
> 定位：**通用教程手册 + 本项目实战（第十三节）**——第一~十二节为不绑定项目的概念与语法大全；第十三节把本项目（pipeline-fault-tracker）的 CI 方案按当前代码事实整理为可执行示例。
> 可信度标注：「实测」= 本机执行验证过。第一~十二节内容基于官方文档与官方 changelog 整理、未逐一实测；第十三节本项目 CI 已落地 `.github/workflows/ci.yml`（2026-09-29），三条验证命令本地实测全绿（backend `uv run pytest` 72 用例通过、frontend `type-check` 无错误、`build` 退出码 0）；**尚未 push 触发 Actions 首跑**，CI 端到端（runner 上装依赖、缓存、双 job 并行）仍属「待验证」。
> 执行位置约定：workflow 运行在 **GitHub 托管 runner**（远端 Linux VM）上，不依赖本机环境；本地调试用 `act`（见第十节），本机已具备其依赖（WSL 内 Docker，见 [docker.md](docker.md) 12.2）。PowerShell 命令仅用于本地 git 操作与 act 调用。

---

## 目录

1. [核心概念](#一核心概念)
2. [触发方式（Events）](#二触发方式events)
3. [Workflow 语法与结构](#三workflow-语法与结构)
4. [Actions 生态与常用 Action](#四actions-生态与常用-action)
5. [环境变量与密钥](#五环境变量与密钥)
6. [缓存与依赖加速](#六缓存与依赖加速)
7. [矩阵策略与并发控制](#七矩阵策略与并发控制)
8. [制品、发布与部署](#八制品发布与部署)
9. [权限与安全](#九权限与安全)
10. [调试与排障](#十调试与排障)
11. [计费与配额](#十一计费与配额)
12. [坑点汇总](#十二坑点汇总)
13. [本项目实战（pipeline-fault-tracker）](#十三本项目实战pipeline-fault-tracker)
14. [速查表](#十四速查表)

---

## 一、核心概念

### 1.1 六个基础对象

| 对象 | 是什么 | 类比 |
|---|---|---|
| **Workflow（工作流）** | 一个 YAML 文件描述的自动化流程，由事件触发 | 一条 CI 流水线定义 |
| **Event（事件）** | 触发 workflow 的仓库活动：push、PR、定时、手动 | 触发器 |
| **Job（作业）** | workflow 内的执行单元，跑在一台独立 Runner 上；多个 job 默认并行 | 流水线的一段 |
| **Step（步骤）** | job 内的顺序执行单元：执行命令（`run`）或调用 action（`uses`） | 一段内的单个动作 |
| **Action（动作）** | 可复用的执行单元，官方/社区提供 | npm 包 |
| **Runner（运行器）** | 实际执行 job 的机器（GitHub 托管 VM 或自托管） | 执行环境 |

### 1.2 执行模型

```
事件（push / PR / 定时 / 手动）
   │ 触发
   ▼
workflow（.github/workflows/*.yml）
   ├─ job A：step 1 → step 2 → step 3   ← 独立 VM，默认并行
   └─ job B：step 1 → step 2            ← 独立 VM，默认并行
```

三个关键推论（与本地脚本思维最大的差异）：

- **job 之间互不共享**：每个 job 跑在独立的干净 VM 上，文件系统、内存互不相通；job 之间传数据只能靠制品（artifacts，第八节）或缓存（第六节）；
- **同一 job 内 steps 共享**：steps 顺序执行，共享同一个工作目录（`$GITHUB_WORKSPACE`，`actions/checkout` 之后即仓库代码）与进程环境；
- **每次运行从零开始**：VM 不保留上次运行的状态，持久化只能靠缓存/制品/外部存储。

### 1.3 与本地脚本的关系

workflow 本质上就是「在干净的远程 Linux/Windows/macOS 机器上，按你写的步骤执行命令」。本地 `dev.bat`、`seed.py` 里的操作搬到 runner 上就是一条条 `run` 步骤；不同点仅是：环境要现场装（Node、Python、依赖），以及用 YAML 声明而非脚本顺序。

---

## 二、触发方式（Events）

### 2.1 代码事件：push / pull_request

```yaml
on:
  push:
    branches: [main]              # 只监听 main 分支的推送
  pull_request:
    branches: [main]              # 只监听合入 main 的 PR
```

路径过滤（大仓库减少无谓运行）：

```yaml
on:
  push:
    paths: ['backend/**']          # 只有 backend 目录变更才触发
  pull_request:
    paths-ignore: ['docs/**', '*.md']   # 文档变更不触发
```

- `branches` / `branches-ignore`、`paths` / `paths-ignore` 均支持通配符 `*` / `**`；
- 同一事件里 `branches` 与 `branches-ignore` 不能同时出现（paths 同理）；
- push 到 PR 源分支会同时触发 `push` 与 `pull_request` 两个事件 → 常用 `paths` 或忽略 `push` 规避重复运行。

### 2.2 定时任务：schedule

```yaml
on:
  schedule:
    - cron: '0 16 * * 1'    # 每周一 16:00（UTC）
```

- cron 为五段式：`分 时 日 月 周`；
- **时区是 UTC**（北京时间 = UTC + 8，`0 16 * * 1` 即北京周二凌晨 0 点）；
- 定时任务**只在默认分支**（main/master）的 workflow 文件上运行；
- 仓库 60 天无任何活动时，定时任务会被 GitHub 自动禁用。

### 2.3 手动触发：workflow_dispatch

```yaml
on:
  workflow_dispatch:
    inputs:
      env:
        description: '部署环境'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]
```

- 需 workflow 文件在**默认分支**上，Actions 页面才会出现「Run workflow」按钮；
- `inputs` 在运行里通过 `${{ inputs.env }}` 读取。

### 2.4 复用与联动：workflow_call / workflow_run

- `workflow_call`：供其他 workflow 像函数一样调用（`uses: ./.github/workflows/build.yml`），可声明 `inputs` / `outputs` / `secrets` 参数；
- `workflow_run`：**另一个 workflow 运行完成后**触发本 workflow——fork PR 安全两段式（先跑检查、再触发有权限的后置任务）的标准做法。

### 2.5 其他常用事件

| 事件 | 用途 |
|---|---|
| `release` / `release: published` | 打 release 后自动构建/发布 |
| `issues` / `issue_comment` | issue 自动化 |
| `repository_dispatch` | 外部系统经 API 触发 |
| `merge_group` | merge queue（合并队列） |

---

## 三、Workflow 语法与结构

### 3.1 文件位置与最小骨架

workflow 文件放在 `.github/workflows/*.yml`（可多个，互不干扰）：

```yaml
name: CI                       # workflow 显示名（可省略，缺省用文件名）

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest     # 运行平台：ubuntu-latest / windows-latest / macos-latest
    steps:
      - uses: actions/checkout@v7          # 检出代码到工作目录
      - name: 安装依赖                      # run 步骤显示名（可省略）
        run: npm ci
      - name: 执行检查
        run: npm run type-check
```

### 3.2 键速览

| 键 | 层级 | 作用 |
|---|---|---|
| `name` / `run-name` | workflow | 显示名 / 运行名模板 |
| `on` | workflow | 触发事件（见第二节） |
| `permissions` | workflow / job | 声明 `GITHUB_TOKEN` 权限（见 9.1） |
| `env` | workflow / job / step | 环境变量（见 5.1） |
| `defaults.run` | workflow / job | 默认 shell 与工作目录 |
| `jobs.<job_id>` | job | 作业定义，job_id 自定义 |
| `runs-on` | job | runner 平台 |
| `needs` | job | 依赖其他 job（先完成才启动） |
| `strategy` | job | 矩阵 / 并发控制（见第七节） |
| `timeout-minutes` | job / step | 超时（默认 job 360 分钟） |
| `steps` | job | 步骤列表 |
| `uses` / `run` / `with` / `if` | step | 调 action / 跑命令 / 传参数 / 条件 |

### 3.3 上下文与表达式

表达式写在 `${{ }}` 里，运行前由 GitHub 求值：

```yaml
- name: 打印分支名
  run: echo "当前分支 ${{ github.ref }}，SHA ${{ github.sha }}"
```

| 常用上下文 | 内容 |
|---|---|
| `github` | 事件相关：`github.ref`（分支/标签）、`github.sha`、`github.event_name`、`github.actor`、`github.repository` |
| `env` | 环境变量（见第五节） |
| `secrets` / `vars` | 密钥 / 变量 |
| `matrix` / `strategy` | 矩阵组合值 |
| `inputs` | workflow_dispatch / workflow_call 的入参 |
| `steps` / `needs` | 步骤 / 上游 job 的输出 |
| `runner` | runner 信息：`runner.os`（Linux/Windows/macOS）、`runner.arch` |

| 常用函数 | 示例 |
|---|---|
| `contains(list, item)` | `contains(github.ref, 'refs/tags/')` |
| `startsWith` / `endsWith` | `startsWith(github.ref, 'refs/tags/')` |
| `format()` | `format('v{0}', 1)` |
| `join()` / `toJSON()` / `fromJSON()` | 数组拼接 / 转 JSON / 解析 JSON |
| `hashFiles('**/package-lock.json')` | 文件内容哈希（缓存 key 常用，见 6.1） |

### 3.4 条件 if 与状态函数

```yaml
steps:
  - name: 仅标签推送时执行
    if: startsWith(github.ref, 'refs/tags/')
    run: ./deploy.sh
  - name: 失败时通知
    if: failure()
    run: echo "构建挂了"
```

| 状态函数 | 何时为真 |
|---|---|
| `success()` | 此前步骤全部成功（`if` 缺省即此项） |
| `failure()` | 此前任一步骤失败 |
| `always()` | 无条件（含被取消时也执行） |
| `cancelled()` | 运行被取消 |

### 3.5 YAML 三大坑（Actions 专属）

- **`on` 是 YAML 1.1 的布尔值**：`on: [push]` 会先被解析成布尔再处理——数组写法没问题，但 `on: ${{ ... }}` 这类写法会被判非法；键名后必须跟冒号加空格（`on:`），不能写成 `on :`;
- **字符串值含特殊字符要加引号**：`*`、`{`、`}`、`:`、`-` 开头的值必须引号包裹，例如 `run: echo "a*b"`、`node-version: "16.20.2"`；
- **缩进是结构**：一律空格（不用 Tab），层级用两空格递进；`steps:` 下的 `-` 与 `uses`/`run` 缩进对齐错误是最常见的新手报错。

---

## 四、Actions 生态与常用 Action

### 4.1 Action 的三种形态

| 形态 | 实现 | 特点 |
|---|---|---|
| JavaScript action | Node 脚本 | 快、跨平台，官方 action 多用 |
| Docker action | 容器镜像 | 环境自包含，只能跑 Linux |
| Composite action | 组合既有步骤 | 只是 workflow 片段的「函数化」，最易上手 |

### 4.2 引用语法与版本固定

```yaml
- uses: actions/checkout@v7          # 官方 action，用主版本移动标签
- uses: docker/build-push-action@v6   # 第三方 action（建议固定 SHA，见 9.3）
- uses: ./github/actions/my-action    # 本仓库自研 composite action（相对路径）
```

`@` 后面可以是 tag（`@v7`）、commit SHA（`@3d3c42e...`）或分支名。**tag 会移动**（v7 指向的内容随发布更新），供应链安全要求第三方 action 固定到 commit SHA（见 9.3）。

### 4.3 常用官方 Action（版本为 2026-09 核实基线）

| Action | 用途 | 当前主版本 |
|---|---|---|
| `actions/checkout` | 检出代码 | v7（2026-07 发布 v7.0.1） |
| `actions/setup-node` | 安装 Node + npm 缓存 | v6 |
| `actions/setup-python` | 安装 Python + pip 缓存 | v5 |
| `astral-sh/setup-uv` | 安装 uv（含 Python 管理 + 缓存） | v9.0.0（无裸主版本标签，钉完整 semver） |
| `actions/cache` | 通用文件缓存 | v4 |
| `actions/upload-artifact` / `download-artifact` | 制品上传 / 下载 | v4 |
| `actions/configure-pages` / `deploy-pages` | GitHub Pages 部署 | 官方配套 |
| `docker/login-action` / `build-push-action` | 登录 registry / 构建推送镜像 | 以官方 README 为准 |

### 4.4 自研 composite action 示例

`./.github/actions/setup-backend/action.yml`：

```yaml
name: setup-backend
description: 安装 uv 与后端依赖（项目自研片段）
runs:
  using: composite
  steps:
    - uses: astral-sh/setup-uv@v9.0.0
      with:
        python-version: "3.14"
        working-directory: backend
    - run: uv sync --frozen
      shell: bash
      working-directory: backend
```

调用方：`- uses: ./.github/actions/setup-backend`。composite action 适合把多项目共用的步骤序列收拢成一行。

---

## 五、环境变量与密钥

### 5.1 env 三级作用域

```yaml
env:                       # workflow 级：所有 job 可见
  NODE_ENV: production

jobs:
  build:
    env:                   # job 级：覆盖 workflow 级
      NODE_ENV: test
    steps:
      - run: echo $NODE_ENV
        env:               # step 级：仅本步可见
          NODE_ENV: ci
```

优先级：step > job > workflow。**后写覆盖先写**，不能在同一层级合并追加。

### 5.2 内置默认环境变量（节选）

| 变量 | 内容 |
|---|---|
| `GITHUB_WORKSPACE` | runner 上的工作目录（checkout 后即仓库根） |
| `GITHUB_SHA` / `GITHUB_REF` | 触发提交 SHA / 分支或标签引用 |
| `GITHUB_EVENT_NAME` | 事件名（push / pull_request / …） |
| `GITHUB_ACTOR` | 触发者用户名 |
| `GITHUB_RUN_ID` / `GITHUB_RUN_NUMBER` | 本次运行 ID / 序号 |
| `RUNNER_OS` | runner 系统（Linux / Windows / macOS） |
| `CI` | 恒为 `true`（可据此在代码里切换行为） |

### 5.3 Secrets 与 Variables

- **Secrets**：敏感数据（token、密码）。在仓库 Settings → Secrets and variables → Actions 添加；用 `${{ secrets.NAME }}` 引用；日志中会被自动打码；
- **Variables**：非敏感配置（如部署环境名），用 `${{ vars.NAME }}` 引用；
- 也可建在**环境（Environment）**与**组织**层级，作用域逐步收窄（见 8.4）。

**Secrets 的两条硬限制**：

1. 不能直接写进 `if:` 条件——先中转成环境变量：
   ```yaml
   jobs:
     build:
       env:
         HAS_TOKEN: ${{ secrets.MY_TOKEN != '' }}
       steps:
         - if: env.HAS_TOKEN == 'true'
           run: ./deploy.sh
   ```
2. **fork 仓库的 PR 拿不到 secrets**（`pull_request` 事件中 `secrets` 不可用，`GITHUB_TOKEN` 只读）——安全设计，规避方式见 9.2。

### 5.4 GITHUB_TOKEN 与 permissions

每个 job 自动注入 `GITHUB_TOKEN`（挂在 `secrets.GITHUB_TOKEN`），无需手动创建；其**默认权限取决于仓库/组织的 Actions 设置**（默认通常可读可写）。推荐在 workflow 顶部显式声明最小权限：

```yaml
permissions:
  contents: read          # 只读代码（checkout 的最低要求）
```

需要 push、发 PR、推镜像等写操作时按需放宽（见 8.2 / 9.1）。

---

## 六、缓存与依赖加速

### 6.1 actions/cache 基础

```yaml
- uses: actions/cache@v4
  with:
    path: |
      ~/.cache/pip
      .venv
    key: ${{ runner.os }}-py-${{ hashFiles('backend/uv.lock') }}
    restore-keys: |
      ${{ runner.os }}-py-
```

语义（务必理解）：

- 查找顺序：**当前分支**精确 `key` → 当前分支 `restore-keys` 前缀（取最新一条）→ 默认分支同样的查找；
- `hashFiles` 把锁文件内容参与 key：依赖不变则缓存命中，依赖一变 key 失效自动重建；
- 未命中时 job 结束后会把 `path` 内容存为新缓存条目；
- 作用域：缓存条目**属于当前分支**，其他分支用不上（除非走 `restore-keys` 回退）。

### 6.2 setup-node 内置缓存

```yaml
- uses: actions/setup-node@v6
  with:
    node-version: "16.20.2"
    cache: npm                         # 自动解析锁文件做 key（替代手写 cache）
    cache-dependency-path: frontend/package-lock.json   # 锁文件不在根目录时必填
```

`cache: npm` 等价于按 `package-lock.json` 哈希缓存 `~/.npm`，比手写 `actions/cache` 少两行且不会写错路径。

### 6.3 uv 项目缓存（setup-uv）

```yaml
- uses: astral-sh/setup-uv@v9.0.0
  with:
    python-version: "3.14"
    working-directory: backend
    # enable-cache 缺省为 auto：检测到 uv.lock/pyproject.toml 自动缓存
    # cache-dependency-glob 缺省已覆盖 **/uv.lock 与 **/pyproject.toml，无需手配
```

`setup-uv` 会缓存 uv 二进制、Python 解释器与 `.venv` 依赖，连续运行显著提速；参数细节以 action 官方 README 为准（v8 起停止发布裸主版本移动标签、改为不可变 semver 发布，故钉完整版本如 v9.0.0；2026-09-29 经 `git ls-remote --tags` 实测：标签止于 v9.0.0，无 v10）。

### 6.4 缓存限制与回收

- 仓库缓存总量上限 **10 GB**（Free 计划），超出后最旧条目被回收；
- 单条缓存 **7 天未被访问**会被自动删除；
- 缓存命中≠加速：npm 官方建议对缓存条目设版本上限，避免无界膨胀。

---

## 七、矩阵策略与并发控制

### 7.1 matrix 基础

```yaml
strategy:
  matrix:
    node: [16, 18, 20]        # 3 种组合，生成 3 个并行 job
```

```yaml
strategy:
  matrix:
    python-version: ["3.11", "3.12", "3.14"]
steps:
  - uses: actions/setup-python@v5
    with:
      python-version: ${{ matrix.python-version }}
```

### 7.2 include / exclude / fail-fast

```yaml
strategy:
  fail-fast: true            # 缺省 true：任一组合失败，取消其余组合
  max-parallel: 4            # 限制同时并行的组合数
  matrix:
    os: [ubuntu-latest, windows-latest]
    node: [18, 20]
    include:                 # 追加额外组合（可含新键）
      - os: ubuntu-latest
        node: 16
    exclude:                 # 剔除不需要的组合
      - os: windows-latest
        node: 18
```

### 7.3 concurrency 并发组

```yaml
concurrency:
  group: ci-${{ github.ref }}       # 同一分支的运行为一组
  cancel-in-progress: true          # 新运行进来时取消旧运行
```

用途：防止同一分支的旧运行与新提交的运行同时执行（部署场景尤其重要——两个运行同时操作同一资源会互相覆盖）。

---

## 八、制品、发布与部署

### 8.1 Artifacts（job 间传文件 + 留存产物）

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: frontend-dist
    path: frontend/dist/        # 文件或目录
    retention-days: 7           # 保留天数（缺省 90，最多 90）
```

```yaml
- uses: actions/download-artifact@v4
  with:
    name: frontend-dist
    path: ./dist
```

- 制品用于 job 间传文件、下载构建产物、附加到运行详情页；
- v4 起同一运行内**同名重复上传会报错**（v3 是静默覆盖）——多 job 上传同名制品时需各自用不同 name。

### 8.2 GitHub Release

```yaml
- name: 创建 Release
  run: gh release create v1.0.0 --generate-notes   # runner 自带 gh CLI，自动用 GITHUB_TOKEN 鉴权
```

或第三方 action（如 `softprops/action-gh-release`，需固定 SHA 使用，见 9.3）。触发事件通常写 `on: release: types: [published]`。

### 8.3 GitHub Pages

```yaml
permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/configure-pages@v5
      - run: npm ci && npm run build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: dist
      - id: deployment
        uses: actions/deploy-pages@v4
```

（以上 action 小版本以官方 Pages 文档为准；仓库须先在 Settings → Pages 里把 Source 切到 GitHub Actions。）

### 8.4 Environments（环境）与保护规则

- 在仓库 Settings → Environments 创建环境（如 `production`）；
- 可配置：**人工审批（required reviewers）**、环境专属 secrets/variables、部署分支限制；
- workflow 引用：`jobs.<id>.environment: production`——该 job 只会拿到该环境的 secrets。

---

## 九、权限与安全

### 9.1 permissions 最小权限

```yaml
permissions:
  contents: read
```

- `contents: read` 足够 checkout 与只读操作；`contents: write` 才允许 push / 提 PR；
- 推镜像加 `packages: write`；Pages 部署加 `pages: write` + `id-token: write`；
- 写权限只授给真正需要的 job，不要图省事全开。

### 9.2 pull_request_target 的风险与安全写法

- `pull_request_target` 的运行**发生在目标分支上下文**（有 secrets、有写权限），但 PR 里的代码是**外部提交者可控的**——若直接 checkout PR 代码再执行，等于把 secrets 交给陌生人；
- 安全两段式：用 `pull_request` 跑不受信任的 PR 代码（无 secrets）→ 完成后用 `workflow_run` 触发有权限的后置任务；
- 2026-06-18 起 `actions/checkout` 在 `pull_request_target` 下的默认行为收紧（v6.1.0 起拒绝不安全检出 PR 代码），老教程里的写法已不适用，以官方 changelog 为准。

### 9.3 第三方 action 供应链安全

- **2025-03 案例**：`tj-actions/changed-files` 被投毒（tag 被篡改指向恶意代码），大量用 `@v45` 这类 tag 的项目集体中招；
- 规范：第三方 action 固定 **commit SHA**：`uses: tj-actions/changed-files@2d756ea4c53f7f6e397136d91a3b1b46f76be577`，再以注释标注版本号；
- 官方 `actions/*` 仓库同样建议固定 SHA（或至少锁主版本）；引入前审阅 action 的权限声明与代码。

### 9.4 自托管 runner 风险

- 自托管 runner 上，**同仓库任何分支的 PR 代码都能在 runner 机器上执行**——相当于任何能提 PR 的人都获得了 runner 机器的执行权；
- 若必须自托管：用临时性 runner（跑完销毁）、放隔离网络、绝不放生产凭据；注意自托管 runner 自 2026-03-01 起按用量计费（见 11.2）。

---

## 十、调试与排障

### 10.1 运行页操作

- **Rerun jobs**：失败后重跑全部或**只重跑失败的 job**（在失败的 job 上 Re-run failed jobs）；
- **Enable debug logging**：重跑时勾选，会打印大量内部日志（含敏感步骤的更多细节，注意别在公开仓库随意开启）；
- 每个 step 可展开看原始日志；运行摘要页可下载所有日志。

### 10.2 workflow 命令

在 `run` 步骤里往 stdout 打印特殊格式即可干预运行：

| 命令 | 效果 |
|---|---|
| `echo "::error::后端启动失败"` | 步骤标记为失败并显示消息 |
| `echo "::warning::缓存未命中"` | 显示警告（不失败） |
| `echo "::notice::提示信息"` | 显示提示 |
| `echo "::group::安装依赖"` / `echo "::endgroup::"` | 折叠日志分组 |
| `echo "mykey=myval" >> $GITHUB_OUTPUT` | 步骤输出（旧 `::set-output::` 已废弃） |
| `echo "MSG=hello" >> $GITHUB_ENV` | 后续步骤可用的环境变量 |

### 10.3 act 本地调试

[nektos/act](https://github.com/nektos/act) 在本地用 Docker 模拟运行 workflow，**不用 push 到 GitHub**：

```powershell
# 本机已有 WSL 内 Docker（docker.md 12.2），act 装进 WSL 内运行
wsl -e bash -c "curl -sSL https://raw.githubusercontent.com/nektos/act/master/install.sh | bash"
wsl -e bash -c "act pull_request --list"     # 列出本地所有 workflow 的 job
wsl -e bash -c "act -j backend"              # 只跑 backend job
```

局限（官方文档明示）：不能 100% 复现云端环境——默认镜像比 GitHub runner 精简（可用 `--platform ubuntu-latest=ghcr.io/catthehacker/ubuntu:act-latest` 逼近）、无 secrets（用 `.secrets` 文件或 `-s` 传入）、定时/权限等平台行为不一致。**本机未实测**，属「方案待验证」。

### 10.4 常见失败速查

| 现象 | 原因与修法 |
|---|---|
| `403 Forbidden` | permissions 不足——按 9.1 放宽对应权限 |
| YAML 语法错误（运行直接不启动） | 检查缩进 / `on:` 冒号空格 / 特殊字符引号（3.5） |
| `Unable to resolve action` | action 名或版本写错、私有仓库跨仓引用需 PAT |
| 本地能跑、CI 上 Node/Python 版本不对 | 未显式指定版本，用了 runner 默认（见坑点 11） |
| 定时任务不触发 | 只在默认分支生效 + cron 是 UTC（2.2） |
| 缓存永远不命中 | key 计算包含会变的输入；路径写错（6.1） |

---

## 十一、计费与配额

### 11.1 免费额度（Free 计划，2026-09 核实）

- **公共仓库**：GitHub 托管 runner 无限免费；
- **私有仓库**：每月 **2000 分钟**（GitHub-hosted runner）+ 制品/缓存存储额度；
- 本项目（pipeline-fault-tracker）为私有仓库，即受 2000 分钟/月约束——双 job 的轻量 CI 每次运行约 1~2 分钟，月内个人迭代完全够用。

### 11.2 计费乘数与自托管收费

| Runner | 分钟乘数 |
|---|---|
| Linux | ×1 |
| Windows | ×2 |
| macOS | ×10 |

- 自托管 runner：2026-03-01 起按 **$0.002/分钟** 计费（官方 changelog 2025-12-16），不再是免费替代品。

### 11.3 主要硬限制

| 项 | 限制 |
|---|---|
| 单 job 超时 | 360 分钟（可 `timeout-minutes` 调小，不能调大） |
| 单 workflow 运行总时长 | 72 小时 |
| 缓存总量 | 10 GB / 仓库 |
| 制品保留 | 最多 90 天 |
| 并发 job 数（Free） | 20 |

---

## 十二、坑点汇总

1. **`on` 是 YAML 布尔值**：`on: [push]` 合法，但 `on: ${{ ... }}` 报错；键名后冒号必须跟空格（见 3.5）。
2. **cron 是 UTC 且只在默认分支**：`0 16 * * 1` 不是北京时间周一 16 点（见 2.2）。
3. **secrets 不能直接用于 `if:`**：先经 `env` 中转（见 5.3）。
4. **fork PR 拿不到 secrets**：`pull_request` 事件下 `secrets` 不可用、`GITHUB_TOKEN` 只读；别指望在 fork PR 里做发布。
5. **`pull_request_target` 是安全陷阱**：在目标分支上下文跑外部代码，等于交出 secrets；且 checkout 2026-06 起默认行为已收紧，老教程写法失效（见 9.2）。
6. **第三方 action 用移动 tag 有供应链风险**：2025-03 tj-actions 投毒事件；固定 commit SHA（见 9.3）。
7. **`ubuntu-latest` 是移动标签**：2026-10-19 起 x64 从 Ubuntu 24.04 迁到 26.04（runner-images issue #14748）；在意稳定性的项目固化为 `ubuntu-24.04`。
8. **缓存默认只在当前分支命中**：跨分支复用需 `restore-keys`（见 6.1）。
9. **upload-artifact v4 同名冲突**：多 job 上传同名制品直接报错（v3 是覆盖），起名要区分（见 8.1）。
10. **不显式指定 Node/Python 版本会用 runner 默认**：runner 2026-06-16 起默认 Node 24，老项目（如本项目 Node 16）必须经 setup-node 显式安装指定版本。
11. **定时任务 60 天无活动被禁用**：长期不动的仓库 schedule 会停摆（见 2.2）。
12. **`${{ }}` 字面量输出需转义**：`run: echo '${{ github.ref }}'`（单引号包裹）或 `${{ '${{' }}` 才能打印原文。
13. **GITHUB_TOKEN 默认权限可能过大**：仓库设置不同默认不同；养成显式 `permissions: contents: read` 的习惯（见 9.1）。
14. **部署场景必须用 concurrency**：同资源并发部署互相覆盖，加 `concurrency` + `cancel-in-progress`（见 7.3）。
15. **Windows runner 的 shell 是 PowerShell**：`run` 默认 shell 依平台而变（Linux= bash，Windows= PowerShell），跨平台脚本要么显式 `shell: bash`，要么按平台分叉。

---

## 十三、本项目实战（pipeline-fault-tracker）

> 本节按**当前项目事实**（2026-09-29 核查）给出本仓库的 CI 方案。产物文件 `.github/workflows/ci.yml` **已落地**（独立提交 `chore(ci):`），13.4 即仓库实际内容；本地三条验证命令已实测全绿，尚待 push 触发 Actions 首跑。

### 13.1 现状基线与目标

| 项 | 结论 | 证据 |
|---|---|---|
| 远程仓库 | `git@github.com:WSD2007zhuchangle/pipeline-fault-tracker.git`（私有） | `git remote -v`（2026-09-23） |
| Actions 现状 | 已落地 `.github/workflows/ci.yml`（双 job）；尚未 push 触发首跑 | 仓库结构（2026-09-29） |
| 后端 | Python 3.14 + uv 工作流（`pyproject.toml` + `uv.lock`）；dev 组含 `pytest>=9.1.1` / `httpx>=0.28.1`；`tests/` 四层 72 用例，本地 `uv run pytest` 全绿 | `backend/pyproject.toml` / `backend/tests/`（提交 `d8f7f35`） |
| 前端 | Node 16.20.2 锁定（`dev.bat` 用 `nvm use 16.20.2`）；npm（有 `package-lock.json`）；检查手段 `npm run type-check`（vue-tsc）+ `npm run build`（vite）；本地均实测通过 | `frontend/dev.bat` / `frontend/package.json` |
| Node 16 可用性 | setup-node 的 versions-manifest 仍含 16.20.2（stable），CI 可显式安装 | `actions/node-versions` manifest（2026-09 核实） |

- **目标**：push 到 `main` 与开 PR 时自动跑双 job——backend 装依赖 + `uv run pytest`（四层测试）；frontend 装依赖 + 类型检查 + 构建；
- **非目标**：自动部署/CD、镜像推送、docker build 第三 job（可选扩展见 13.5）。

### 13.2 backend job 设计说明

- 用 `astral-sh/setup-uv@v9.0.0` 而非 `setup-python`：项目是 uv 工作流，锁文件复现依赖必须走 `uv sync --frozen`；`uv sync` 默认安装 dev 依赖组，pytest/httpx 随之就绪；
- `working-directory: backend` 让 setup-uv 在 `backend/` 下解析 `pyproject.toml` / `.python-version`；`python-version: "3.14"` 显式钉版，uv 会按需自动下载 CPython 3.14；
- 验证手段为 `uv run pytest`：P1 已落地四层测试（schemas 单元 / crud 单元 / API 集成 / 错误路径，72 用例），API 集成层经 ASGI 走完整请求链路，已覆盖旧的「导入检查 + 启动冒烟」，故不再单列冒烟步骤。

### 13.3 frontend job 设计说明

- `node-version: "16.20.2"` 必须显式写：runner 默认 Node 已是 24（坑点 10），不写则 `npm ci` 环境与本地不一致；
- `cache: npm` + `cache-dependency-path: frontend/package-lock.json`：锁文件在子目录，不指路径缓存会永远 miss；
- `npm ci` 按锁文件干净安装（比 `npm install` 严格，CI 标准做法）；随后 `type-check` 与 `build` 即本项目现有的全部前端验证手段。

### 13.4 完整示例：`.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v7

      - name: 安装 uv 与 Python 3.14
        uses: astral-sh/setup-uv@v9.0.0
        with:
          python-version: "3.14"
          working-directory: backend

      - name: 安装依赖（uv 锁文件复现，含 dev 组 pytest/httpx）
        run: uv sync --frozen

      - name: 运行测试（四层：schemas/crud/API 集成/错误路径）
        run: uv run pytest

  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-node@v6
        with:
          node-version: "16.20.2"
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: 安装依赖
        run: npm ci

      - name: 类型检查
        run: npm run type-check

      - name: 构建
        run: npm run build
```

### 13.5 可选扩展（后续按需再加，当前不做）

- **定时巡检**：加 `schedule` 每周跑一次，顺带规避「60 天无活动定时禁用」（坑点 11）；
- **镜像构建推送 ghcr**：`docker/login-action` + `docker/build-push-action`（配合 docker.md 12.4/12.5 的 Dockerfile），需 `permissions: packages: write`；私有仓库的 ghcr 托管在免费用量内；
- **依赖更新**：开启 Dependabot 自动提 PR（workflow 会随之自动跑 CI 验证更新）。

### 13.6 落地与验证步骤

1. ✅ 已创建 `.github/workflows/ci.yml`（内容即 13.4）；
2. ✅ 本地实测三条验证命令全绿：`uv run pytest`（72 passed）、`npm run type-check`（无错误）、`npm run build`（退出码 0）；
3. ⏳ 独立提交（`chore(ci):`，与功能改动分离）后 `git push`，到 Actions 页面观察首次运行：两个 job 并行、各步骤绿色即通过；
4. ⏳ 开一个 PR 验证 `pull_request` 触发；本地可先经 act 演练（见 10.3，本机未实测）；
5. ⏳ 红-绿闭环演练：故意提交类型错误 → CI 变红 → 修复 → 变绿（`_phase2_plan.md` P2 验收项）；
6. 首跑通过后，顶部可信度标注的 CI「待验证」状态升级为「实测」。

---

## 十四、速查表

### 14.1 常用上下文 / 函数

| 表达式 | 含义 |
|---|---|
| `${{ github.ref }}` | 当前分支/标签引用 |
| `${{ github.sha }}` | 触发提交 SHA |
| `${{ github.event_name }}` | 事件名 |
| `${{ secrets.X }}` / `${{ vars.X }}` | 密钥 / 变量 |
| `${{ matrix.os }}` | 矩阵当前组合值 |
| `${{ runner.os }}` | runner 系统 |
| `${{ hashFiles('**/uv.lock') }}` | 锁文件哈希（缓存 key） |
| `${{ steps.<id>.outputs.<key> }}` | 某步骤的输出 |
| `${{ needs.<job_id>.result }}` | 上游 job 结果（success/failure） |

### 14.2 常用 Action（2026-09 版本基线）

| Action | 版本 | 用途 |
|---|---|---|
| `actions/checkout` | v7 | 检出代码 |
| `actions/setup-node` | v6 | Node + npm 缓存 |
| `actions/setup-python` | v5 | Python + pip 缓存 |
| `astral-sh/setup-uv` | v9.0.0 | uv + Python + 缓存 |
| `actions/cache` | v4 | 通用缓存 |
| `actions/upload-artifact` / `download-artifact` | v4 | 制品 |
| `actions/configure-pages` / `upload-pages-artifact` / `deploy-pages` | 官方配套 | Pages 部署 |

### 14.3 常用 workflow 命令

| 命令 | 效果 |
|---|---|
| `::error::msg` / `::warning::msg` / `::notice::msg` | 失败 / 警告 / 提示 |
| `::group::name` / `::endgroup::` | 折叠日志 |
| `>> $GITHUB_OUTPUT` | 步骤输出 |
| `>> $GITHUB_ENV` | 设置后续步骤环境变量 |

### 14.4 最小可运行 workflow（复制即用）

```yaml
name: hello
on: [push, pull_request]
permissions:
  contents: read
jobs:
  hello:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - run: echo "Hello from GitHub Actions"
```

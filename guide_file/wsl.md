# WSL 完整使用文档

> 适用环境：Windows 10/11 + WSL2 + Ubuntu 26.04.1 LTS（本项目于 2026-09-22 D5 练习中实测）。
> 定位：通用 WSL 概念 + 本项目 `pipeline-fault-tracker` 在 WSL 内的完整部署实操。纯命令速查见 [wsl-commands.md](wsl-commands.md)（命令参考手册，与本文分工）。
> 可信度标注：标「实测」的命令均在本机验证通过（结果附在预期输出中）；未标注的为 WSL 官方标准行为。
> 与计划对应：[process/_next_week_plan.md](../process/_next_week_plan.md) 的 D5「工程化：WSL / Linux 下跑通前后端」——验收标准：WSL 下两服务均启动、`curl` 验证通过；能用 Linux 命令完成查看/停止进程。

---

## 目录

1. [核心概念](#一核心概念)
2. [安装与初始化](#二安装与初始化)
3. [Windows ↔ WSL 文件系统互访](#三windows--wsl-文件系统互访)
4. [Windows ↔ WSL 网络与端口转发](#四windows--wsl-网络与端口转发)
5. [PATH 互通与常见污染](#五path-互通与常见污染)
6. [本项目在 WSL 的完整部署（D5 实操手册）](#六本项目在-wsl-的完整部署d5-实操手册)
7. [坑点汇总](#七坑点汇总)
8. [命令速查表](#八命令速查表)
9. [日常开发工作流建议](#九日常开发工作流建议)

---

## 一、核心概念

### 1.1 WSL 解决什么问题

WSL（Windows Subsystem for Linux）让 Windows 上直接运行 Linux 用户态环境，免装双系统/虚拟机。对开发者意味着：

- 用 Linux 原生命令（`ls` / `ps` / `kill` / `curl` / `grep`）而不是 PowerShell；
- 开发环境贴近 Linux 部署环境（本项目部署目标是 Linux 服务器，见 D5 目标）；
- 与 Windows 文件、工具、浏览器互通（`/mnt/...` 互访、`localhost` 端口转发）。

### 1.2 WSL1 与 WSL2

| | WSL1 | WSL2（本项目使用） |
|---|---|---|
| 架构 | 系统调用翻译层（无 Linux 内核） | 轻量虚拟机 + 完整 Linux 内核 |
| 系统调用兼容性 | 不完全（部分内核特性不支持） | 完整 |
| 跨文件系统 IO（访问 `/mnt/...`） | 快 | 慢（9P 协议） |
| 发行版内 IO（ext4） | — | 接近原生 Linux 速度 |
| 内存模型 | 共享 Windows 内存 | 独立 VM，按需伸缩 |

结论：**开发文件放 WSL 内部（ext4）跑得飞快；频繁跨系统读大文件会拖慢**——这正是本项目把代码复制进 WSL 家目录的原因（见第三节）。

### 1.3 本项目为何引入 WSL

呼应阶段评估反馈「Agent 更擅长 Linux、WSL 贴近部署环境」：在 WSL 内用纯 Linux 命令完成「装依赖 → 起服务 → 验证 → 看进程/停进程」全流程，与 D4（uv 环境管理）衔接，为将来 Docker 化打底。

---

## 二、安装与初始化

### 2.1 安装（管理员 PowerShell，一次性）

```powershell
wsl --install          # 默认安装 WSL2 + Ubuntu 发行版
# 或指定发行版：
wsl --install -d Ubuntu
```

安装后**按提示重启 Windows**。旧系统需先启用虚拟机平台：控制面板 → 启用或关闭 Windows 功能 → 勾选「适用于 Linux 的 Windows 子系统」和「虚拟机平台」。

### 2.2 查看状态

```powershell
wsl --list --verbose   # 列出所有发行版：名称 / 状态 / WSL 版本
wsl --status           # 查看默认版本与内核版本
```

实测输出（本机）：

```
  NAME      STATE           VERSION
* Ubuntu    Stopped         2
```

- `*` = 默认发行版；`Stopped` = 未在运行（任何 wsl 命令会自动拉起）；
- `VERSION 2` = WSL2。若显示 1，执行 `wsl --set-version Ubuntu 2` 升级。

### 2.3 常用管理命令

```powershell
wsl --set-default Ubuntu            # 设默认发行版
wsl --set-default-version 2         # 新装发行版默认用 WSL2
wsl --shutdown                      # 关闭整个 WSL VM（释放内存，所有发行版停止）
wsl --terminate Ubuntu              # 只停止指定发行版
wsl -u root                         # 以 root 身份进入（免 sudo 密码，安装软件用）
wsl -e bash -c '<命令>'             # 不进交互式 shell，直接执行一条命令
wsl --export Ubuntu d:\ubuntu.tar   # 备份发行版
wsl --import Ubuntu2 d:\wsl2 d:\ubuntu.tar   # 从备份恢复
```

---

## 三、Windows ↔ WSL 文件系统互访

### 3.1 WSL 看 Windows：`/mnt/...`

Windows 各盘符挂载在 WSL 内：

```bash
ls /mnt/c    # C 盘
ls /mnt/e    # E 盘（本项目所在盘）
```

### 3.2 Windows 看 WSL：`\\wsl$`

在 Windows 资源管理器或 PowerShell 里：

```powershell
explorer \\wsl$\Ubuntu\home\xiaozhu     # 浏览 WSL 家目录
```

其中 `xiaozhu` 是 WSL 内的用户名，用 `whoami` 查看。

### 3.3 性能差异与放置原则

- `/mnt/e`（NTFS 挂载）上的文件读写走 9P 协议跨虚拟机，比 ext4 慢一个数量级；
- 实测对比：`npm ci` 在 WSL 家目录 ext4 上 17 秒完成 75 个包；在 `/mnt/e` 上会显著变慢且易出权限/软链报错；
- **Windows 装的 `node_modules` / `.venv` 不能跨系统复用**：esbuild 等原生二进制按平台编译，Windows 版在 Linux 跑不了（报错 `Cannot find module` 或 exec format error）。

**原则：项目代码放进 WSL 家目录（ext4），Windows 侧保留原副本，两边通过 git 同步（见第九节）。**

### 3.4 本项目复制命令（实测）

先在 PowerShell 里 `cd` 到项目根目录（**必须先 cd，原因见 3.5**）：

```powershell
cd e:\python项目\pipeline-fault-tracker
wsl -e bash -c 'mkdir -p ~/pipeline-fault-tracker && rsync -a --no-perms --no-owner --no-group --exclude=node_modules --exclude=.venv --exclude=dist --exclude=__pycache__ --exclude=.idea ./ ~/pipeline-fault-tracker/ && echo "RSYNC_OK" && du -sh ~/pipeline-fault-tracker && ls ~/pipeline-fault-tracker'
```


实测输出：

```
RSYNC_OK
2.4M    /home/xiaozhu/pipeline-fault-tracker
DEPENDENCIES.md  README.md  backend  frontend  guide_file  process
```

要点：

- `--exclude` 排除的五个目录要么体积巨大（`node_modules`），要么是 Windows 平台产物（`.venv` / `dist` / `__pycache__`），要么无关（`.idea`）；
- `--no-perms --no-owner --no-group`：NTFS → ext4 跨文件系统复制时不照搬权限/属主，避免元数据警告；
- `.git` 和 `fault_tracker.db` **保留**：前者用于在 WSL 内继续 git 操作，后者让 WSL 内首次启动就有数据可验证。

python_learn项目：

```powershell
robocopy E:\python_learn \\wsl.localhost\Ubuntu\home\xiaozhu\projects\python_learn `
  /E `
  /XD guide_file process sqlalchemy_learn .venv __pycache__ .idea `
  /XF uv.lock
```
```powershell
robocopy E:\python_learn \\wsl.localhost\Ubuntu\home\xiaozhu\projects\python_learn /E /XD guide_file process sqlalchemy_learn .venv __pycache__ .idea /XF uv.lock
```

说明：
- 行尾的反引号 ` 是 PowerShell 的续行符，必须紧跟在内容后面、下一行前不能有多余字符
- /XD 后跟多个目录名即可排除多个目录，这里同时排除了你要的三个目录，以及沿用上次建议的 .venv、__pycache__、.idea
- /XD 用目录名（非完整路径）时会匹配任意层级下的同名目录；若只想排除项目根目录下的这几个，可写完整路径，例如 /XD E:\python_learn\guide_file 
  E:\python_learn\process 
  E:\python_learn\sqlalchemy_learn
- /XF uv.lock 为可选排除项，不需要可整行删掉

### 3.5 中文路径坑（实测）

**现象**：在传给 `wsl.exe` 的命令字符串里直接写含中文的 Windows 路径（如 `e:\python项目\...`），WSL 侧报「目录不存在」。

**原因**：PowerShell 5.1 把参数按 GBK 编码传给 `wsl.exe`，非 ASCII 字符在传输中乱码（已写入长期记忆）。

**规避**：命令字符串里**不出现任何中文路径**——先在 PowerShell 侧 `cd` 进目标目录再启动 `wsl`；WSL 会把 Windows 当前目录自动挂载为 bash 的 cwd，bash 内一律用 `./` 相对路径。

---

## 四、Windows ↔ WSL 网络与端口转发

### 4.1 原理：localhostForwarding（默认开启）

WSL2 默认启用 `localhostForwarding`：**Windows 侧访问 `localhost:<端口>` 会被自动转发到 WSL 内监听同端口的服务**，反之亦然。因此：

- WSL 里起 uvicorn（127.0.0.1:8000）→ Windows 浏览器直接开 `http://localhost:8000`；
- Windows 起的服务 → WSL 内 `curl localhost:<端口>` 同样可达。

### 4.2 验证方法（实测）

后端与前端分别在 WSL 内跑起来后，回到 PowerShell（不经 WSL）：

```powershell
curl.exe -s http://localhost:8000/api/faults   # 预期：200 + 故障 JSON
curl.exe -s http://localhost:5173/             # 预期：返回 index.html
```

浏览器打开 `http://localhost:5173` 应能看到故障列表页面。

**坑点**：PowerShell 里必须写 `curl.exe`——裸写 `curl` 是 `Invoke-WebRequest` 的别名，参数语义不同。

### 4.3 关闭端口转发

在 `C:\Users\<用户名>\.wslconfig` 中加入：

```ini
[wsl2]
localhostForwarding=false
```

关闭后 Windows 无法经 `localhost` 直达 WSL 服务，需改走 WSL 的 IP（`wsl hostname -I` 查看）。本项目联调依赖 localhost 转发，**勿关**。

### 4.4 本项目端口约定（与代码对齐）

| 服务 | 地址 | 来源 |
|---|---|---|
| backend | `http://127.0.0.1:8000` | `backend/app/config.py` 默认值（host=127.0.0.1, port=8000） |
| frontend dev | `http://127.0.0.1:5173` | `frontend/vite.config.ts`（host 与 port 均写死） |
| CORS 白名单 | `http://localhost:5173`、`http://127.0.0.1:5173` | `backend/app/config.py` 的 `cors_origins` |

**为什么 5173 不能变**：vite 在 5173 被占用时会自动退避到 5174，而 5174 不在后端 CORS 白名单内，浏览器端所有请求被拦（已写入长期记忆）。起前端前先确认 5173 空闲。

---

## 五、PATH 互通与常见污染

### 5.1 appendWindowsPath 机制

WSL 默认把 Windows 的 PATH 追加到 Linux PATH 之后（`/etc/wsl.conf` 的 `appendWindowsPath`，默认 true）。好处是能在 Linux 里调 `notepad.exe`、`code` 等 Windows 程序；坏处是 **Windows 侧同名工具会混入 Linux 环境**。

### 5.2 本项目实测污染实例

部署 WSL 环境时出现：`which npm` 指向 `/mnt/d/nodejs/npm`（Windows 装的 Node），而 `node` 报 `command not found`、npm 报 `Cannot find module 'E:\node_modules\npm\...'`。

**原因**：Windows 的 Node 目录混进了 Linux PATH，但 Windows 版 npm 脚本在 Linux 下无法执行。

**解决**：用 apt 安装 Linux 版 nodejs 后，`/usr/bin/node` 优先级更高，问题消失（见 6.4）。排查手段：

```bash
which node npm          # 看解析到哪个路径
echo $PATH | tr ':' '\n' | grep -iE 'node|npm'
```

### 5.3 彻底关闭互通 PATH

编辑 `/etc/wsl.conf`：

```ini
[interop]
appendWindowsPath=false
```

保存后 `wsl --terminate Ubuntu` 重启生效。本项目开发需用 `code .`、`explorer.exe .` 等 Windows 程序，保留默认即可，遇冲突时用 5.2 的排查思路。

---

## 六、本项目在 WSL 的完整部署（D5 实操手册）

> 本节为 D5 验收的完整命令清单。标注「PowerShell」在 Windows 终端执行，标注「bash」在 WSL 内执行。依赖安装均按既有锁文件复现（后端 `uv.lock`、前端 `package-lock.json`），不引入新依赖。

### 6.1 前置条件

- 已完成 D4（项目迁移到 uv 工作流，`backend/pyproject.toml` + `uv.lock` 已提交）；
- WSL2 + Ubuntu 可用（`wsl --list --verbose` 显示 VERSION 2）；
- Windows 侧项目位于 `e:\python项目\pipeline-fault-tracker`。

### 6.2 Step 1：检查 WSL（PowerShell）

```powershell
wsl --list --verbose
```

预期：`Ubuntu ... 2`。若不存在见 2.1。

### 6.3 Step 2：复制项目进 WSL（PowerShell）

见 3.4 完整命令，预期 `2.4M` 复制完成。

### 6.4 Step 3：安装 Node.js（PowerShell，root 免交互）

```powershell
wsl -u root -e bash -c 'apt-get update -qq && apt-get install -y -qq nodejs npm && node --version && npm --version'
```

实测输出：`v22.22.1` / `9.2.0`（满足 `frontend/package.json` 的 `engines: node >= 16` 与 vite 4.5）。

**为什么这样装**：

- `-u root`：WSL 普通用户 sudo 需交互输密码，root 免交互；
- apt 官方源而非 NodeSource/nvm：版本够用且最省事；nvm 用于需要多版本切换的场景。

**推荐用 nvm 管理版本，完美适配前端开发（bash）：**

```bash
# 1. 安装 nvm（若提示 curl 不存在，先 sudo apt update && sudo apt install curl）
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# 重新加载配置（或重开终端）
source ~/.bashrc
# 2. 安装最新稳定版 Node（会自动配好 npm）
nvm install --lts
# 3. 验证
node -v
npm -v
```

### 6.5 Step 4：安装 uv 并同步 backend 依赖（bash）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"     # 当前终端立即生效（重开终端可免）
uv --version

cd ~/pipeline-fault-tracker/backend
uv sync
```

预期：创建 `.venv`，按 `uv.lock` 装好 fastapi / uvicorn / sqlalchemy / alembic（实测一次成功）。

**坑点预警**：`pyproject.toml` 约束 `watchfiles==1.2.0`（2022 年的包），Python 3.14 下无预编译轮子，uv 会尝试自动构建；若报构建错误，备选方案是 `uv python install 3.12` 后以 3.12 重建 `.venv`。

### 6.6 Step 5：安装 frontend 依赖（bash）

```bash
cd ~/pipeline-fault-tracker/frontend && npm ci --no-audit --no-fund
```

实测输出：`added 75 packages in 17s`。

- `npm ci` 严格按 `package-lock.json` 复现（先清空 node_modules），等价于后端的 `uv sync`；`npm install` 则可能顺手更新 lock 文件，复现环境禁用；
- 必须在 ext4 家目录里跑（见 3.3）。

### 6.7 Step 6：启动 backend（bash，终端 A）

```bash
cd ~/pipeline-fault-tracker/backend
uv run uvicorn app.main:app --reload
```

预期：`Uvicorn running on http://127.0.0.1:8000`。此命令与 Windows 侧 `dev.bat` 一致（`-m uvicorn app.main:app --reload`），只是把「venv 里的 python」换成 `uv run`。

### 6.8 Step 7：curl 验证 backend（bash，另开终端 B）

```powershell
wsl     # 再开一个终端进入 WSL
```

```bash
curl -s http://127.0.0.1:8000/api/faults
```

预期：200 + 故障列表 JSON（数据来自复制过去的 `fault_tracker.db`）。

### 6.9 Step 8：启动 frontend（bash，另开终端 C）

```bash
cd ~/pipeline-fault-tracker/frontend
npm run dev
```

预期：`VITE ready`，`Local: http://127.0.0.1:5173/`（端口写死在 `vite.config.ts`，见 4.4）。

### 6.10 Step 9：curl 验证 frontend（bash）

```bash
curl -s http://127.0.0.1:5173/ | head -20
```

预期：返回 `index.html` 源码。

### 6.11 Step 10：Windows 侧验证端口转发（PowerShell）

见 4.2 两条 `curl.exe` 命令 + 浏览器开 `http://localhost:5173`。

### 6.12 Step 11：进程查看与停止（bash，验收项）

```bash
ps aux | grep -E 'uvicorn|vite' | grep -v grep
```

实测输出（列序 `USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND`，**第 2 列即 PID**）：

```
xiaozhu  990  ...  uv run uvicorn app.main:app --reload     ← 主进程（看门）
xiaozhu  993  ...  .venv/bin/python ... uvicorn --reload    ← worker（干活）
xiaozhu 1039  ...  sh -c vite                                ← npm 包装 shell
xiaozhu 1040  ...  node .../.bin/vite                        ← 真正的 vite 进程
```

停止方式（两选一）：

```bash
kill 990       # 停 backend：主进程退出，worker 993 被带走
kill 1040      # 停 frontend：node 退出，sh 包装随之退出
# 或回到各服务所在终端按 Ctrl+C（更优雅）
```

验收闭环：`ps` 复查为空 + `curl` 对应端口连接失败。

**知识点**：`--reload` 模式是「父进程看门 + 子进程干活」，父进程发现代码变化就杀掉子进程重新拉起，所以 uvicorn 永远两个进程；`npm run dev` 多一层 `sh -c` 包装同理。

---

## 七、坑点汇总

| # | 现象 | 原因 | 规避 |
|---|---|---|---|
| 1 | `wsl.exe` 报「目录不存在」 | PowerShell 5.1 → wsl.exe 传参 GBK 编码，中文路径乱码 | 先 `cd` 进目录再启动 wsl，bash 内用 `./` 相对路径 |
| 2 | `node: command not found` 但 `which npm` 有输出 | appendWindowsPath 把 Windows 的 Node 混进 Linux PATH | apt 装 Linux 版 nodejs；排查用 `which node npm` |
| 3 | WSL 内跑前端报模块/二进制错误 | Windows 装的 node_modules 含平台二进制（esbuild），不可跨系统复用 | 复制项目排除 node_modules/.venv，进 WSL 重装 |
| 4 | 浏览器报 CORS 错误 | vite 端口退避到 5174，不在后端 CORS 白名单 | 起前端前确认 5173 空闲；白名单见 `backend/app/config.py` |
| 5 | PowerShell 里 `curl` 行为怪异 | `curl` 是 `Invoke-WebRequest` 别名 | 一律用 `curl.exe` |
| 6 | `/mnt/e` 下 `npm ci` 极慢或报错 | NTFS 挂载跨 VM IO 慢、权限/软链语义差异 | 项目复制进 ext4 家目录再装 |
| 7 | `uv sync` 卡在 watchfiles 构建 | watchfiles==1.2.0 无 Python 3.14 轮子，需构建 | 实测一次通过；失败则 `uv python install 3.12` 换解释器 |
| 8 | apt 装软件要输 sudo 密码 | 普通用户 sudo 交互式 | `wsl -u root -e bash -c '...'` 免交互 |

---

## 八、命令速查表

### PowerShell 侧（管理 WSL 本体）

```powershell
wsl --list --verbose          # 看发行版 / 状态 / 版本
wsl --shutdown                # 关闭整个 VM（释放内存）
wsl --terminate Ubuntu        # 停止指定发行版
wsl -u root                   # root 进入（装软件）
wsl -e bash -c '...'          # 执行单条 Linux 命令
curl.exe -s http://localhost:8000/api/faults   # Windows 侧验证转发
```

### bash 侧（WSL 内日常）

```bash
whoami                        # 当前用户
which node npm python3        # 确认工具解析路径
ls /mnt/e                     # 访问 Windows E 盘
df -h /home                   # 磁盘空间
uv sync                       # backend 依赖（cd backend）
npm ci                        # frontend 依赖（cd frontend）
uv run uvicorn app.main:app --reload    # 起 backend（8000）
npm run dev                   # 起 frontend（5173）
curl -s http://127.0.0.1:8000/api/faults
ps aux | grep -E 'uvicorn|vite' | grep -v grep
kill <PID>                    # 停进程
```

---

## 九、日常开发工作流建议

1. **代码同步以 git 为主**：Windows 侧写代码提交推送 → WSL 内 `git pull`；或 WSL 内改完 push，Windows 侧 pull。不要在两端手动同步文件。
2. **数据相互隔离**：WSL 副本的 `fault_tracker.db` 是复制瞬间的快照，之后两端各自演进、互不影响；验证接口时注意你 curl 到的是**哪一端**的数据。
3. **环境重建**：WSL 环境坏了直接 `rm -rf ~/pipeline-fault-tracker` 重走第六节即可（Windows 侧原项目不受影响，`rsync` 前先确保 Windows 侧已提交所有改动）。
4. **运行环境差异认知**：两端各自独立的 `.venv` / `node_modules`；本项目依赖用锁文件（`uv.lock` / `package-lock.json`）保证两端版本一致，任何依赖变更按规则 2.5 同步声明 + 锁文件 + 台账。
5. **资源回收**：不用 WSL 时 `wsl --shutdown` 释放 VM 占用的内存（vmmem 进程）。

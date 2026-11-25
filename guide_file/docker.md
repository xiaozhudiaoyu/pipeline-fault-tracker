# Docker 完整使用文档（通用教程手册 + 项目部署实战）

> 适用版本：以 **Docker Engine 29.x** 官方文档为基准整理（2026-09），具体版本以 `docker --version` 自查为准；Compose 章节对应 **Compose v2**（`docker compose` 子命令）语法。
> 定位：**通用教程手册 + 本项目部署实战（第十二节）**——第一~十节为不绑定项目的概念与命令大全；第十二节把本项目（pipeline-fault-tracker）的 Docker 化部署方案按当前代码事实整理为可执行示例（对应 [../process/_docker_plan.md](../process/_docker_plan.md) 的 D1~D5）。
> 可信度标注：「实测」= 本机执行验证过。WSL 内 Docker **29.8.1** / Compose **v5.5.1** 已装好（2026-09-22 实测，路线 B 已落地）；第一~十节命令为官方文档行为、未逐一实测；第十二节部署方案基于当前代码事实核查（env 名 / 探活端点 / uv 锁文件均已证实）；**D1 已实测验收通过**（镜像构建成功、四端点全 200，见 12.4），D2 / D3 操作步骤已交付、实际执行结果待验证（见 12.5 / 12.6）；**D1~D3 容器化产物已 commit**（`7ab3d84 chore(docker):`，6 files +92），D4 compose（SQLite 形态）见 12.7，**P3 已把 compose 迁移为 PostgreSQL 三服务（当前仓库实际形态，见 12.13，2026-09-30 实测全绿）**，D5 操作手册已完整交付（排障 / 埋雷 / 优化，见 12.10）。所有代码块已与仓库实际产物逐字对齐（compose 以 12.13 的 PG 形态为准，12.7 SQLite 形态保留作 D4 历史）；8.6 / 8.7 与 11.10 / 11.11 来自 python_learn 数据库容器化实战（2026-09-28 实测，同一台机器的 WSL Docker 引擎）。
> 执行位置约定：**PowerShell** = Windows 终端；**bash** = WSL / Linux 内。命令示例统一不含中文路径（中文路径与 WSL 互操作坑见 [WSL.md](WSL.md) 3.5 节）。本机 Docker 引擎装在 WSL 内（路线 B），实际执行 docker 命令时从 PowerShell 经 `wsl -e bash -c "..."` 包装进入（见 12.3）。

---

## 目录

1. [核心概念](#一核心概念)
2. [安装与环境准备](#二安装与环境准备)
3. [镜像操作](#三镜像操作)
4. [容器生命周期](#四容器生命周期)
5. [Dockerfile 指令集](#五dockerfile-指令集)
6. [数据持久化（卷）](#六数据持久化卷)
7. [网络](#七网络)
8. [Docker Compose](#八docker-compose)
9. [运维与排障](#九运维与排障)
10. [镜像优化](#十镜像优化)
11. [坑点汇总](#十一坑点汇总)
12. [本项目部署实战（pipeline-fault-tracker）](#十二本项目部署实战pipeline-fault-tracker)
13. [命令速查表](#十三命令速查表)

---

## 一、核心概念

### 1.1 三个基础对象：镜像 / 容器 / Registry

| 对象 | 是什么 | 类比 |
|---|---|---|
| **镜像（Image）** | 只读的静态模板：文件系统快照 + 启动元数据（入口命令、环境变量、端口声明） | 程序安装包 / 类（Class） |
| **容器（Container）** | 镜像的运行实例：镜像之上加一层**可写层**，进程在其中运行 | 运行中的进程 / 实例（Object） |
| **Registry** | 镜像仓库（远程），存放与分发镜像 | 包管理器源（npm registry / PyPI） |

三者关系：`docker pull` 从 Registry 取镜像 → `docker run` 由镜像创建容器 → 容器产生的修改（文件、进程）只存在于容器的可写层，**镜像本身永远不变**。

### 1.2 Docker 架构

```
┌─────────────┐    REST API     ┌─────────────┐
│  docker CLI │ ──────────────▶ │   daemon    │ ──▶ Registry（远程）
└─────────────┘   (本地 socket)  │  (dockerd)  │ ──▶ 容器 / 镜像 / 卷 / 网络
                                └─────────────┘
```

- **CLI**：你敲的 `docker` 命令，只是客户端，负责把请求发给 daemon；
- **daemon**：真正干活的后台服务（管理容器、镜像、网络、卷）；
- **registry**：默认 Docker Hub（`docker.io`），也可自建或用私有源。
- 推论：CLI 与 daemon 可以在不同机器（`docker -H ssh://...` 远程操作）；WSL 内装 Docker Engine 时，daemon 跑在 WSL 里。

### 1.3 分层与构建缓存（理解镜像体积与构建速度的钥匙）

- 镜像由**只读层**堆叠而成，Dockerfile 里每条会改动文件系统的指令（`RUN` / `COPY` / `ADD`）产生一层；
- **构建缓存**：某层及之前的输入不变 → 该层直接复用缓存，不重新执行；一旦某一层失效，其后的所有层全部重建；
- 实践推论：Dockerfile 里**变化频率低的指令放前面**（如先 `COPY requirements.txt` 装依赖、再 `COPY .` 拷贝代码），改业务代码时不重装依赖——详见 10.1。

### 1.4 卷与网络一句话

- **卷（Volume）**：容器删了数据就没了（可写层随容器销毁），卷是独立于容器生命周期之外的持久化存储——详见第六节；
- **网络（Network）**：容器默认在隔离的网络命名空间里，靠端口映射（`-p`）暴露服务；同一自定义网络内的容器可**直接用容器名/服务名互访**——详见第七节。

---

## 二、安装与环境准备

> 两条路线任选其一即可；路线 A 省事、路线 B 更贴近 Linux 部署形态。

### 2.1 路线 A：Windows 安装 Docker Desktop（WSL2 后端）

1. 从官网下载安装包并安装（勾选 "Use WSL 2 based engine"）；
2. 安装后启动 Docker Desktop，等待右下角状态变为 "Engine running"；
3. Docker Desktop 自带 Compose v2 插件，无需另装。

### 2.2 路线 B：WSL Ubuntu 内装 Docker Engine + Compose 插件

前置：WSL 发行版启用 systemd（`/etc/wsl.conf` 配 `[boot] systemd=true` 后 `wsl --shutdown` 重启，见 [WSL.md](WSL.md)）。

```bash
# 以 root 执行（从 PowerShell 调用：wsl -u root -e bash -c '...'）
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

> 命令来源：Docker 官方「Install Docker Engine on Ubuntu」文档（apt 仓库安装法），未实测。

### 2.3 免 sudo 运行（路线 B 收尾）

```bash
usermod -aG docker $USER    # 加入 docker 组，重新登录后免 sudo 跑 docker
```

### 2.4 安装验证三连

```powershell
docker --version            # 客户端版本
docker compose version      # Compose v2 版本（v2 是插件，独立版本号）
docker run --rm hello-world # 拉取 hello-world 并运行，能打印欢迎信息即 daemon 正常
```

三连全过即环境就绪。首次 `docker run hello-world` 会经历「本地无镜像 → pull → 创建容器 → 运行 → 退出」完整链路，是理解 1.1 概念的最好实验。

---

## 三、镜像操作

### 3.1 拉取 / 查看 / 删除

```powershell
docker pull python:3.14-slim        # 从 Docker Hub 拉镜像（无仓库名默认 docker.io/library/）
docker images                       # 列出本地镜像（旧命令 docker image ls 等价）
docker image inspect python:3.14-slim   # 看镜像元数据（分层、入口、环境变量）
docker rmi python:3.14-slim         # 删除镜像（有容器引用时需先删容器或用 -f）
docker image prune                  # 清理无标签的悬空镜像（<none>）
```

### 3.2 构建：`docker build`

```powershell
docker build -t myapp:0.1 .        # 用当前目录做构建上下文，构建并打 tag
docker build -t myapp:0.1 -f backend/Dockerfile backend/   # 指定 Dockerfile 与上下文目录
docker build --no-cache -t myapp:0.1 .   # 强制忽略全部缓存重建
```

- **构建上下文**：`docker build` 最后一个参数是「上下文目录」，该目录（受 `.dockerignore` 过滤后）会被整体发送给 daemon——所以上下文越小构建越快，绝不要把仓库根目录当上下文去拷整个 `node_modules`；
- **tag 规范**：`[registry/][repo/]name[:tag]`，省略 tag 默认 `latest`；`latest` 只是普通标签、无「最新」语义，生产应显式打版本 tag（如 `0.1`、`20260922`）。

### 3.3 推送 / 打标签

```powershell
docker tag myapp:0.1 docker.io/yourname/myapp:0.1   # 另打一个含仓库名的 tag
docker login                                          # 登录 Docker Hub（或私有 registry）
docker push docker.io/yourname/myapp:0.1              # 推送
```

### 3.4 `.dockerignore`

构建上下文的过滤清单，语法同 `.gitignore`，放置于上下文根目录。**必须排除**：`node_modules/`、`.venv/`、`__pycache__/`、`*.db`、`.env`（含密钥，绝不打进镜像）、`.git/`、`.idea/`。

---

## 四、容器生命周期

### 4.1 创建并运行：`docker run`

```powershell
docker run hello-world                          # 前台跑完即退出
docker run -it ubuntu bash                      # 交互式进入 bash（-i 交互 -t 分配 TTY）
docker run -d --name web -p 8080:80 nginx       # 后台运行、命名、端口映射
docker run --rm -p 8000:8000 -e KEY=val -v data:/data myapp:0.1
```

常用选项：

| 选项 | 说明 |
|---|---|
| `-d` | 后台（detached）运行 |
| `--name <名>` | 命名容器（否则随机名），便于后续 `logs`/`exec`/`stop` 引用 |
| `--rm` | 容器退出后自动删除（一次性任务标配，防止残留僵尸容器） |
| `-p 宿主机:容器` | 端口映射，格式 `[宿主IP:]宿主端口:容器端口[/协议]` |
| `-e KEY=value` / `--env-file .env` | 注入环境变量 |
| `-v 卷或路径:容器路径` | 挂载存储（详见第六节） |
| `--restart always` | 重启策略：`no`（默认）/ `always` / `unless-stopped` / `on-failure[:次数]` |
| `-m 512m` / `--cpus 1.5` | 内存 / CPU 配额限制 |
| `-it` | 交互模式（进入 shell 用） |

### 4.2 查看 / 启停 / 删除

```powershell
docker ps                  # 正在运行的容器（-a 显示全部含已退出）
docker start web           # 启动已存在的容器（run 是「新建+启动」）
docker stop web            # 优雅停止（发 SIGTERM，等待宽限期后 SIGKILL）
docker kill web            # 立即 SIGKILL
docker restart web         # 重启
docker rm web              # 删除已停止容器（-f 强制删除运行中的）
docker rm (docker ps -aq)     # 批量删全部容器（PowerShell 语法；bash 下为 docker rm $(docker ps -aq)）
```

> 区分：`docker rm` 删容器，`docker rmi` 删镜像；`run` = create + start，重复 `run` 会建新容器。

### 4.3 进入容器 / 看日志 / 拷文件

```powershell
docker exec -it web sh            # 在运行中的容器里开 shell（排障最常用）
docker exec web ls /usr/share     # 执行单条命令不进入
docker logs web                   # 看容器 stdout/stderr（-f 持续跟踪 --tail 100 只看末尾）
docker cp web:/app/data.db .      # 容器 → 宿主机拷文件（方向反过来同理）
```

---

## 五、Dockerfile 指令集

### 5.1 指令速查表

| 指令 | 作用 | 关键点 |
|---|---|---|
| `FROM <镜像>` | 指定基础镜像（每个阶段第一条指令） | 尽量选官方 slim/alpine 系 |
| `WORKDIR <路径>` | 设置工作目录 | 不存在则自动创建，后续相对路径以其为基准 |
| `COPY <源> <目标>` | 从**构建上下文**拷文件进镜像 | 源只能用上下文内的路径，不能用绝对宿主路径 |
| `ADD <源> <目标>` | 同 COPY，额外支持 URL 与自动解压 tar | 无特殊需求一律用 COPY |
| `RUN <命令>` | 构建期执行命令（装依赖、编译） | 每条产生一层，可合并的用 `&&` 串起来 |
| `ENV K=V` | 设置环境变量（运行时也存在） | 构建期 + 运行期都生效 |
| `ARG K=V` | 构建期变量（`--build-arg` 传入） | 仅构建期可见，运行期不存在 |
| `EXPOSE <端口>` | 声明容器监听端口 | 纯文档性质，实际开放靠 `-p` / compose `ports` |
| `CMD [...]` | 容器默认启动命令 | 运行时可被 `docker run` 末尾参数覆盖 |
| `ENTRYPOINT [...]` | 容器入口程序 | `run` 末尾参数会作为它的**参数**追加 |
| `VOLUME ["/data"]` | 声明匿名卷挂载点 | 建议显式 `-v`/compose volumes，少依赖它 |
| `USER <用户>` | 指定运行用户 | 生产镜像避免 root 运行 |
| `HEALTHCHECK ...` | 定义健康检查 | Dockerfile 形式：`HEALTHCHECK --interval=5s CMD <探活命令>`；compose 字段写法见 8.4 |

### 5.2 shell 形式 vs exec 形式

```dockerfile
CMD echo hello            # shell 形式：经 /bin/sh -c 执行，支持变量展开与 && 串联
CMD ["echo", "hello"]     # exec 形式：直接 exec，无 shell，变量不展开
```

- 需要 shell 特性（管道、`&&`、`$VAR` 展开）→ shell 形式；
- 想正确接收信号（优雅退出）→ exec 形式；JSON 数组内必须用双引号。

### 5.3 CMD vs ENTRYPOINT 分工

- **只有 CMD**：`docker run myapp ls` 会把默认命令整个替换成 `ls`（最灵活）；
- **ENTRYPOINT + CMD**：ENTRYPOINT 固定入口程序，CMD 提供默认参数——`docker run myapp --port 9000` 时 `--port 9000` 追加到入口之后，适合「镜像即命令」场景（如 curl 专用镜像）；
- 判断依据：容器被用户拿来当「进程」用 → ENTRYPOINT；容器是「环境」、入口随场景变 → CMD。

### 5.4 多阶段构建（前端 / 编译型项目标配）

```dockerfile
# ---- stage 1：构建（含完整工具链，镜像大）----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- stage 2：运行（只有产物 + 轻量运行时）----
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

- 终镜像**不含** node 工具链与 `node_modules`，体积从数百 MB 降到几十 MB；
- `COPY --from=build` 跨阶段拷文件；只有最终 `FROM` 生效，中间阶段不产出镜像；
- 前端框架的环境变量（`VITE_*`、`REACT_APP_*` 等）是**构建期**替换，必须在构建阶段用 `ARG`/`ENV` 传入，运行期再设无效——坑见 11.4。

### 5.5 通用后端示例（Python/FastAPI 形态）

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

三个考点：先 COPY 锁文件再 COPY 代码（层缓存，改代码不重装依赖）；`--no-cache-dir` 不落 pip 缓存（瘦身）；必须监听 `0.0.0.0`（容器内只绑 `127.0.0.1` 外部不可达，坑见 11.2）。

---

## 六、数据持久化（卷）

### 6.1 为什么容器删了数据就没了

容器的文件修改写在**可写层**，`docker rm` 后随容器销毁。要持久化，须把数据写到「容器文件系统之外」的挂载点。

### 6.2 三种挂载对比

| 挂载类型 | 语法 | 数据位置 | 典型场景 |
|---|---|---|---|
| **bind mount** | `-v 宿主机绝对路径:容器路径` | 宿主机指定目录（可读可写） | 开发热更新、注入配置文件 |
| **named volume** | `-v 卷名:容器路径` | Docker 管理的卷目录（`/var/lib/docker/volumes/`） | 数据库文件、上传文件等需持久化的数据 |
| **tmpfs** | `--tmpfs 容器路径` | 内存 | 临时缓存、敏感中间数据（不落盘） |

选型：数据归「用户自己管理、要看内容」→ bind mount；数据归「应用管、换容器/换机器要带走」→ named volume。**卷名可复用**：同名卷已存在时直接复用其数据，这是「删容器重跑不丢数据」的机制。

### 6.3 volume 命令

```powershell
docker volume create pft-data            # 显式创建卷
docker volume ls                         # 列出卷
docker volume inspect pft-data           # 看卷详情（含宿主机实际挂载路径 Mountpoint）
docker volume rm pft-data                # 删除卷 = 删除数据（不可逆！）
docker run --rm -v pft-data:/app/data myapp:0.1   # 容器挂载卷
```

> `docker volume rm` 是**不可逆操作**：卷删了数据就真没了（回收站、`docker system` 均找不回）。删除前先备份（见 6.4），并把「先备份再删」当作固定心智。

### 6.4 备份与恢复卷

```powershell
# 备份：起一个临时容器，把卷挂进来打成 tar
docker run --rm -v pft-data:/data -v "$PWD":/backup alpine tar czf /backup/pft-data.tar.gz -C /data .

# 恢复：解 tar 回卷
docker run --rm -v pft-data:/data -v "$PWD":/backup alpine tar xzf /backup/pft-data.tar.gz -C /data
```

手法：用 `alpine` 这类极小的「工具容器」借挂载点搬运文件（`docker cp` 只能碰容器文件系统，碰不到卷本体）。

---

## 七、网络

### 7.1 网络驱动一览

| 驱动 | 说明 |
|---|---|
| `bridge` | 默认：容器在同一宿主机桥接网络内，靠端口映射对外 |
| `host` | 容器直接共享宿主机网络栈（无端口映射概念，性能好、隔离差） |
| `none` | 无网络（完全隔离） |
| `overlay` | 跨宿主机的 Swarm 集群网络（进阶，不在本文范围） |

### 7.2 端口映射

```powershell
docker run -p 8080:80 nginx      # 宿主机 8080 → 容器 80
docker run -P nginx              # 大写 -P：把 EXPOSE 声明的端口随机映射到宿主机
```

访问路径：浏览器 → 宿主机 `127.0.0.1:8080` → 容器 `:80`。**`-p` 前面的是宿主机端口，后面的是容器内端口**，顺序记反是最常见错误。

### 7.3 默认 bridge vs 自定义网络

```powershell
docker network create mynet          # 创建自定义 bridge 网络
docker network ls                    # 列出网络
docker run --network mynet ...       # 加入自定义网络
docker network rm mynet              # 删除网络
```

关键差异：

| | 默认 bridge | 自定义网络 |
|---|---|---|
| 容器互访方式 | 只能靠容器 IP（重启会变） | 可**直接用容器名当 DNS 解析** |
| 网络隔离 | 全部默认网络里的容器可互通 | 只有同网络内互通，天然分组 |
| 适用 | 单容器快速试跑 | 多容器互相依赖（几乎总是用它） |

> Compose 场景下无需手动建网：`docker compose` 自动为项目创建专用网络，服务名（如 `backend`）即 DNS 名，`backend:8000` 即访问方式——见 8.3。

### 7.4 容器访问宿主机：`host.docker.internal`

容器内想访问宿主机的服务时：

- Docker Desktop（Windows/Mac）：内置域名 `host.docker.internal` 直接可用；
- Linux Docker Engine：较新版本（20.10+）可用 `docker run --add-host=host.docker.internal:host-gateway` 追加映射；
- WSL2 + Docker Desktop 组合下该域名解析到 Windows 宿主；
- **本机实测坑**：Docker 引擎装在 WSL2 内（路线 B）时 `host-gateway` 指向 WSL 虚拟机而非 Windows 宿主，见 11.11。

---

## 八、Docker Compose

### 8.1 Compose 是什么、v1 与 v2

- **定位**：多容器应用的一键编排——用一份声明式 YAML 描述服务、网络、卷，替代一长串 `docker run`；
- **v2（现行）**：`docker compose`（daemon 的插件，compose.yml 顶格无 version 字段或写 `version: "3.x"` 均可）；
- **v1（历史）**：`docker-compose`（独立 Python 程序，已停止维护）。本文只讲 v2。

### 8.2 最小可用模板

```yaml
services:
  backend:
    build: ./backend
    environment:
      DATABASE_URL: sqlite:///./data/fault_tracker.db
    volumes:
      - pft-data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 5
  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
volumes:
  pft-data:
```

### 8.3 常用指令含义

| 键 | 含义 |
|---|---|
| `services` | 服务列表，一个服务 ≈ 一类容器的定义（可 `--scale` 多副本） |
| `build: <目录>` | 用该目录构建镜像（可用 `build: {context: ., dockerfile: Dockerfile, args: {...}}` 扩展） |
| `image: <名>` | 直接拉现成镜像跑（与 build 二选一） |
| `ports: ["宿:容"]` | 端口映射（仅宿主机可见；`expose` 是仅网络内可见） |
| `environment:` / `env_file:` | 环境变量 / 从 `.env` 文件读取 |
| `volumes: ["卷名:/容器路径"]` | 挂载（短语法）；长语法 `{type: volume, source: ..., target: ...}` |
| `depends_on: {condition: service_healthy}` | 等依赖服务「健康」后再启动（须配 healthcheck 才有意义） |
| `healthcheck` | 健康检查定义（test/interval/timeout/retries/start_period） |
| `restart: unless-stopped` | 重启策略 |
| 顶层 `volumes:` / `networks:` | 声明命名卷 / 网络 |

**服务名即 DNS**：compose 为项目建专用网络，容器间用 `http://backend:8000` 互访，**不是** `localhost`——`localhost` 在容器里指容器自己。

### 8.4 健康检查（healthcheck）

`depends_on` **只管启动顺序、不管就绪**——后端可能「容器起来了但服务还没监听」。三种写法：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]  # 基础镜像有 curl 时
  test: ["CMD-SHELL", "curl -f http://127.0.0.1:8000/health || exit 1"]   # 需 shell 时
  test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"]  # slim 镜像无 curl 时（用运行时自带工具）
  interval: 5s
  timeout: 3s
  retries: 5
```

> 注意：slim/alpine 基础镜像普遍**不带 curl**，healthcheck 里用 curl 会持续失败——优先用应用运行时自带的手段（python urllib / node 内置 fetch / wget）。

### 8.5 命令集

```powershell
docker compose up -d --build     # 构建并后台启动全部服务（-d 后台，--build 强制重建）
docker compose up -d backend     # 只启动指定服务（含其依赖）
docker compose ps                # 看编排内容器状态（含健康状态列）
docker compose logs -f backend   # 跟踪某服务日志
docker compose exec backend sh   # 进入服务容器开 shell
docker compose build             # 只构建不启动
docker compose down              # 停止并删除容器与网络（卷保留）
docker compose down -v           # 连声明卷一起删除（危险！见 11.5）
docker compose restart           # 重启（不重建镜像）
```

- `down`（不带 `-v`）再 `up`：容器重建但**卷还在，数据不丢**；
- 修改 Dockerfile / compose 配置后重跑 `up`：compose 自动识别变更，重建受影响的容器；
- 服务名补全：`docker compose logs backend` 中的 `backend` 是 YAML 里的服务名，不是容器名（裸容器名带项目前缀，坑见 11.10）。

### 8.6 数据库服务容器化编排（MySQL 模板）

把数据库与应用放进同一 compose 编排、容器间用服务名互访、不依赖任何宿主机 IP——是「容器连宿主机数据库」诸拓扑之外的首选拓扑（2026-09-28 实测）：

```yaml
services:
  mysql:
    image: mysql:8.4            # 版本须 ≥ 源库版本，保证 dump 可导入（见 8.7）
    environment:
      # 敏感值全部来自项目根目录 .env（compose 自动读取并插值，不入库、不进镜像）；
      # :? 语法 = 变量缺失时直接报错拒绝启动，避免带空口令把卷初始化坏
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:?请在 .env 中设置 MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE:?请在 .env 中设置 MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER:?请在 .env 中设置 MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:?请在 .env 中设置 MYSQL_PASSWORD}
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
    ports:
      - "127.0.0.1:3307:3306"   # 只绑回环：与宿主机 3306 并存；容器间通信不走此端口
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uroot", "-p${MYSQL_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
  app:
    depends_on:
      mysql:
        condition: service_healthy   # 数据库健康后再启应用（见 11.6）
volumes:
  mysql_data:
```

要点：

- **应用侧连接参数**：DB_HOST 写服务名 `mysql`、DB_PORT 写 **3306（容器内端口）**，与宿主机映射的 3307 无关；
- **.env 双重排除**：`.env` 须同时进 `.gitignore` 与 `.dockerignore`（机理见 11.8），仓库只提交 `.env.example` 模板；
- **官方镜像初始化时点**：`MYSQL_*` 变量只在**空卷首启**时生效；卷已存在后再改 `.env` 不会重建库/账号，须删卷重来（不可逆，见 11.5）；
- **账号自动授权**：`MYSQL_USER` 首启时自动创建并授予 `MYSQL_DATABASE` 库全部权限，「容器连宿主机库」时代的 ERROR 1130 授权问题不复存在；
- **健康检查带口令**：`mysqladmin ping -p<口令>` 的口令经 compose 插值注入，只存在于 `.env`，不进镜像层。

### 8.7 存量数据迁入容器数据库（mysqldump 导出/导入）

```powershell
# 导出（PowerShell）：必须用 cmd /c 包装——PowerShell 的 > 重定向写 UTF-16 编码，
# 直接 mysqldump ... > dump.sql 得到的文件 mysql 导入会报语法错误
cmd /c "mysqldump -h 127.0.0.1 -u <账号> -p --single-transaction --databases <库名> > dump.sql"
```

```bash
# 导入（bash / WSL）：stdin 重定向发生在宿主机侧，-T 关闭 TTY 分配
docker compose exec -T mysql sh -c "mysql -uroot -p'<root口令>'" < dump.sql
# 抽查：表清单 + 行数，与源库对比
docker compose exec mysql sh -c "mysql -uroot -p'<root口令>' -e 'USE <库名>; SHOW TABLES;'"
```

要点：

- `--single-transaction`：InnoDB 一致性快照导出，不锁表；
- `--databases`：dump 自带 `CREATE DATABASE` / `USE` 语句（含 IF NOT EXISTS，与首启已建的库不冲突），导入时库名自动对齐；
- dump 含表结构 + 数据 + 迁移版本表（如 `alembic_version`），导入后**无需**再跑迁移；
- 迁移顺序：先 `docker compose up -d mysql` 起空库 → 导入 → 应用配置切到服务名 → `docker compose up -d` 全栈 → 用业务接口抽查数据与源库一致；
- `dump.sql` 含全库数据：验证完成后自行删除，**绝不提交**（不在 `.gitignore` 里时尤其注意）。

---

## 九、运维与排障

### 9.1 排障三件套

| 工具 | 用途 | 典型命令 |
|---|---|---|
| `docker logs` | 看应用输出（崩了、报错先看它） | `docker logs -f --tail 200 web` |
| `docker exec` | 进容器现场勘查 | `docker exec -it web sh` → `ls` / `ps` / `cat 配置文件` |
| `docker inspect` | 看运行态真相（实际生效的配置） | `docker inspect web` → 查 IP、挂载、重启策略、退出码 |

排障顺序建议：`logs` 看报错 → 若端口/网络类问题 → `inspect` 看实际映射与挂载 → `exec` 进容器验证容器内视角（如 `127.0.0.1:8000` 在容器内是否可通）。

### 9.2 磁盘与资源

```powershell
docker system df        # 各对象磁盘占用总览（镜像/容器/卷/缓存，-v 明细）
docker system prune     # 清理：停止的容器、无引用网络、悬空镜像、构建缓存（-a 连未使用镜像也删）
docker stats            # 实时看各容器 CPU/内存占用
```

### 9.3 事件与容器详情

```powershell
docker events --since 1h          # 实时事件流（创建/启动/退出/OOM 等）
docker port web                   # 看容器实际生效的端口映射
docker top web                    # 看容器内进程
```

---

## 十、镜像优化

### 10.1 六大手段与体积对照

| 手段 | 效果 | 说明 |
|---|---|---|
| 写 `.dockerignore` | 上下文瘦身（间接） | 挡住 `node_modules`/`.git` 等，构建快且避免垃圾进镜像 |
| 依赖层前置（先 COPY 锁文件） | 构建提速 | 改代码不触发依赖层重建，缓存命中率高 |
| `--no-cache-dir`（pip） | 减几十~几百 MB | 不落包管理器缓存；npm 用 `npm ci` + 多阶段构建等效解决 |
| 合并 RUN（`&&` 串联） | 每层节省 | 每层 = 一份压缩快照，零散 RUN 膨胀体积 |
| slim / alpine 基础镜像 | 一个数量级 | `python:3.14`（数百 MB）→ `python:3.14-slim`（~100+ MB）；alpine 更小但 musl 兼容风险需评估 |
| 多阶段构建 | 数量级缩减 | 终镜像不含构建工具链（见 5.4） |

### 10.2 验证手法

```powershell
docker build -t myapp:0.1 .
docker image ls myapp         # 记录体积
# 改动一行业务代码后重新构建，观察输出里哪些层 "CACHED"（缓存命中）、哪些层重跑
docker history myapp:0.1      # 看每层体积与来源指令，定位大头
```

改一行代码就重装全部依赖 = Dockerfile 层序有问题，回到 10.1 第二行修正。

---

## 十一、坑点汇总

### 11.1 端口映射顺序记反

`-p 8080:80` 是「宿主机:容器」。记反后现象：容器内服务明明起来了，浏览器访问的却是别的端口 / 直接连不上。口诀：**前宿主后容器**。

### 11.2 容器只监听 127.0.0.1，外部不可达

uvicorn 默认 `--host 127.0.0.1` 在容器里只对容器自身可达，宿主机映射端口访问不通。凡是「容器里的服务要对外提供」，一律监听 `0.0.0.0`。`inspect` 或 `exec` 进去 `curl 127.0.0.1:端口` 通、宿主机不通时，优先怀疑这条。

### 11.3 `localhost` 在容器里是容器自己

多容器互访必须用服务名 / 容器名（如 `http://backend:8000`）。在浏览器（宿主机）访问时才用 `localhost:映射端口`。混用是 Compose 联调第一大坑。

### 11.4 前端构建期环境变量运行期注入无效

`VITE_*` / `REACT_APP_*` / `NEXT_PUBLIC_*` 在 **build 时**被替换进产物。镜像里若 `ARG` 不传默认空/undefined，产物里就出现 `undefined/api/...` 这类残缺路径。正确姿势：构建时显式传参（`--build-arg` 或 compose `build.args`）；同源部署（nginx 代理 `/api`）传**空串**让请求走相对路径。

### 11.5 `down -v` 与 `volume rm` 不可逆

`docker compose down -v` 连卷一起删、`docker volume rm` 删卷——都是「删数据」，没有回收站。执行前先按 6.4 备份；「先备份再删」是处理卷的唯一安全路径。

### 11.6 `depends_on` 不等同于「就绪」

`depends_on` 只保证启动顺序，不保证依赖服务已可接受请求。要管就绪，配 `condition: service_healthy` + healthcheck；且 healthcheck 的命令必须存在于镜像内（slim/alpine 无 curl，见 8.4）。

### 11.7 PowerShell 的命令分隔与子表达式

PowerShell 不支持 `&&` 语句分隔（用 `;` 或换行）；bash 的 `$(命令)` 命令替换在 PowerShell 里优先用 `(命令)` 直接收集输出（`$()` 在 PowerShell 中是子表达式、行为有差异，避免照搬 bash 写法）：

```powershell
docker rm (docker ps -aq)                 # PowerShell：括号收集输出，直接作为参数列表
docker ps -aq | ForEach-Object { docker rm $_ }   # 或管道逐条处理
```

### 11.8 `.env` 与 `env_file` 的时点差异

- 镜像里的 `.env` 若被 `COPY` 进镜像 → 密钥泄漏进镜像层（`docker history` 可挖出）；
- compose 的 `env_file:` / `environment:` 是**运行期**注入，不落镜像；
- `.env` 文件本身必须同时进 `.gitignore` 与 `.dockerignore`。

### 11.9 容器退出码与僵尸容器

- 前台进程结束 → 容器退出（不是故障，`hello-world` 就是正常退出）；
- 退出码非 0 → 看 `docker logs` 与 `docker inspect -f '{{.State.ExitCode}}'`；
- 不带 `--rm` 的一次性容器会堆积为 Exited 状态，`docker system prune` 定期清。

### 11.10 `docker logs <服务名>` 报 No such container

compose 创建的容器名带**项目名前缀**：`<项目>-<服务>-<序号>`（如 `python_learn-mysql-1`），不是裸服务名。于是容器明明在跑，`docker logs mysql` 仍报 `Error response from daemon: No such container: mysql`（2026-09-28 实测）。正确姿势：

- `docker compose logs mysql`——参数是**服务名**，推荐；
- `docker logs python_learn-mysql-1`——完整容器名，先 `docker ps` 查。

### 11.11 Docker 引擎在 WSL2 内时 `host-gateway` 指向 WSL 虚拟机

`extra_hosts: host.docker.internal:host-gateway` 在 Docker Desktop 下指向 Windows 宿主；但 Docker 引擎装在 WSL2 内（路线 B）时，`host-gateway` 解析到的是 **WSL 虚拟机自己**——Windows 侧的服务（如宿主机 MySQL 3306）经此名不可达（Connection refused），只能改填 Windows 虚拟网卡 IP（如 172.19.x.x），且 WSL 重启后该 IP 可能漂移（2026-09-28 实测）。**根治办法**：把数据库放进同一 compose 编排、容器间走服务名（见 8.6），彻底不经过宿主机网络。

---

## 十二、本项目部署实战（pipeline-fault-tracker）

> 本节把 [../process/_docker_plan.md](../process/_docker_plan.md) 的 D1~D5 方案按**当前项目事实**（2026-09-23 核查）整理为可执行的部署示例。产物文件已全部落地：`backend/Dockerfile`、`backend/.dockerignore`、`frontend/Dockerfile`、`frontend/nginx.conf`、`frontend/.dockerignore`、`frontend/.npmrc` 已 commit（`7ab3d84 chore(docker):`）；`docker-compose.yml` 已生成（待 D4 验证后单独提交，见 12.7）。所有代码块与仓库实际文件逐字对齐。

### 12.1 现状基线与部署目标

| 项 | 结论 | 证据 |
|---|---|---|
| Docker 引擎 | WSL 内 Docker 29.8.1 + Compose v5.5.1（路线 B 已落地，Session 0 完成） | 2026-09-22 实测 |
| 后端依赖 | uv 工作流：`pyproject.toml` + `uv.lock`（旧 pip requirements 两文件已删，镜像内须用 uv） | `backend/pyproject.toml` |
| 前端 Node | `engines.node >= 16`；本地 `dev.bat` 用 `nvm use 16.20.2`（Node 16 锁定，镜像选 node:16 系） | `frontend/package.json` / `frontend/dev.bat` |
| 配置 env 名 | `DATABASE_URL` / `HOST` / `PORT` / `CORS_ORIGINS`（pydantic-settings，大小写不敏感） | `backend/app/config.py` |
| 探活端点 | `/` 与 `/api/health`（返回 `{"status":"ok"}`，compose healthcheck 直接用） | `backend/app/main.py` |
| 建表 | lifespan → `create_all(checkfirst=True)` 自动建表，启动即用 | `backend/app/main.py` |
| 前端路由 | history 模式 → 生产 nginx 需 `try_files` 回退 index.html | `frontend/src/router/index.ts` |
| API 地址 | `VITE_API_BASE_URL` 为**构建期**替换（`.env.example` 已证实） | `frontend/.env.example` |

- **目标**：前后端容器化 + Compose 编排 + SQLite named volume 持久化，走通列表/登记/详情全闭环；
- **非目标**（与计划一致）：TLS、镜像签名、CI 推 registry、K8s、多环境配置分离。

### 12.2 Session 0 操作步骤：WSL 内安装 Docker Engine（2026-09-22 已实测完成）

> 本节把 _docker_plan.md 的 Session 0 文档化：路线 B（WSL 内 Docker Engine + compose 插件）已按四步手册实际执行成功，实测 **Docker 29.8.1 / Compose v5.5.1**。通用双路线说明与概念讲解见第二节；此处记录本项目实际执行的命令、交付要点与验证证据。

**步骤 1：前置检查（本项目实测基线）**

```powershell
wsl -l -v                                    # Ubuntu / WSL2（Stopped 属正常，安装过程会自动拉起）
wsl -e bash -c "ps -p 1 -o comm="            # 输出 systemd = 路线 B 前提具备
wsl -e bash -c "grep VERSION_CODENAME /etc/os-release"   # 本项目 resolute（Ubuntu 26.04.1 LTS）
wsl -e bash -c "dpkg --print-architecture"   # 本项目 amd64
```

- systemd 未启用时：`/etc/wsl.conf` 配 `[boot] systemd=true` 后 `wsl --shutdown`（见 [WSL.md](WSL.md)）；
- 本项目实测基线：Ubuntu 26.04.1 LTS（codename `resolute`）、`amd64`、PID 1 = systemd、默认用户 `xiaozhu`。

**步骤 2：添加 Docker 官方 apt 仓库（root 执行）**

> 交付要点：把 arch / codename **写死**为 `amd64` / `resolute`（而非 2.2 的 `$(...)` 变量展开），规避 PowerShell → wsl.exe 参数转义坑；每条命令独立成一条 `wsl -u root -e bash -c "..."`，不堆叠引号。

```powershell
wsl -u root -e bash -c "apt-get update"
wsl -u root -e bash -c "apt-get install -y ca-certificates curl"
wsl -u root -e bash -c "install -m 0755 -d /etc/apt/keyrings"
wsl -u root -e bash -c "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc"
wsl -u root -e bash -c "chmod a+r /etc/apt/keyrings/docker.asc"
wsl -u root -e bash -c "echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu resolute stable' > /etc/apt/sources.list.d/docker.list"
wsl -u root -e bash -c "apt-get update"
```

**步骤 3：安装 Engine + Compose 插件**

```powershell
wsl -u root -e bash -c "apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin"
```

**步骤 4：免 sudo 配置**

```powershell
wsl -u root -e bash -c "usermod -aG docker xiaozhu"
wsl --shutdown   # 一步两用：docker 组权限下次登录生效 + systemd 拉起 docker.service（无需单独 systemctl enable）
```

**步骤 5：验证三连（本项目实测结果）**

```powershell
wsl -e bash -c "docker --version"          # Docker version 29.8.1, build 4a63305
wsl -e bash -c "docker compose version"    # Docker Compose version v5.5.1
wsl -e bash -c "docker run --rm hello-world"   # 能打印欢迎信息 = daemon 正常（验收标准）
```

- 实测：`docker.service` 由 systemd 托管，默认无容器运行；Linux 提示符下 docker 免 sudo；
- Windows 侧未装 Docker Desktop，但 PowerShell 直接敲 `docker --version` 亦可成功（CLI 连接 WSL 内同一 daemon）——文档与交付步骤仍统一用 `wsl -e bash -c` 包装。

**步骤 6：安装后配置——registry 镜像加速器（本项目实测坑）**

- 实测网络：`registry-1.docker.io`（Docker Hub）直连不通（connection reset by peer）；`https://docker.m.daocloud.io` 连通（`/v2/` 返回 401 属 registry 正常未认证响应）；`docker.mirrors.ustc.edu.cn` 不通；
- 配置（写 daemon.json 需 root）：

```powershell
wsl -u root -e bash -c "echo '{\"registry-mirrors\":[\"https://docker.m.daocloud.io\"]}' > /etc/docker/daemon.json"
wsl -u root -e bash -c "systemctl restart docker"
```

- 对 WSL 内 daemon 全局生效（Windows 侧调用同样受益）；
- **边界**：该加速器只代理 Docker Hub，**不覆盖 ghcr.io 等其它 registry**——12.4 的 backend 镜像从 `ghcr.io/astral-sh/uv` 取 uv 二进制时仍走直连，是已知风险点。

### 12.3 执行约定

- 引擎装在 WSL 内（路线 B），所有 docker 命令从 PowerShell 经 `wsl -e bash -c "..."` 包装执行（引号嵌套坑见 [WSL.md](WSL.md)）；
- 产物落地状态（2026-09-23）：`backend/Dockerfile`、`backend/.dockerignore`、`frontend/Dockerfile`、`frontend/nginx.conf`、`frontend/.dockerignore`、`frontend/.npmrc` 已 commit（`7ab3d84 chore(docker): 前后端容器化构建产物（D1-D3 练习）`，6 files +92）；`docker-compose.yml` 已生成（未跟踪，待 D4 验证后单独提交）。产物提交不与功能改动混合（规则 3.5 精神）；
- 执行状态：D1 已实测构建运行通过（见 12.4）；D2 演练方案已交付、实际执行结果待验证（见 12.5）；D3 已实测构建通过（pft-frontend:0.1 CONTENT SIZE 26.7MB，见 12.6）；D4 compose 已生成、待用户验证闭环（见 12.7）；D5 操作手册已完整交付（排障 / 埋雷 / 优化实验，见 12.10），具体执行结果待用户反馈。

### 12.4 backend 镜像（uv 路线）

> **注意**：_docker_plan.md 制定于 2026-09-21，其 D1 写的是 pip + `requirements.lock.txt` 路线；后端于 2026-09-22 迁至 uv（迁移记录见 DEPENDENCIES.md「八」），requirements 两文件已删——**照抄旧计划会构建失败**，以本节为准。
>
> **产物状态（2026-09-23）**：`backend/Dockerfile` 与 `backend/.dockerignore` 均已落地（commit `7ab3d84`，仓库实际文件即下述内容），构建与运行已实测验收（见本节末尾）。

`backend/.dockerignore`：

```
# 构建上下文排除清单：减小发送给 daemon 的体积，避免本机产物混入镜像
.venv/
__pycache__/
*.db
.env
.idea/
.python-version
```

`backend/Dockerfile`：

```dockerfile
FROM python:3.14-slim
WORKDIR /app
# uv 二进制从官方镜像直拷到 PATH（不经 pip，规避 PyPI 网络路径；registry 边界见 12.2 步骤 6）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# 先拷声明与锁文件再装依赖（层缓存考点）：--no-dev 跳过 dev 组、--no-cache 不落缓存目录
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
EXPOSE 8000
# 必须绑 0.0.0.0（容器内 127.0.0.1 外部不可达）；
# uv run 复用 sync 好的 .venv，--no-sync 免启动时重新解析
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- 层缓存 / `0.0.0.0` 考点与 5.5 相同；
- uv 三点：uv 二进制从 `ghcr.io/astral-sh/uv` 官方镜像直拷到 PATH（不经 pip，规避 PyPI 网络路径）；`uv sync --frozen` 按 `uv.lock` 精确复现（不容忍漂移）；`--no-dev --no-cache` 跳过 dev 组且不落缓存目录（对应 pip 路线的 `--no-cache-dir` 瘦身）。

验证（D1 闭环，bash 语境）：

```bash
docker build -t pft-backend:0.1 backend/
docker run --rm -p 8000:8000 pft-backend:0.1
# 另开终端：
curl http://127.0.0.1:8000/api/health   # 期望 {"status":"ok"}
```

**实测验收（D1，2026-09-22 已通过）**：

- 构建：`docker build -t pft-backend:0.1 backend/` 成功，`ghcr.io/astral-sh/uv:latest` 直连拉取成功（12.2 步骤 6 预警的 ghcr.io 风险本机未发生，但「mirrors 不覆盖 ghcr.io」的机制结论不变）；
- 体积：`docker images` 显示 CONTENT SIZE **79.9MB**（真实镜像层）；构建日志 exporting 阶段的 MB 数只是中间层、DISK USAGE 324MB 含与 `python:3.14-slim` 共享的底层——都别当镜像增量（坑见 12.9）；
- 运行：日志 `Uvicorn running on http://0.0.0.0:8000`（考点三验证）；`/api/health`、`/docs`、`/openapi.json`、`/redoc` 全返回 200；访问日志来源 IP `172.17.0.1`（docker bridge 网关）= 宿主机 → 容器网络路径走通；
- 待补一环：改一行业务代码重建，观察依赖层应显示 `CACHED`（层缓存考点闭环，建议实测一次）。

### 12.5 数据持久化（named volume）—— D2 演练四阶段

> **前置提醒**（已核实接口约束）：容器内是全新空库，`POST /api/faults` 的 `pipeline_id` 是外键、流水线必须已存在——登记故障前先 `POST /api/pipelines` 建一条（如 `{"code":"LINE-A","name":"一号线"}`）；字段约束：`location` 2~200 字、`symptom` 5~1000 字、`occurred_at` ISO 8601 且不晚于当前时间。

**阶段 A：丢数据演示（为什么需要卷）**

```bash
docker run --rm -p 8000:8000 pft-backend:0.1   # 无卷
# 登记一条故障（先建流水线）→ 确认列表 total = 1
# Ctrl+C 停容器（--rm 自动删除）
docker run --rm -p 8000:8000 pft-backend:0.1   # 再起同镜像
# 列表 total = 0 —— db 落在容器可写层（copy-on-write），容器删了数据就没了
```

**阶段 B：named volume 持久化（验收核心）**

```bash
docker run --rm -p 8000:8000 -v pft-data:/app/data \
  -e DATABASE_URL=sqlite:///./data/fault_tracker.db pft-backend:0.1
# 登记一条故障 → Ctrl+C 删容器 → 同命令重建 → 列表 total 保持 1（数据不丢）
# docker volume ls / docker volume inspect pft-data 复核
```

验收：跨容器重建数据不丢；能说清 named volume 与 bind mount 的差异与选型（见 6.2）。

**阶段 C（选做）：bind mount 对比**

```bash
docker run --rm -p 8000:8000 -v ~/pft-bind:/app/data \
  -e DATABASE_URL=sqlite:///./data/fault_tracker.db pft-backend:0.1
# 宿主机 ls ~/pft-bind 可直接看到 db 文件（named volume 则藏在 /var/lib/docker/volumes）
```

**阶段 D：不可逆演练心智**

`docker volume rm pft-data` = 删数据，属不可逆操作，练「先备份再删」：

```bash
docker run --rm -v pft-data:/data -v ~/pft-backup:/backup busybox tar czf /backup/pft-data.tar.gz /data
#（临时起一个 busybox 容器，把卷打成 tar 存到宿主 ~/pft-backup；备份手法同 6.4，不一定要真删卷。）
```

> **执行状态**：四阶段命令已交付，实际执行结果（阶段 B 重建后 total 是否保持）待用户操作后确认。

### 12.6 frontend 两阶段构建 + nginx 同源代理

> **产物状态（2026-09-23）**：`frontend/Dockerfile`、`frontend/nginx.conf`、`frontend/.dockerignore`、`frontend/.npmrc` 均已落地（commit `7ab3d84`，仓库实际文件即下述内容）；nginx.conf 当前为 **D4 compose 编排形态**（`proxy_pass http://backend:8000`，服务名直连），D3 单容器试跑阶段的 `host.docker.internal` 形态见 git 历史。D3 已实测构建通过（见本节末尾）。

`frontend/.dockerignore`：

```
# 构建上下文排除清单：避免把本机 node_modules / 旧构建产物上传给 daemon
node_modules/
dist/
.env
.env.local
```

`frontend/.npmrc`（关键文件——lock 里写死的 npmmirror 源已不可达，靠此强制走官方源）：

```
# npm 源配置（项目级）：package-lock.json 的 resolved 字段写死了旧镜像源 npmmirror，
# 而 npmmirror CDN 当前不可达（ETIMEDOUT / 403）。replace-registry-host=always
# 让 npm ci 忽略 lock 里的主机、统一走下方 registry（npm 8.3+ 支持，Node 16.20.2 自带 npm 8.19）。
registry=https://registry.npmjs.org/
replace-registry-host=always
```

`frontend/Dockerfile`：

```dockerfile
# ---- stage 1：构建（Node 16 系；lockfileVersion 2 与 npm 8 兼容）----
FROM node:16.20.2-alpine AS build
WORKDIR /app
# 先拷声明文件再 npm ci：层缓存——改业务代码不重装依赖（与 backend 同考点）
# .npmrc 必须在 npm ci 之前进入镜像：lock 的 resolved 写死 npmmirror（旧镜像源已不可达），
# 靠 replace-registry-host=always 强制走官方源（见 .npmrc 注释）
COPY package.json package-lock.json .npmrc ./
RUN npm ci
COPY . .
# 坑点：VITE_* 是【构建期】替换，ARG 不传会被拼成字符串 "undefined" 进请求路径。
# 同源部署必须显式传空串（相对路径 /api/... 由 nginx 代理），故默认值设为空。
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# ---- stage 2：仅 nginx + 静态产物（终镜像不含 node 工具链，体积小）----
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

`frontend/nginx.conf`：

```nginx
# nginx 站点配置：静态托管 + API 同源反向代理（覆盖官方默认 default.conf）。
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # SPA 回退：前端是 createWebHistory 模式（URL 无 #），刷新或直达
    # /faults/xxx 这类子路由时，nginx 找不到对应文件，必须回退到 index.html
    # 交给 vue-router 处理（router/index.ts 注释明确要求生产服务器做此回退）。
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理：浏览器请求发到本容器（8080，同源），由 nginx 转发给后端。
    # 同源之后浏览器不再跨域，后端 CORS 白名单自然不再需要（对比 dev 模式 5173→8000）。
    #
    # 注意：compose 编排下用【服务名】backend 访问后端（同一网络内 DNS 解析），
    # 不是 localhost 也不是宿主机地址——这是容器互访的核心规则。
    # D3 单容器试跑阶段的 host.docker.internal 形态见 git 历史或文档。
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

- **VITE_API_BASE_URL 坑**：构建期替换，`ARG` 不传 = undefined = 请求路径变 `undefined/api/...`（通用机理见 11.4）；**必须显式传空串**走同源（产物 Dockerfile 已把默认值设为空）；
- **compose 编排下**（D4）：nginx.conf 用服务名 `backend:8000` 直连后端（同一 compose 网络内 DNS 解析，见 8.3）；D3 单容器试跑阶段曾用 `host.docker.internal:8000` 指向宿主机（需 `--add-host=host.docker.internal:host-gateway`，见 7.4），已演进为当前服务名形态；
- **.npmrc 必须在 npm ci 前进入镜像**：`package-lock.json` 的 `resolved` 写死了 npmmirror（旧源已不可达），`.npmrc` 的 `replace-registry-host=always` 强制走官方源；漏拷会导致 `npm ci` 超时失败；
- 两阶段构建为何镜像小见 5.4。

**实测验收（D3，2026-09-23 已通过）**：

- 构建：`docker build -t pft-frontend:0.1 frontend/` 成功，`.npmrc` 源替换生效、`npm ci` 顺利走完；
- 体积：`docker images` 显示 CONTENT SIZE **26.7MB**（nginx:alpine + 静态产物，两阶段构建生效——终镜像不含 node 工具链）；
- D3 单容器试跑操作步骤（bash 语境，D4 compose 编排时直接用 `docker compose up`）：

```bash
cd ~/pipeline-fault-tracker/frontend
docker build -t pft-frontend:0.1 .
docker run --rm -p 8000:8000 pft-backend:0.1 &          # 先起 backend（后台）
docker run --rm -p 8080:80 --add-host=host.docker.internal:host-gateway pft-frontend:0.1
```

> D3 单容器试跑阶段 nginx.conf 尚为 `host.docker.internal` 形态；当前仓库已演进为 D4 服务名形态，上述步骤仅供理解 D3→D4 演进过程。

验收（按计划 D3 标准）：浏览器开 `http://127.0.0.1:8080` 走通列表/登记/详情；Network 面板无 CORS 报错（同源）；能说清两阶段构建为何镜像小（终镜像不含 node 工具链）。

### 12.7 Compose 编排

> **⚠️ 形态提示（2026-09-30）**：本节是 **D4 阶段的 SQLite + bind mount 双服务形态**，保留作教学历史。**当前仓库实际 `docker-compose.yml` 已在 P3 迁移为 PostgreSQL + named volume 三服务，见 12.13**。下述内容与当前实际文件不一致，仅反映 D4 当时形态。

根目录 `docker-compose.yml`（compose v2 亦可命名 `compose.yaml`）：

```yaml
# 编排定义：一条命令起前后端双服务（D4 练习）。
# 使用：docker compose up -d --build
# 停止：docker compose down
# 注意：backend 用 bind mount（~/pft-bind）持久化，数据落在宿主机目录；
# down / down -v 都不会删它（down -v 只删 named volume），手动删目录才丢数据

services:
  backend:
    build: ./backend
    environment:
      # 与挂载点对齐：数据库文件落在容器内 /app/data（bind mount 到宿主机 ~/pft-bind）
      DATABASE_URL: sqlite:///./data/fault_tracker.db
    volumes:
      # bind mount：数据库直接落在宿主机（WSL 家目录）的 ~/pft-bind 下，
      # 可直接 ls/备份；与 D2 的单容器命令形态一致
      - ~/pft-bind:/app/data
    healthcheck:
      # slim 镜像无 curl，用系统 python 的 urllib 探活（探活端点 /api/health）
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 5

  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      backend:
        # 关键概念：depends_on 只保证【启动顺序】，不保证【就绪】；
        # 加 condition: service_healthy 后，等 backend 健康检查通过才启动 frontend
        condition: service_healthy
```

- healthcheck 用 python urllib：slim 镜像无 curl（见 8.4）；
- nginx 里 `proxy_pass http://backend:8000` 用的正是**服务名**（服务名即 DNS，见 8.3）；
- `depends_on` + `condition: service_healthy` 才管「就绪」、不管则只管启动顺序（见 11.6）；
- **bind mount 替代 named volume**：D4 实际采用 `~/pft-bind:/app/data`（与 D2 阶段 C 的 bind mount 形态一致），数据直接落在宿主机目录，`docker compose down` 甚至 `down -v` 都不会删它（`down -v` 只删 named volume），手动删 `~/pft-bind` 才丢数据。

### 12.8 部署与验证命令集（按 D1→D4 顺序，bash 语境）

```bash
# D1 backend（已实测验收通过，见 12.4）
cd ~/pipeline-fault-tracker
docker build -t pft-backend:0.1 backend/
docker run --rm -p 8000:8000 pft-backend:0.1 &
sleep 3
curl http://127.0.0.1:8000/api/health          # {"status":"ok"}

# D2 持久化（见 12.5，卷建好后删容器重建验证数据不丢）

# D3 frontend
docker build -t pft-frontend:0.1 frontend/
docker run --rm -p 8080:80 pft-frontend:0.1    # 浏览器 http://127.0.0.1:8080

# D4 compose 全闭环
docker compose up -d --build
docker compose ps                              # 关注健康状态列
# 浏览器 http://127.0.0.1:8080 走通列表/登记/详情；Network 面板无 CORS 报错

# 持久性验收：down 不带 -v 再 up，数据仍在
docker compose down
docker compose up -d
# bind mount 下 down / down -v 都不删数据（只删 named volume），手动删 ~/pft-bind 才丢
```

> Windows 侧访问：容器跑在 WSL2 内，浏览器直接访问 `http://127.0.0.1:8080` 即可（WSL2 localhost 转发默认开启）。

### 12.9 本项目专属坑点（补充）

- **uv 路线替代 pip 路线**：旧计划 D1 的 `requirements.lock.txt` 已删，照抄会构建失败，以 12.4 为准；
- **同源后 CORS 不再是问题**：dev 模式跨源靠后端 CORS 白名单放行 5173；容器化后浏览器与 API 同源，`cors_origins` 不再参与（代码仍加载，无副作用）；
- **DATABASE_URL 必须指向卷内路径**（`sqlite:///./data/fault_tracker.db` 相对 `/app`，落在 pft-data 卷）；若用默认值 `sqlite:///./fault_tracker.db`，db 落在可写层，删容器即丢数据；
- **healthcheck 用运行时自带的 python**，不要用 curl（slim 无 curl）；
- **Node 镜像选 `node:16.20.2-alpine`**：与本地 `dev.bat` 的 `nvm use 16.20.2` 对齐（engines 仅声明 >=16，锁定 16 可避免「本地 16、容器 22」的版本漂移争议）；
- **宿主机端口冲突**：8000 常被本地 dev 的 uvicorn 占用（本机实测过其他目录进程占用 8000）；容器映射 8000 前先确认端口归属，或改映射为 `8001:8000`；
- **镜像体积别读错数**：`docker build` 日志 exporting 阶段的 MB 数是中间层；看 `docker images` 的 **CONTENT SIZE**（本项目 pft-backend:0.1 实测 79.9MB、pft-frontend:0.1 实测 26.7MB）才是镜像自身层；DISK USAGE 含共享底层，不能当镜像增量；
- **.npmrc 必须在 npm ci 前 COPY 进镜像**：`package-lock.json` 的 `resolved` 写死了 npmmirror 旧源（ETIMEDOUT / 403），`.npmrc` 靠 `replace-registry-host=always` 强制走官方源；漏拷 `.npmrc` → `npm ci` 超时失败。

### 12.10 D5 —— 排障演练 + 镜像优化 + 收尾决策

> D5 是 Docker 学习计划的收官环节，验收标准：独立定位并修复一个埋雷；产出镜像体积对照表。本节给出四部分操作手册，具体执行在 WSL 终端完成。

**Part 1：排障三件套——工具分工心智模型**

| 工具 | 问什么问题 | 典型命令 |
|---|---|---|
| `docker logs` | 发生了什么（应用输出） | `docker compose logs --tail=30 backend` |
| `docker exec` | 现场长什么样（容器内文件 / 环境变量） | `docker compose exec backend sh` → `ls /app/data`、`env \| grep DATABASE` |
| `docker inspect` | 被配置成什么（运行态真相） | `docker inspect <容器> \| grep -A5 Health` |
| `docker system df` | 磁盘占用总览 | 排障收尾清理用 |

compose 场景常用只读命令速查：

```bash
docker compose ps                        # 服务状态 + 健康状态列
docker compose logs --tail=30 backend    # 后端日志（-f 持续跟踪）
docker compose exec backend sh           # 进容器现场勘验
docker compose exec frontend cat /etc/nginx/conf.d/default.conf   # 看容器内生效的 nginx 配置
```

**Part 2：埋雷演练（在 WSL 副本操作，不改仓库文件）**

**主雷：改坏 nginx 后端地址**

```bash
# 在 WSL 副本侧：
sed -i 's|backend:8000|backend:9000|' frontend/nginx.conf
docker compose up -d --build frontend
```

- 预期现象：浏览器开 `http://127.0.0.1:8080`，页面框架加载但 API 数据全部 502；
- **考点**：nginx.conf 是构建期 `COPY` 进镜像的（不是 volume 挂载），改本地文件后必须**重建镜像**（`--build`）才生效，`docker compose restart` 无效——restart 只重启容器，不重建镜像；
- 定位方法：`docker compose logs frontend` 看 nginx 错误日志，会看到 `connect() failed (111: Connection refused) while connecting to upstream`，upstream 地址是 `backend:9000`；
- 修复：`sed` 改回 `backend:8000` + `docker compose up -d --build frontend`，或直接 `docker compose exec frontend` 进容器 `vi` 改 + `nginx -s reload`（临时生效，不改镜像）。

**加练雷：改坏健康检查端点**

```bash
# 在 WSL 副本侧 docker-compose.yml 里：
# 把 healthcheck 的 /api/health 改成 /api/nonexistent
docker compose up -d --build
```

- 预期现象：`docker compose ps` 显示 backend `(health: starting)` → 等 retries 耗尽 → `(unhealthy)`；frontend 因 `depends_on: condition: service_healthy` **卡住不启动**；
- 考点：验证 11.6「`depends_on` 只管启动顺序不管就绪」的反面——加了 `service_healthy` 后，backend 不健康 = frontend 永远等；
- 定位：`docker inspect <backend 容器> | grep -A10 Health` 看 LastExitCode 与非 200 响应。

**Part 3：镜像优化实验与对照表**

**实验 1：层缓存实证**——改一行 `backend/app/main.py`（如加一行注释），重建：

```bash
docker build -t pft-backend:0.1 backend/
# 观察输出：RUN uv sync 层应显示 CACHED（依赖未变）；只有 COPY app/ 及之后的层重跑
```

**实验 2：.dockerignore 效果**——临时移走 `.dockerignore`，重建对比 `transferring context` 体积。

**本项目优化对照表**：

| 手段 | 本项目状态 | 若未采用的体积估算 |
|---|---|---|
| `.dockerignore` | 已采用（排除 .venv/、node_modules/、*.db 等） | 上下文体积膨胀，构建变慢 |
| `--no-cache`（uv sync） | 已采用 | uv 缓存目录进镜像，多占数十 MB |
| slim 基础镜像 | `python:3.14-slim` | `python:3.14`（bookworm 全量）约 300MB+ vs slim 约 100MB+ |
| 多阶段构建（frontend） | node 构建 → nginx 托管 | 单阶段含 node 工具链约 350MB+ vs 两阶段 26.7MB |
| 声明文件先 COPY | pyproject.toml/uv.lock 与 package.json/package-lock.json 均前置 | 改一行业务代码触发全量依赖重装 |

**Part 4：收尾两项决策**

1. **产物归属**：`docker-compose.yml` 是否以 `chore(docker):` 独立提交入库（D1~D3 六个产物已 commit `7ab3d84`）；还是保持未跟踪、留作练习产物；
2. **可选进阶**：`entrypoint.sh` 先 `alembic upgrade head` 再启 uvicorn——让表结构跟随代码版本演进，与当前 `create_all(checkfirst=True)` 的分工（前者管表结构变更、后者管首次建表）和回退风险需讨论；涉代码改动，按规则 2.2 另行确认，本节不预写方案。

---

### 12.11 与计划及后续的关系

- 本节是 _docker_plan.md Session 0 + D1~D5 的「文档化 + uv 路线修正版」；当前进度：Session 0 + D1~D3 已完成（D1~D3 产物已 commit `7ab3d84`），D4 compose 已验证闭环（SQLite 形态，见 12.7/12.8），D5 操作手册已完整交付（排障 / 埋雷 / 优化实验，见 12.10）——D5 的具体执行结果（埋雷定位修复、CACHED 观察、上下文体积对比）待用户反馈；
- **P3（阶段二）已完成（2026-09-30）**：compose 从 D4 的 SQLite + bind mount 双服务迁移为 PostgreSQL + named volume 三服务，app 代码仅 database.py 加方言分支、业务层零改动；实测三容器 healthy、业务闭环 + 错误路径 + 持久化 + 测试双方言全绿（详见 12.13）；
- 后续两项决策待用户回复：① `docker-compose.yml` 是否以 `chore(docker):` 独立提交入库；② 是否启用 `entrypoint.sh` 先 `alembic upgrade head` 再启 uvicorn（涉代码改动 + 回退风险讨论，按规则 2.2 另行确认）。

### 12.12 临时公网演示：内网穿透暴露本地 compose 栈（2026-09-30 实测）

> 定位：想把本机跑起来的 compose 栈发给别人用浏览器临时看，又不想买服务器/备案时的路线。原理：cloudflared 容器主动向 Cloudflare 边缘建立出站连接，边缘节点把公网 URL 的流量回灌进来——**不需要公网 IP、不需要开端口**。代价：链接依赖本机开机 + WSL 运行，URL 临时（隧道容器重启即变）。

**前置**：compose 栈可正常起（12.7/12.8）；Docker Hub 拉镜像可达（cloudflare/cloudflared 在 Docker Hub，镜像加速器可代理）。

**步骤（bash 语境，WSL 内）**：

```bash
# 1. 起栈（复用既有镜像，不带 --build——理由见本节坑点 1）
cd <仓库目录>
docker compose up -d

# 2. 本地验证
curl -s http://localhost:8080/api/health   # 期望 {"status":"ok"}

# 3. 起隧道（容器方式，不装宿主机二进制）
docker run --rm -d --name pft-tunnel \
  --add-host=host.docker.internal:host-gateway \
  cloudflare/cloudflared:latest tunnel --url http://host.docker.internal:8080

# 4. 取公网 URL
docker logs pft-tunnel 2>&1 | grep -o "https://[a-z0-9-]*\.trycloudflare\.com" | head -1
```

5. 公网路径验证（Windows 侧或手机）：curl 该 URL 的 `/` 与 `/api/health` 均 200 才算通——只测 localhost 不算验证。

**关键参数**：

- `--rm`：stop 后容器自动删除，临时工具不留环境（规则 2.5「用完即卸载」）；
- `--add-host=host.docker.internal:host-gateway`：Linux/WSL 下容器内默认不解析 `host.docker.internal`，此行把它映射到宿主机；缺了隧道够不到 8080；
- 指向 8080 一个入口即可：frontend nginx 同源代理（12.6），前端页面与 `/api` 全走它。

**生命周期与收摊**：

| 操作 | 命令 |
|---|---|
| 关链接 | `docker stop pft-tunnel`（`--rm` 连带删容器，URL 秒失效） |
| 全栈收摊 | `docker compose down`（数据保留在 `~/pft-bind`，见 12.7） |
| 次日再演示 | `docker compose up -d`（不带 --build）+ 重跑步骤 3/4，URL 会变 |
| 清理镜像 | `docker rmi cloudflare/cloudflared:latest`（不长期演示时） |

**坑点（2026-09-30 实测）**：

1. `up -d --build` 卡 20 分钟无输出：构建上下文新增目录（P1 加的 `tests/`）使 COPY 层缓存失效，构建内 `uv sync` 拉官方 PyPI 挂起；**进镜像的 app 代码零变化时**（判定依据：上次构建后的提交只动 `tests/`、`.github/`、文档），直接 `up -d` 不带 --build 复用既有镜像，秒级起栈；
2. 卡死的 wsl 会话无法用第二个 wsl 调用 pkill（并发实例竞争 E_ACCESSDENIED）；解法是从 Windows 侧 `taskkill` 该会话对应的 wsl.exe 客户端 PID（沙箱内拒绝访问，需提权执行）；
3. **安全边界**：链接持有者 = 完整读写权限（本系统无认证），只发给要看的人，演示完立即关链接。

**实测记录**：首条链接 `https://deserve-kinase-witness-between.trycloudflare.com` 公网 root 200、`/api/health` 200（2026-09-30）；撰写时该隧道仍在线，URL 仅作格式示例、不保证仍有效。

### 12.13 P3：compose 迁移到 PostgreSQL（当前仓库实际形态，2026-09-30 实测）

> **产物状态（2026-09-30）**：P3 已把根目录 `docker-compose.yml` 从 D4 的「SQLite + bind mount 双服务」改为「PostgreSQL + named volume 三服务」，本节代码块与当前仓库实际文件**逐字对齐**。**12.7 的 SQLite 形态保留作 D4 教学历史**，当前实际以本节为准。迁移走**路径 a（保守）**：建表仍靠 backend 启动的 `create_all(checkfirst=True)`，Alembic 未接入 PG（仅作练习产物）。涉及 app 代码只改了一处方言分支（见下），crud / routers / schemas / models 等业务代码**零改动**。

**当前 `docker-compose.yml`（三服务，逐字对齐仓库）：**

```yaml
# 编排定义：一条命令起 PostgreSQL + 前后端三服务（P3：SQLite → PostgreSQL）。
# 使用：docker compose up -d --build
# 停止：docker compose down（保留数据卷）/ down -v（连 pft-pgdata 一起删）
# 数据持久化：PG 数据落在 named volume pft-pgdata，down 不删、down -v 才删；
# 与 D4 的 SQLite bind mount（~/pft-bind）形态不同，本次改为服务端 PG + named volume。

services:
  postgres:
    image: postgres:16-alpine
    environment:
      # 首次启动时 postgres 镜像用这三个变量初始化库/用户/密码（仅空数据卷时生效）
      POSTGRES_DB: pft
      POSTGRES_USER: pft
      POSTGRES_PASSWORD: pft_pass
    volumes:
      # named volume：PG 数据目录持久化，容器重建不丢；down -v 才会删
      - pft-pgdata:/var/lib/postgresql/data
    healthcheck:
      # pg_isready 是 postgres 镜像自带的就绪探针，比 TCP 探活更准（等的是“能接受连接”）
      test: ["CMD-SHELL", "pg_isready -U pft -d pft"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build: ./backend
    environment:
      # 方言切换点：URL scheme 换成 postgresql+psycopg 即驱动 SQLAlchemy 用 psycopg 连 PG；
      # host 用 compose 服务名 postgres（同网络内 DNS 解析），端口 5432；建表靠启动 create_all
      DATABASE_URL: postgresql+psycopg://pft:pft_pass@postgres:5432/pft
    depends_on:
      postgres:
        # 等 PG 健康（能接受连接）再启 backend，否则 backend 启动即连库会失败
        condition: service_healthy
    healthcheck:
      # slim 镜像无 curl，用系统 python 的 urllib 探活（探活端点 /api/health）
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 5

  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      backend:
        # 关键概念：depends_on 只保证【启动顺序】，不保证【就绪】；
        # 加 condition: service_healthy 后，等 backend 健康检查通过才启动 frontend
        condition: service_healthy

volumes:
  # named volume 声明：PG 数据目录，生命周期独立于容器（down 不删、down -v 才删）
  pft-pgdata:
```

**与 D4（12.7）SQLite 形态的差异：**

| 维度 | D4（12.7，SQLite） | P3（本节，PostgreSQL） |
|---|---|---|
| 服务数 | 2（backend + frontend） | 3（**postgres** + backend + frontend） |
| `DATABASE_URL` | `sqlite:///./data/fault_tracker.db` | `postgresql+psycopg://pft:pft_pass@postgres:5432/pft` |
| 持久化 | bind mount `~/pft-bind:/app/data` | **named volume** `pft-pgdata` |
| `down -v` 后果 | 不删数据（bind mount 不受影响，须手动删目录） | **删数据**（named volume 被删） |
| 启动依赖链 | frontend 等 backend healthy | **backend 等 postgres healthy** → frontend 等 backend healthy |
| Enum 落库 | VARCHAR + CHECK 约束 | **PG 原生 ENUM 类型** `faultstatus` |
| 新增依赖 | 无 | **psycopg[binary]**（运行时依赖，进镜像；见 DEPENDENCIES.md 第十节） |

**方言切换点（唯一改动的 app 代码）—— `backend/app/database.py`：**

`DATABASE_URL` 的 scheme 从 `sqlite` 换成 `postgresql+psycopg` 即驱动 SQLAlchemy 用 psycopg 连 PG；但 SQLite 专属的 `check_same_thread` 参数 psycopg **不认**（传进去 TypeError），故 engine 按方言分支：

```python
_is_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine: Engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=_connect_args,
)
```

**双方言测试 —— `backend/tests/conftest.py`：**

测试库默认仍是内存 SQLite（零依赖，与引入 PG 前行为**逐字一致**）；设 `TEST_DATABASE_URL` 可整套切到 PG，验证「同一套测试跑两种方言」。test_engine 同样按方言分支（PG 不传 `check_same_thread`、不用 StaticPool）：

```python
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["DB_ECHO"] = "false"
```

```python
if _TEST_DB_URL.startswith("sqlite"):
    test_engine: Engine = create_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    test_engine: Engine = create_engine(_TEST_DB_URL)
```

> **测试连 PG 的通路坑**：backend 的 `.venv` 是 Windows venv，pytest 只能在 Windows 侧跑；而 compose 的 postgres 未对宿主发布端口。要在 Windows 侧用 pytest 连 PG，需另起一个**发布端口的临时 PG 容器**（如 `-p 5433:5432`），借 WSL2 localhost 转发让 Windows 可达；用完 `docker rm -f` 清理，**不动 committed compose**。

**SQLite ↔ PG 并存切换（P3 验收项）：**

- `config.py` 默认值**未改**，仍 `sqlite:///./fault_tracker.db`；PG 只由 compose 的环境变量注入。
- 因此「本地 SQLite 开发库」与「PG 容器库」天然并存：本地 `uv run uvicorn`（无 `.env`）走 SQLite，`docker compose up` 走 PG，二者数据**互不相通**、切换只改 `DATABASE_URL` 一个环境变量。

**实测验证证据（2026-09-30，全绿）：**

| 验证项 | 结果 |
|---|---|
| 三容器状态 | postgres / backend `(healthy)`、frontend Up；依赖链 postgres→backend→frontend 正确 |
| PG 建表 | `\dt` 见 `pipelines` + `pipeline_faults` 两表（`create_all` 建成） |
| 原生 ENUM | `\dT+` 见 `faultstatus`（pending/processing/done）——与 SQLite 的 VARCHAR+CHECK 不同 |
| 业务闭环 | 经 nginx `:8080/api`：建流水线 → 登记故障 → 列表/详情 → 改 location → pending→processing→done（closed_at 写入），中文全链路无损 |
| 错误路径 | done 不可逆 **409**、重复 code **409**、非法枚举 **422** |
| 持久化 | 基线 1/1 → `down`（容器+网络全删、卷 `pft-pgdata` 仍在）→ `up` → 重计数仍 **1/1**、API `total:1` |
| 测试双方言 | SQLite `uv run pytest` **72 passed (0.84s)**；PG（临时容器 + `TEST_DATABASE_URL`）**72 passed (10.58s)** |

**本节专属坑点（2026-09-30 实测）：**

1. **管道喂 bash 执行脚本被吞**：`sed 's/\r$//' x.sh | bash` 时，脚本里的 `docker compose exec -T` / `psql` 会继承同一 stdin，把脚本剩余行当自己输入读走 → 脚本**静默中断**（`down` 根本没执行、容器仍在跑）。修法：先落临时文件再 `bash /tmp/x.sh`，让脚本走独立文件 FD 与 stdin 分离。
2. **明文密码连接串触发沙箱拦截**：命令里带 `postgresql+psycopg://user:pass@...` 时 `uv.exe`/`python.exe` 报「拒绝访问」（无显式 SANDBOXING 标记，但去掉凭据即可跑）；须在沙箱外执行。凭据也**不写入长期记忆**（用占位符）。
3. **PG 比 SQLite 慢一个数量级**：同一套 72 测试 SQLite 0.84s、PG 10.58s——网络往返 + 服务端库开销，属正常，不是回归。
4. **首次 `up --build` 可能很慢**：`uv sync --no-cache` 从官方 PyPI 直连拉包（镜像加速器只代理 Docker Hub、**不覆盖 PyPI**），实测可达 700s+；耐心等 `Downloaded` 行推进，勿误判死锁去 taskkill（判死锁前先确认是否真零进展）。

### 12.8 M9 部署形态定稿（2026-11-10，覆盖上文 D4 时期叙述）

> 第三阶段 M9 把容器编排**定稿为「SQLite 默认主线 + PostgreSQL 可选覆盖」**，本节上方 D4/D5 以 PG 为默认形态的 compose 代码块与结论属历史演练态，以本小节为准。交付文档口径见 [../README.md](../README.md) 第十一节「Docker 部署」。

四处关键变更（产物已与代码逐字对齐）：

1. **compose 双文件**：`docker-compose.yml` 默认 SQLite——`DATABASE_URL: sqlite:////app/data/fault_tracker.db`（注意四斜杠的容器内绝对路径）+ named volume `pft-data:/app/data`，无 postgres 服务；`docker-compose.pg.yml` 为覆盖文件，`docker compose -f docker-compose.yml -f docker-compose.pg.yml up -d --build` 才叠加出 postgres 服务并把 backend 方言切到 `postgresql+psycopg://`、追加 `depends_on: postgres (service_healthy)`。合并语义：标量按覆盖、映射/列表按键追加。
2. **迁移接入启动（推翻早期「entrypoint 暂不实施」决策）**：新增 `backend/entrypoint.sh`——`set -e` → `uv run --no-sync alembic upgrade head` → `exec "$@"`（PID 1 交 uvicorn，正确透传 SIGTERM）。Dockerfile 由纯 `CMD` 改为 `ENTRYPOINT ["/app/entrypoint.sh"] + CMD [uvicorn…]`，并 `COPY entrypoint.sh` 后 `RUN sed -i 's/\r$//' … && chmod +x …`（**Windows 侧写的 .sh 可能带 CRLF，容器内 shebang 会变 `#!/bin/sh\r` 直接报错，必须先剥 CR**）。`alembic upgrade head` 靠 `alembic_version` 表幂等，容器反复重启不清库不重迁；`alembic`/`psycopg` 均为运行时依赖，`uv sync --no-dev` 保留。
3. **密钥与管理员不写死**：compose 用 `SECRET_KEY: ${SECRET_KEY:?…}` 强制根目录 `.env` 提供（缺失拒绝启动，不回退代码默认密钥）；新增 `backend/create_admin.py`（读 `settings.admin_*`，幂等、账号已存在即跳过且**绝不重置已有密码**），与 `seed.py` 一同 `COPY` 进镜像，经 `docker compose run --rm backend uv run --no-sync python create_admin.py` 调用。
4. **backend 加 `TZ: Asia/Shanghai`（2026-11-12 时区缺陷修复附带）**：容器默认 UTC 而用户在北京，旧代码的时间口径隐式读【进程时区】→ 登记“此刻”被误判为未来 8 小时（422）、`created_at` 早 8 小时。应用层已改为只看 `settings.business_utc_offset_hours`（默认 8，见 `backend/app/timeutil.py`），**不设 TZ 也不会算错**；compose 里的 `TZ` 只让容器日志时间戳与业务口径一致，便于运维对时。`python:3.14-slim` 自带 tzdata，`TZ` 直接生效（已实测 `time.tzname` 由 `('UTC','UTC')` 变 `('CST','CST')`）。

已实测（静态）：空库 `alembic upgrade head` 建全五表至 head `105a10b2f697`；`create_admin.py` 临时库 18 项断言全绿；`docker compose config` 校验 SQLite 主线 / PG 合并 / 缺 `SECRET_KEY` 被拒三种结果均符预期。**运行态 `up -d`、重启保数据、容器内首启迁移交用户自验**（PG 形态经 alembic 建全表未实盘，见 README 已知问题）。

---

## 十三、命令速查表

### 13.1 镜像

| 命令 | 作用 |
|---|---|
| `docker pull <镜像>` | 拉取镜像 |
| `docker build -t <名:tag> <上下文>` | 构建镜像 |
| `docker tag <源> <目标>` | 打标签 |
| `docker push <镜像>` | 推送到 registry |
| `docker images` | 列出本地镜像 |
| `docker rmi <镜像>` | 删除镜像 |
| `docker image prune` | 清理悬空镜像 |
| `docker history <镜像>` | 看镜像分层 |

### 13.2 容器

| 命令 | 作用 |
|---|---|
| `docker run [选项] <镜像> [命令]` | 新建并启动容器 |
| `docker ps` / `ps -a` | 列出运行中 / 全部容器 |
| `docker start` / `stop` / `restart` / `kill` | 启动 / 停止 / 重启 / 强杀 |
| `docker rm [-f] <容器>` | 删除容器 |
| `docker exec -it <容器> sh` | 进入容器 |
| `docker logs [-f] [--tail N] <容器>` | 看日志 |
| `docker inspect <容器>` | 看运行态配置 |
| `docker cp` | 容器 ↔ 宿主机拷文件 |
| `docker stats` | 资源占用 |

### 13.3 卷与网络

| 命令 | 作用 |
|---|---|
| `docker volume ls` / `create` / `inspect` / `rm` | 卷管理（`rm` 不可逆） |
| `docker network ls` / `create` / `rm` | 网络管理 |
| `docker run -v <卷>:<路径>` | 挂载卷 |
| `docker run -p <宿:容>` | 端口映射 |

### 13.4 Compose（v2）

| 命令 | 作用 |
|---|---|
| `docker compose up -d --build` | 构建并后台启动 |
| `docker compose ps` | 查看服务状态 |
| `docker compose logs -f <服务>` | 跟踪日志 |
| `docker compose exec <服务> sh` | 进入服务容器 |
| `docker compose down` | 停止并删除容器与网络（保留卷） |
| `docker compose down -v` | 连卷一起删（危险） |

### 13.5 清理与诊断

| 命令 | 作用 |
|---|---|
| `docker system df` | 磁盘占用总览 |
| `docker system prune [-a]` | 清理无用对象 |
| `docker events` | 事件流 |
| `docker --version` / `docker compose version` | 版本自检 |

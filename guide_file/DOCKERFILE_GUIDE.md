# Dockerfile 完整指令速查

> 通用参考文档，不限于本项目；语法基准为 `docker/dockerfile:1`（BuildKit 前端，Docker 20.10+ 默认启用）。
>
> 每章末尾的「本项目实证」关联仓库根目录 [Dockerfile](../Dockerfile) 与 [docker-compose.yml](../docker-compose.yml) 的实际用法。

---

## 目录

- 一、Dockerfile 是什么：镜像 = 指令堆叠出的只读层
- 二、FROM：基础镜像
- 三、RUN：构建期执行命令
- 四、COPY / ADD：拷贝文件
- 五、WORKDIR：工作目录
- 六、ENV / ARG：环境变量与构建参数
- 七、CMD / ENTRYPOINT：容器启动命令
- 八、EXPOSE / VOLUME：端口声明与数据卷
- 九、USER / GROUP：运行身份
- 十、HEALTHCHECK：健康检查
- 十一、ONBUILD / STOPSIGNAL / SHELL / LABEL / MAINTAINER
- 十二、多阶段构建（Multi-stage Build）
- 十三、BuildKit 专属特性（RUN --mount、heredoc）
- 十四、.dockerignore
- 十五、层缓存原理与镜像瘦身
- 十六、最佳实践清单
- 十七、指令速查总表
- 附录 A：本项目（python_learn）Dockerfile 逐行解读
- 附录 B：pipeline-fault-tracker 项目 Dockerfile 逐行解读（前后端双镜像）

---

## 一、Dockerfile 是什么：镜像 = 指令堆叠出的只读层

Dockerfile 是一个纯文本脚本，`docker build` 按顺序执行其中每条指令，**每条指令生成一个只读镜像层（layer）**，层与层叠加得到最终镜像。

```dockerfile
# 注释以 # 开头（但第一行 # syntax= 是解析器指令，不是注释）
FROM python:3.14-slim   # 第 1 层（基于基础镜像的层之上）
WORKDIR /app            # 元数据，几乎不占空间
COPY . .                # 第 2 层
RUN pip install -r requirements.txt   # 第 3 层
CMD ["python", "app.py"]              # 元数据，不产生文件系统层
```

核心规则：

1. **指令不区分大小写**，但约定全大写，便于和参数区分。
2. **构建缓存**：某层的构建上下文没变，就直接复用缓存层；一旦某层失效，**它之后的所有层全部重建**。这是「不常变的指令写前面、常变的写后面」的根本原因。
3. **容器启动 = 镜像（只读层）+ 可写层**。容器内对文件的修改写在可写层，容器删除即丢失；要持久化用 VOLUME / bind mount。
4. **构建上下文（build context）**：`docker build .` 中的 `.`。上下文里的文件会被打包发给 Docker 守护进程，所以上下文越大构建越慢——用 `.dockerignore` 排除无关文件。

解析器指令（Parser directives）：文件最顶部以 `# 指令=值` 形式书写，必须在任何指令/注释之前：

```dockerfile
# syntax=docker/dockerfile:1        # 指定 BuildKit 前端版本（启用 --mount、heredoc 等新语法）
# escape=\                          # Windows 镜像常用，换行转义符改为反斜杠
```

---

## 二、FROM：基础镜像

```dockerfile
FROM <镜像>[:<标签>] [AS <阶段名>]
```

- 每个 Dockerfile **必须以 FROM 开头**（解析器指令除外），它是所有后续层的基底。
- `AS <阶段名>` 用于多阶段构建（见第十二章）。
- 一个 Dockerfile 可以有多个 FROM（多阶段），每个 FROM 开启一个新阶段。

标签选择：

| 写法 | 说明 |
|---|---|
| `FROM ubuntu` | 等价 `ubuntu:latest`，**危险**——latest 会随时间漂移，构建不可复现 |
| `FROM ubuntu:24.04` | 固定发行版版本，可复现 |
| `FROM python:3.14-slim` | 官方瘦身版，去掉了大部分非必要工具，体积小很多 |
| `FROM python:3.14-alpine` | 基于 musl libc，最小，但编译 C 扩展常踩坑（glibc 二进制不兼容） |
| `FROM scratch` | 空镜像，用于放静态编译的单二进制（Go/Rust） |
| `FROM mcr.microsoft.com/...` | 第三方/厂商镜像仓库同样可用 |

`FROM --platform`：交叉构建指定架构的镜像。

```dockerfile
FROM --platform=linux/amd64 python:3.14-slim
# 配合 docker buildx build --platform linux/amd64,linux/arm64 做多架构构建
```

**实践建议**：
- 永远钉住具体标签（甚至 `@sha256:` 摘要），不要用 `latest`。
- 优先选 `-slim` 变体；`alpine` 只在无 C 扩展依赖或愿意自己编译时用。
- 生产镜像尽量不用大而全的 `ubuntu`/`debian` 完整版。

> **本项目实证**：`FROM python:3.14-slim`，与项目 `.python-version`/uv 锁定的 Python 版本一致，slim 版满足 uv + FastAPI 的运行需求。

---

## 三、RUN：构建期执行命令

```dockerfile
RUN <命令>                       # shell 形式，走 /bin/sh -c
RUN ["可执行文件", "参数1", ...]   # exec 形式，不经过 shell
```

**构建镜像时**执行命令，结果固化为一个新层。与 CMD 的本质区别：RUN 在 build 阶段跑，CMD 在容器启动时跑。

### shell 形式 vs exec 形式

```dockerfile
RUN echo $HOME            # shell 形式：$HOME 由 /bin/sh 展开
RUN ["/bin/echo", "$HOME"] # exec 形式：$HOME 不会被展开，原样输出字面量
```

- shell 形式可用管道、变量、通配符，绝大多数场景用它。
- exec 形式适合：镜像里没有 shell（scratch/distroless）、或需要精确控制参数不被 shell 二次解析。
- Windows 基础镜像注意：`RUN` shell 形式走 `cmd /S /C`，转义规则不同，必要时用 `# escape=\`。

### 换行续行与链式命令

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*
```

- `\` 续行把一个逻辑命令写成多行。
- `update && install && 清理` 写在**同一个 RUN** 里：分层执行时，若 install 单独一层，update 产生的缓存元数据会永久留在上一层，镜像变肥；且分开写时缓存命中 install 层会导致装到过期包。
- `set -e`：多条命令的 RUN 建议开头加，任一命令失败立即终止构建（`&&` 链本身也有此效果）。

### 常用 RUN 技巧

```dockerfile
# 失败重试（网络不稳的下载）
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

# 创建非 root 用户（构建期完成）
RUN groupadd -r app && useradd -r -g app app

# 下载二进制并校验
RUN curl -fsSL https://example.com/tool.tar.gz | tar -xz -C /usr/local/bin
```

> **本项目实证**：依赖安装层
> ```dockerfile
> RUN --mount=type=cache,target=/root/.cache/uv \
>     uv sync --no-dev --no-install-project
> ```
> 使用了 BuildKit cache mount（第十三章详解）：uv 的下载缓存跨构建复用，但不落进镜像层。

---

## 四、COPY / ADD：拷贝文件

```dockerfile
COPY [--chown=<用户>:<组>] [--chmod=<权限>] [--link] <源>... <目标>
ADD  [--chown=...] [--chmod=...] [--keep-git-dir] <源>... <目标>
```

两者都从**构建上下文**拷贝文件到镜像。区别：

| 能力 | COPY | ADD |
|---|---|---|
| 拷贝本地文件 | ✅ | ✅ |
| 自动解压本地 tar | ❌ | ✅（仅本地 tar） |
| 支持 URL 下载 | ❌ | ✅（**不推荐**，无法删缓存、无法校验） |
| 从其他构建阶段拷贝 | ✅ `--from=` | ❌ |

**官方立场：默认用 COPY，只有明确需要 ADD 的自动解压时才用 ADD。**

### 源路径规则

- 源路径是**相对于构建上下文**的，不能用 `../` 跳出上下文。
- 支持 Go 风格通配符：`COPY src/*.py /app/`、`COPY conf/**/*.json /etc/`。
- 多个源时，目标必须是目录（以 `/` 结尾）。

```dockerfile
COPY package.json yarn.lock ./     # 多源拷贝，./ 表示 WORKDIR
COPY dist/ /usr/share/nginx/html/  # 目录拷贝：拷的是 dist 里的内容，不含 dist 目录本身
COPY --chown=app:app config/ /app/config/
COPY --chmod=600 secrets.env /app/ # BuildKit 特性
```

⚠️ 目录拷贝的常见坑：`COPY dir /target/` 拷的是 **dir 的内容**，不是 dir 本身；想要 `/target/dir/` 需写 `COPY dir /target/dir/`。

### COPY --from：跨阶段/跨镜像拷贝

```dockerfile
# 从多阶段构建的前一阶段拷贝产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 直接从外部镜像拷贝二进制（免安装）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# 从具名构建参数镜像拷贝（ARG 参数化基础镜像）
ARG BASE_IMAGE=node:22
COPY --from=${BASE_IMAGE} /usr/local/bin/node /usr/local/bin/
```

`COPY --link`（BuildKit）：把拷贝作为独立层链接而非叠加，允许在基础层不变时并行构建、独立缓存，大文件拷贝提速明显。

> **本项目实证**：
> ```dockerfile
> COPY --from=ghcr.m.daocloud.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
> COPY pyproject.toml uv.lock ./    # 先只拷依赖声明文件（缓存友好）
> ...
> COPY todo_api/ ./todo_api/        # 再拷代码（常变，放后面）
> ```
> 从 uv 官方镜像直接取二进制，镜像内无需 pip install uv，也无需 curl 下载脚本。

---

## 五、WORKDIR：工作目录

```dockerfile
WORKDIR /app
```

- 设置后续 `RUN` / `CMD` / `ENTRYPOINT` / `COPY` / `ADD` 的当前目录，不存在则自动创建。
- 可多次调用，相对路径基于上一个 WORKDIR：

```dockerfile
WORKDIR /app
WORKDIR src      # 实际是 /app/src
COPY . .         # 拷进 /app/src
```

- 可用环境变量：`WORKDIR $DIRNAME`（ENV 定义后生效）。
- **不要靠 `RUN cd /some/path && ...` 代替 WORKDIR**：cd 只在当条 RUN 内生效，后续指令仍回到默认目录（`/`），且默认目录随基础镜像不同而不同（有的是 `/`，有的是 `/home/xxx`）。

> **本项目实证**：`WORKDIR /app`，后续所有 COPY 的相对目标路径都以它为基准。

---

## 六、ENV / ARG：环境变量与构建参数

### ENV：运行期 + 构建期环境变量

```dockerfile
ENV <key>=<value> ...
ENV <key> <value>          # 旧语法，不推荐
```

- 对**构建期后续指令**和**容器运行期**都生效（会写入镜像元数据，`docker run -e` 可覆盖）。
- 支持变量引用与转义：

```dockerfile
ENV APP_HOME=/app
ENV PATH="${APP_HOME}/.venv/bin:$PATH"    # 追加 PATH
ENV VERSION=1.0 \
    NAME=demo                              # 多变量续行
ENV GREETING="hello world"                 # 带空格加引号
```

### ARG：仅构建期参数

```dockerfile
ARG DEBIAN_FRONTEND=noninteractive   # 可带默认值
ARG VERSION                          # 无默认值，构建时不传则为空
```

- 只在 `docker build` 期间存在，**不进入运行中的容器**（这是与 ENV 最本质的区别）。
- 构建时传值：`docker build --build-arg VERSION=1.2 -t app .`
- **唯一的特殊 ARG**：`ARG` 可以出现在第一个 FROM 之前，供 FROM 使用：

```dockerfile
ARG BASE_TAG=3.14-slim
FROM python:${BASE_TAG}
# FROM 之前定义的 ARG 在 FROM 之后的阶段不可见，需要时须在阶段内重新声明 ARG
ARG BASE_TAG
RUN echo $BASE_TAG
```

- 预定义 ARG（不声明也可直接用）：`HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`、`TARGETPLATFORM`、`TARGETOS`、`TARGETARCH`、`BUILDPLATFORM` 等。
- ⚠️ **安全**：`docker history` 能看到 ARG 的值，**绝不用 ARG 传密钥/密码**。构建期机密用 BuildKit secret mount：

```dockerfile
RUN --mount=type=secret,id=github_token \
    GITHUB_TOKEN=$(cat /run/secrets/github_token) some-command
# 构建：docker build --secret id=github_token,env=GITHUB_TOKEN .
```

### ENV vs ARG 选择

| 需求 | 用什么 |
|---|---|
| 容器运行时要读到的配置（PATH、调试开关、默认端口） | ENV |
| 构建时可变的参数（版本号、基础镜像标签、apt 源） | ARG |
| 构建时传入、运行时也要用 | ARG 接收 → ENV 固化 |
| 机密 | 都不用，用 `--mount=type=secret` |

> **本项目实证**：
> ```dockerfile
> ENV UV_COMPILE_BYTECODE=1 \
>     UV_LINK_MODE=copy \
>     UV_PYTHON_DOWNLOADS=never \
>     PYTHONUNBUFFERED=1
> ENV PATH="/app/.venv/bin:$PATH"
> ```
> `PYTHONUNBUFFERED=1` 让 Python 日志实时输出到 `docker logs`；把 uv 建的 venv 追加进 PATH，CMD 里的 `uvicorn` 才能直接找到。

---

## 七、CMD / ENTRYPOINT：容器启动命令

两者都定义「容器启动时执行什么」，区别在于**能否被 `docker run` 后面的参数覆盖**：

| | `docker run 镜像 参数...` 时 |
|---|---|
| CMD | 参数**整体替换** CMD |
| ENTRYPOINT | 参数**追加**到 ENTRYPOINT 之后 |

### 三种写法

```dockerfile
# 1. CMD exec 形式（推荐）：不经过 shell，PID 1 就是应用本身，能正确收到 SIGTERM
CMD ["uvicorn", "todo_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# 2. CMD shell 形式：实际执行 /bin/sh -c "..."，sh 是 PID 1，可能吞掉停止信号
CMD uvicorn app:app --host 0.0.0.0

# 3. CMD 作为 ENTRYPOINT 的默认参数（只有与 ENTRYPOINT 搭配时才有此语义）
ENTRYPOINT ["python", "manage.py"]
CMD ["runserver", "0.0.0.0:8000"]
# docker run 镜像            → python manage.py runserver 0.0.0.0:8000
# docker run 镜像 shell      → python manage.py shell
```

一个 Dockerfile 只有**最后一条 CMD 生效**；ENTRYPOINT 同理。

### ENTRYPOINT 详解

```dockerfile
ENTRYPOINT ["可执行文件", "固定参数"]     # exec 形式（推荐）
ENTRYPOINT command param                # shell 形式（会忽略 CMD，且 PID 1 是 sh）
```

典型用法——把镜像做成「像命令一样」的工具：

```dockerfile
FROM alpine
ENTRYPOINT ["ping"]
CMD ["localhost"]
# docker run 镜像            → ping localhost
# docker run 镜像 baidu.com  → ping baidu.com
```

需要临时覆盖 ENTRYPOINT 时：`docker run --entrypoint /bin/sh 镜像`。

### 信号与优雅停机（重要）

- exec 形式下应用进程是 PID 1，`docker stop` 发的 SIGTERM 直达应用，可优雅关闭。
- shell 形式下 `/bin/sh` 是 PID 1，默认**不转发**信号给子进程，`docker stop` 等 10 秒后直接 SIGKILL。
- 若必须用 shell 启动（如需环境变量展开），用 `exec` 让应用替换 shell 进程：

```dockerfile
ENTRYPOINT ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
```

- 或用 `docker run --init`（compose 的 `init: true`）注入 tini 做 PID 1，处理信号转发与僵尸进程回收。

> **本项目实证**：
> ```dockerfile
> CMD ["uvicorn", "todo_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
> ```
> exec 形式 + 绑定 `0.0.0.0`（容器内绑 127.0.0.1 则宿主机端口映射不可达）。compose 里可用 `command:` 覆盖此 CMD。

---

## 八、EXPOSE / VOLUME：端口声明与数据卷

### EXPOSE

```dockerfile
EXPOSE 8000
EXPOSE 443/tcp 8080/udp
```

- **纯文档性质的声明**：告诉使用者「容器监听这个端口」，**不会真的发布端口**。
- 实际发布必须在运行时 `-p 8000:8000`（或 compose 的 `ports:`）。
- 唯一的功能性作用：同一自定义网络内容器互访时，`docker run -P`（大写）会自动发布所有 EXPOSE 声明的端口为随机宿主机端口。
- 应用必须监听 `0.0.0.0`，EXPOSE 才有意义。

### VOLUME

```dockerfile
VOLUME /data            # 匿名卷
VOLUME ["/data", "/logs"]
```

- 声明挂载点：容器启动时该路径自动挂一个卷，**该目录的写入不进容器可写层**，容器删除后数据仍在。
- 坑点：
  1. VOLUME 声明**之后**的 Dockerfile 指令对该目录的修改会被丢弃（构建期无法再往卷里写东西）。
  2. 匿名卷不指定名字，容易堆积垃圾卷（`docker volume prune` 清理）。
  3. 应用镜像通常**不建议**在 Dockerfile 里写死 VOLUME，把挂载决策留给运行时（compose `volumes:` / `-v`）更灵活。
- 数据库类镜像（如 mysql 官方镜像）声明 VOLUME 是惯例，因为数据目录天然需要与容器生命周期解耦。

> **本项目实证**：Dockerfile 只有 `EXPOSE 8000`；端口发布与卷挂载全部在 docker-compose.yml 中声明（MySQL 数据卷挂在 db 服务上），符合「镜像声明能力、编排决定策略」的分工。

---

## 九、USER / GROUP：运行身份

```dockerfile
USER <用户名|UID>[:<组名|GID>]
```

- 设置其后所有 RUN / CMD / ENTRYPOINT 的执行身份，并作为容器启动时的默认用户（写入镜像元数据）。
- 对后续指令生效，可多次切换：

```dockerfile
USER root
RUN apt-get update && apt-get install -y git   # 需要 root 的操作
USER app                                        # 切回普通用户
CMD ["uvicorn", "app:app"]                      # 以 app 身份运行
```

- 用户需先存在（基础镜像自带或用 `RUN useradd` 创建；Debian/Ubuntu 用 `useradd`/`groupadd`，Alpine 用 `adduser`/`addgroup`）。
- **生产镜像的最佳实践**：应用以非 root 用户运行。root 运行意味着容器逃逸时直接拿到宿主 root 权限，且应用误操作（删文件、改系统配置）的爆炸半径大得多。
- 拷贝进镜像的文件属主要匹配运行用户，否则运行时读不了：`COPY --chown=app:app ...`。
- `docker run -u 1000:1000 镜像` 可在运行时覆盖。

> 本项目镜像当前未显式 USER（以 root 运行），学习项目可接受；若走生产加固，应在依赖安装后创建 app 用户并 `USER app`。

---

## 十、HEALTHCHECK：健康检查

```dockerfile
HEALTHCHECK [选项] CMD <检查命令>
HEALTHCHECK NONE    # 禁用（覆盖基础镜像继承来的健康检查）
```

选项：

| 选项 | 默认 | 说明 |
|---|---|---|
| `--interval=30s` | 30s | 检查间隔 |
| `--timeout=3s` | 3s | 单次检查超时 |
| `--start-period=0s` | 0s | 启动宽限期（此期间失败不计入次数） |
| `--start-interval=5s` | — | 宽限期内的检查间隔（较新特性） |
| `--retries=3` | 3 | 连续失败几次标记 unhealthy |

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1
```

- 检查命令退出码 0 = healthy，非 0 = unhealthy；`docker ps` 会显示健康状态。
- 命令经 shell 执行，可用 `||`、管道。
- 镜像内没有 curl 时可用应用自身：`CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"`。
- **HEALTHCHECK 影响编排**：compose 中 `depends_on: condition: service_healthy` 依赖它；Swarm 用它决定重启容器。
- 也可以只在 compose 里给服务写 `healthcheck:`，效果等价且不改镜像——**镜像通用时推荐后者**。

---

## 十一、ONBUILD / STOPSIGNAL / SHELL / LABEL / MAINTAINER

### ONBUILD：延迟到子镜像执行的指令

```dockerfile
# base.Dockerfile
FROM python:3.14-slim
WORKDIR /app
ONBUILD COPY requirements.txt ./
ONBUILD RUN pip install -r requirements.txt
```

当别的 Dockerfile `FROM` 这个镜像时，ONBUILD 指令**在子镜像构建的第一个 FROM 之后立即自动执行**。用于「应用骨架镜像」场景。日常很少用；ONBUILD 不能再嵌套 ONBUILD，且会打乱子镜像的层缓存直觉，用之前想清楚。

### STOPSIGNAL：自定义停止信号

```dockerfile
STOPSIGNAL SIGQUIT    # docker stop 时先发 SIGQUIT 而不是 SIGTERM
```

应用只处理特定信号时有用（如 nginx 官方镜像用 SIGQUIT 优雅退出）。

### SHELL：更改 shell 形式的默认解释器

```dockerfile
SHELL ["powershell", "-Command"]    # Windows 容器常用
RUN Get-Process                      # 之后的 RUN/CMD shell 形式都走 powershell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]   # Linux 下让管道中任一命令失败都算失败
```

影响其后所有 shell 形式的 RUN / ENTRYPOINT / CMD。Linux 镜像加 `pipefail` 是下载管道场景的实用技巧。

### LABEL：镜像元数据

```dockerfile
LABEL org.opencontainers.image.title="todo-api" \
      org.opencontainers.image.version="0.1" \
      org.opencontainers.image.source="https://github.com/xxx/yyy"
```

键值对元数据，`docker inspect` 可见。推荐使用 [OCI 标准键名](https://github.com/opencontainers/image-spec/blob/main/annotations.md)。可继承（`docker build --label` 也可在构建时追加）。

### MAINTAINER：已废弃

```dockerfile
MAINTAINER someone@example.com   # 废弃，改用 LABEL org.opencontainers.image.authors=...
```

---

## 十二、多阶段构建（Multi-stage Build）

一个 Dockerfile 里写多个 FROM，**后面的阶段可以只拷贝前面阶段的产物**，最终镜像只含最后一个阶段的内容。

解决的问题：编译工具链（gcc、node_modules 里的 devDependencies、maven）体积巨大，但运行时根本不需要。

### 基本形态

```dockerfile
# ---- 阶段 1：构建（含完整工具链）----
FROM node:22 AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build          # 产出 dist/

# ---- 阶段 2：运行（只有产物 + 运行时）----
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

最终镜像里没有 node、没有源码、没有 devDependencies，可能从 1GB 缩到 50MB。

### 常用技巧

```dockerfile
# 1. 阶段间传依赖声明（缓存友好的多阶段）
FROM python:3.14-slim AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

FROM python:3.14-slim
COPY --from=deps /app/.venv /app/.venv    # 只取虚拟环境
COPY src/ ./src/

# 2. 只构建指定阶段（开发时取调试工具链）
# docker build --target builder -t app:dev .

# 3. 阶段间传递构建信息
FROM builder AS stage1
RUN echo "build-time=$(date -u +%Y%m%d%H%M%S)" > /build-info

# 4. 从外部 Dockerfile 拷贝阶段
COPY --from=./other.Dockerfile:stageName /path /path   # BuildKit 支持
```

### 何时不必多阶段

- 解释型语言 + 纯 wheel 依赖（如本项目 Python + uv 装的全是预编译包），单阶段已足够小。
- 多阶段会增加构建文件复杂度；收益 = 被丢弃阶段的体积，先估算再决定。

> **本项目实证**：单阶段构建，但已用了多阶段的思想片段——`COPY --from=ghcr.m.daocloud.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/` 相当于「从 uv 官方镜像这个阶段拷贝产物」，避免了 pip 安装 uv 或 curl 下载脚本。

---

## 十三、BuildKit 专属特性（RUN --mount、heredoc）

需要文件首行 `# syntax=docker/dockerfile:1` 且使用 BuildKit（Docker 23+ 默认）。旧 docker 引擎需 `DOCKER_BUILDKIT=1`。

### RUN --mount 四种挂载类型

```dockerfile
# 1. cache —— 跨构建持久缓存（最常用）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev
# 缓存存在于构建器本地，不进任何镜像层；可用 id= 区分多个缓存、mode= 控制权限

# 2. secret —— 构建期机密（不落层、不进 history）
RUN --mount=type=secret,id=mytoken \
    curl -H "Authorization: Bearer $(cat /run/secrets/mytoken)" https://api/private
# docker build --secret id=mytoken,src=./token.txt .
# docker build --secret id=mytoken,env=MYTOKEN .   # 从环境变量传

# 3. bind —— 临时挂载上下文/其他阶段的文件（不产生拷贝层）
RUN --mount=type=bind,source=package.json,target=/tmp/pkg.json \
    node -e "console.log(require('/tmp/pkg.json').version)"

# 4. ssh —— 构建期使用宿主的 SSH 转发（拉私有 git 仓库）
RUN --mount=type=ssh git clone git@github.com:org/private-repo.git
# docker build --ssh default .
```

### heredoc（内嵌文件/脚本）

```dockerfile
# 直接写文件内容，不用 COPY 也不用 echo 拼接
COPY <<EOF /etc/motd
Welcome to the container
EOF

RUN <<EOF
apt-get update
apt-get install -y curl
rm -rf /var/lib/apt/lists/*
EOF

# heredoc + shebang 指定解释器
RUN <<EOF python3
import sys
print(sys.version)
EOF
```

### 其他 BuildKit 增强

- `COPY --link`：独立层并行构建，缓存复用更好。
- `COPY --parents`：保留源路径的目录结构。
- `COPY --exclude`：拷贝时排除模式匹配的文件。
- `docker build --check`：静态检查 Dockerfile 常见错误（lint）。
- 构建时可 `--build-context name=path` 传入额外命名上下文，配合 `COPY --from=name`。

> **本项目实证**：`# syntax=docker/dockerfile:1` + `RUN --mount=type=cache,target=/root/.cache/uv`，重复构建时依赖下载走本地缓存，且缓存不增加镜像体积。

---

## 十四、.dockerignore

与 `.gitignore` 语法一致，作用于**构建上下文**：匹配的文件不打包发送给守护进程，也就不能被 COPY/ADD 引用。

```gitignore
# 版本控制与 IDE
.git
.idea
.vscode

# Python 环境与缓存（容器内会重新装）
.venv
__pycache__/
*.pyc

# 敏感配置（规则 1.4：口令文件绝不进镜像）
.env
*_local.py
db_config_local*.py

# 文档与临时产物（不影响运行）
*.md
process/
dump.sql

# Docker 自身
Dockerfile
docker-compose.yml
.dockerignore
```

为什么必须写：

1. **安全**：`.env`、含口令的配置文件、`.git`（含全部历史提交）一旦 COPY 进镜像就随镜像分发泄露。`.gitignore` 管不到构建上下文。
2. **速度/体积**：上下文越小，发送越快；避免 `COPY . .` 把 venv、node_modules、dump 文件带进镜像。
3. **缓存**：无关文件变化不会导致 `COPY . .` 层失效。

⚠️ 注意与 `.gitignore` 的分工：`.gitignore` 决定什么不进 git，`.dockerignore` 决定什么不进构建上下文，两者独立维护、都要覆盖敏感文件。

> **本项目实证**：根目录 `.dockerignore` 排除了 `day15_orm/db_config_local.py` 等含真实口令的配置；容器所需的数据库配置由 docker-compose 以**只读单文件挂载**注入，镜像内零口令。

---

## 十五、层缓存原理与镜像瘦身

### 缓存失效规则

1. 逐层比对：指令文本相同 + 输入相同 → 命中缓存。
2. `COPY`/`ADD` 按**文件内容校验和**判断（不看时间戳），内容没变即命中。
3. `RUN` 只看**命令字符串**是否变化（无法感知命令访问的外部资源变化）。
4. **一旦某层失效，其后所有层连锁失效**——所以指令顺序 = 缓存策略。

### 排序原则：变化频率低的在上

```dockerfile
FROM ...                 # 几乎不变
COPY 依赖声明文件 ./       # 偶尔变（加依赖时）
RUN 安装依赖              # 跟随依赖声明
COPY 源码 ./              # 天天变
CMD [...]                # 元数据，无缓存意义
```

改一行代码 → 只有 COPY 源码层及其后重建，依赖层直接复用。这就是本项目「先 COPY pyproject.toml + uv.lock 装依赖，再 COPY 代码」的全部意义。

### 瘦身手段清单

| 手段 | 效果 |
|---|---|
| 基础镜像选 slim/alpine/distroless | 立竿见影减几十~几百 MB |
| 依赖声明与源码分开 COPY | 不减体积但大幅减**重复构建时间** |
| 同一 RUN 内 `install && rm -rf 缓存目录` | 避免缓存层残留 |
| `--no-install-recommends`（apt） | 不装推荐包 |
| 多阶段构建丢弃编译工具链 | 大项目减 50%+ |
| BuildKit cache mount | 缓存不落层 |
| `.dockerignore` | 防上下文垃圾进镜像 |
| `docker history 镜像` / `docker build --progress=plain` | 排查哪层肥 |
| `docker image prune` / 清理悬空层 | 磁盘回收（不减单镜像体积） |

---

## 十六、最佳实践清单

**可复现**
1. FROM 钉具体版本标签，不用 `latest`。
2. 依赖走锁文件（uv.lock / package-lock.json / requirements.lock.txt）。
3. `# syntax=docker/dockerfile:1` 显式声明解析器版本。

**安全**
4. 应用以非 root USER 运行。
5. 机密不进镜像层：不用 ARG/ENV/COPY 传密钥，用 `--mount=type=secret`；运行时机密用挂载或环境变量注入。
6. `.dockerignore` 覆盖 `.env`、`.git`、本地配置文件。
7. 基础镜像定期重建以获取安全补丁（镜像是不可变的，`docker pull` 不会自动更新已构建的镜像）。

**体积与速度**
8. 最小够用的基础镜像；apt/apk 装完即清缓存。
9. 指令按变化频率排序，最大化缓存命中。
10. 只 COPY 运行必需的文件，不 `COPY . .` 一把梭。

**正确性**
11. CMD 用 exec 形式；需要 shell 展开变量时用 `sh -c "exec ..."`。
12. 网络服务监听 `0.0.0.0`，不监听 127.0.0.1。
13. 日志输出到 stdout/stderr（容器日志模型），不写文件。
14. 一个容器一个进程（主进程）；需要多进程用编排（compose）而不是 supervisor。
15. 设置 `PYTHONUNBUFFERED=1`（Python）之类的输出缓冲开关，否则 `docker logs` 看不到实时日志。
16. 时区/编码：需要时在镜像内配置 `TZ` 环境变量与 locale，别依赖宿主。

**可维护**
17. 每条非显而易见的指令写注释说明「为什么」。
18. Dockerfile 与 compose 分工：镜像定义「应用怎么跑」，compose 定义「环境怎么编排」（端口、卷、网络、依赖顺序）。

---

## 十七、指令速查总表

| 指令 | 作用 | 阶段 | 关键提醒 |
|---|---|---|---|
| `FROM` | 基础镜像 | 构建 | 钉版本；`AS` 命名阶段；可 `--platform` |
| `RUN` | 构建期执行命令 | 构建 | shell/exec 形式；同层清理缓存 |
| `COPY` | 拷贝上下文/其他阶段文件 | 构建 | 默认首选；`--from=` `--chown=` `--link=` |
| `ADD` | 拷贝 + 自动解压 tar + URL | 构建 | 仅在需要自动解压时用 |
| `WORKDIR` | 设置后续指令工作目录 | 构建+运行 | 可多次；相对路径累加 |
| `ENV` | 环境变量 | 构建+运行 | 进镜像元数据，运行时可见可覆盖 |
| `ARG` | 构建参数 | 仅构建 | 不进容器；`docker history` 可见，勿传密钥 |
| `CMD` | 默认启动命令 | 运行 | 被 `docker run 参数` 整体替换；只最后一条生效 |
| `ENTRYPOINT` | 固定入口命令 | 运行 | run 参数追加其后；`--entrypoint` 可覆盖 |
| `EXPOSE` | 端口声明 | 元数据 | 不发布端口；发布靠 `-p`/compose `ports:` |
| `VOLUME` | 声明挂载点 | 运行 | 声明后该目录的镜像层修改失效；慎用 |
| `USER` | 切换执行身份 | 构建+运行 | 生产用非 root；`-u` 可覆盖 |
| `HEALTHCHECK` | 健康检查 | 运行 | compose `service_healthy` 依赖它 |
| `ONBUILD` | 子镜像构建时触发的指令 | 构建 | 少用；不可嵌套 |
| `STOPSIGNAL` | 自定义停止信号 | 运行 | 默认 SIGTERM |
| `SHELL` | 更改默认 shell | 构建 | Windows 容器 / bash pipefail |
| `LABEL` | 键值元数据 | 元数据 | 用 OCI 标准键名 |
| `MAINTAINER` | 维护者 | — | **已废弃**，用 LABEL |

---

## 附录 A：本项目（python_learn）Dockerfile 逐行解读

对照 [../Dockerfile](../Dockerfile)（2026-09-28 容器化方案产物）：

```dockerfile
# syntax=docker/dockerfile:1
```
→ 启用 BuildKit 前端语法（第十三章），支撑后面的 `RUN --mount`。

```dockerfile
FROM python:3.14-slim
```
→ 钉死 Python 版本 + slim 变体（第二章），与项目本地开发版本一致。

```dockerfile
COPY --from=ghcr.m.daocloud.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
```
→ 跨镜像拷贝（第四章）：从 uv 官方镜像直接取二进制，国内走 daocloud 镜像加速。

```dockerfile
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1
```
→ 环境变量（第六章）：预编译字节码提速启动；copy 模式规避跨设备硬链接问题；禁止 uv 自行下载 Python（用镜像自带的）；日志实时输出。

```dockerfile
WORKDIR /app
```
→ 工作目录（第五章），后续 COPY 相对路径的基准。

```dockerfile
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project
```
→ 层缓存核心（第十五章）：先只拷依赖声明，依赖不变则整层复用；cache mount（第十三章）让下载缓存跨构建复用又不落层；`--no-dev` 排除 pyright 等开发工具。

```dockerfile
COPY day15_orm/ ./day15_orm/
COPY day16_crud/ ./day16_crud/
COPY todo_api/ ./todo_api/
COPY alembic.ini ./
COPY day18_alembic/ ./day18_alembic/
```
→ 精确 COPY（第十四章反面教材的规避）：不用 `COPY . .`，只拷跨包依赖链上必需的目录（todo_api → day16_crud → day15_orm），alembic 相关文件为将来容器内迁移预留。

```dockerfile
ENV PATH="/app/.venv/bin:$PATH"
```
→ 把 uv sync 建出的虚拟环境加入 PATH（第六章），CMD 才能直接找到 uvicorn。

```dockerfile
EXPOSE 8000
```
→ 端口声明（第八章）；实际发布在 docker-compose.yml 的 `ports:` 中。

```dockerfile
CMD ["uvicorn", "todo_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
→ exec 形式启动命令（第七章）；绑 0.0.0.0 保证宿主机经端口映射可达；compose 的 `command:` 可覆盖。

**安全设计**：含真实口令的 `day15_orm/db_config_local.py` 由 `.dockerignore` 排除在构建上下文外，容器内的数据库配置由 compose 以只读单文件挂载注入——镜像本身零口令（第十四章第 6 条）。

---

## 附录 B：pipeline-fault-tracker 项目 Dockerfile 逐行解读

> 对照 `E:\python项目\pipeline-fault-tracker`（前后端分离的全栈练习项目），含 backend（Python + uv + SQLite）、frontend（Vue/Vite 构建 → nginx 托管）两个 Dockerfile 与一份 docker-compose.yml 编排。与附录 A 的单体镜像相比，本章重点展示**多阶段构建**（第十二章）与**compose 编排 + healthcheck + depends_on 就绪依赖**（第八、十章）的完整落地。

### B.1 backend/Dockerfile（Python + uv，单阶段）

```dockerfile
FROM python:3.14-slim
WORKDIR /app
```
→ 基础镜像 + 工作目录（第二、五章），与附录 A 同款 slim 变体。

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
```
→ 跨镜像拷贝（第四章）：从 uv 官方镜像取单个二进制。注意与附录 A 的差异——A 取了 `/uv /uvx` 两个二进制且走 daocloud 镜像加速，这里只取 `/uv`（backend 不需要 uvx），走 ghcr.io 原始地址。

```dockerfile
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
```
→ 层缓存核心（第十五章）：先拷依赖声明再装。三个 uv 参数各有含义：
> - `--frozen`：严格按 uv.lock 安装，**不允许**因 pyproject.toml 与 lock 不一致而重新解析——保证构建可复现（对比附录 A 用的 `--no-install-project`，此处未加，因为 backend 是可安装包，需要把项目自身也装进去）。
> - `--no-dev`：开发依赖不进运行镜像。
> - `--no-cache`：不写 uv 缓存目录，对应 pip 路线的 `--no-cache-dir` 瘦身。**注意这里没用 BuildKit cache mount**（第十三章），而是彻底不落缓存——与附录 A 的 `--mount=type=cache` 是两种取舍：A 追求重复构建快，B 追求镜像构建简单、无 BuildKit 依赖。

```dockerfile
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
```
→ 精确 COPY（第十四章）：业务代码 + Alembic 迁移目录 + 配置。与附录 A 同理，不用 `COPY . .` 一把梭。

```dockerfile
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```
→ exec 形式启动（第七章）+ 绑 0.0.0.0。与附录 A 的关键差异：这里用 `uv run --no-sync` 启动，而非把 venv 加进 PATH 直接调 uvicorn。`--no-sync` 表示启动时不再检查/同步依赖（依赖已在构建期 `uv sync` 装好），避免每次启动的额外开销。

### B.2 frontend/Dockerfile（Node 构建 → nginx，两阶段）

这是文档第十二章「多阶段构建」的完整实证：构建工具链（node、node_modules）在终镜像里被完全丢弃。

**阶段 1：build（含完整 Node 工具链）**

```dockerfile
FROM node:16.20.2-alpine AS build
WORKDIR /app
```
→ 钉死 Node 版本（第二章最佳实践）+ alpine 最小基础镜像；`AS build` 命名阶段供后续 `--from=build` 引用。版本注释点明 lockfileVersion 2 与 npm 8 的兼容约束。

```dockerfile
COPY package.json package-lock.json .npmrc ./
RUN npm ci
```
→ 层缓存（第十五章）：先拷声明文件再 `npm ci`（按 lock 精确安装，对应 Python 的 `uv sync --frozen`）。`.npmrc` **必须在 npm ci 之前**进镜像：lock 的 resolved 字段写死了旧的 npmmirror 源（已不可达），靠 `.npmrc` 的 `replace-registry-host=always` 强制回官方源——这是「配置文件参与构建、且顺序敏感」的典型例子。

```dockerfile
COPY . .
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build
```
→ 拷全部源码后构建。这里集中体现了两个易错点：
> - **ARG → ENV 的接力**（第六章）：`ARG VITE_API_BASE_URL=` 声明一个**默认空串**的构建参数，再用 `ENV` 固化，供 `npm run build` 读取。默认空串是刻意的：同源部署时前端应请求相对路径 `/api/...`（由 nginx 代理），若 ARG 不传且默认值不是空串，Vite 会把变量拼成字符串 `"undefined"` 进请求路径。
> - **VITE_ 前缀是构建期替换**：Vite 的 `import.meta.env.VITE_*` 在 `npm run build` 时被静态内联进产物，**不是运行时**读取。所以这个值必须在构建阶段就确定——这也是它不能像后端配置那样留到 compose 的 `environment:` 注入的原因。

**阶段 2：nginx（仅静态产物 + Web 服务器）**

```dockerfile
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```
→ 多阶段的收尾：从 build 阶段只拷 `dist/` 构建产物（第四章 `COPY --from=`），终镜像不含 node、源码、node_modules，体积从数百 MB 缩到 nginx:alpine 的量级。`nginx.conf` 覆盖默认站点配置（承担 `/api` 反向代理到 backend 的职责）。**注意本阶段没有 CMD/ENTRYPOINT**——直接继承 nginx 官方镜像自带的启动命令（第七章：基础镜像的 ENTRYPOINT/CMD 会被继承）。

### B.3 docker-compose.yml（编排 + healthcheck + 就绪依赖）

把前两个镜像组装成一条命令可起的全栈环境，集中体现了第八、十、十六章的编排分工。

```yaml
services:
  backend:
    build: ./backend
    environment:
      DATABASE_URL: sqlite:///./data/fault_tracker.db
    volumes:
      - ~/pft-bind:/app/data
```
→ 运行期配置全部下沉到 compose（第十六章「镜像定义怎么跑、compose 定义怎么编排」）：数据库路径用**环境变量**注入而非写进镜像（第十二章 ARG 不传密钥的反面印证——这里是配置不是密钥，但同理走运行时注入）；`~/pft-bind:/app/data` 是 **bind mount**（第八章 VOLUME 的运行时对应），SQLite 数据文件直接落宿主机目录，`down`/`down -v` 都不会删（down -v 只删 named volume），便于 ls/备份。

```yaml
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 5
```
→ 健康检查（第十章）：因为 slim 镜像内没有 curl，改用系统 python 的 urllib 探活 `/api/health`。这里 healthcheck 写在 **compose 而非 Dockerfile**——正是第十章「镜像通用时推荐把健康检查留给编排层」的实践。

```yaml
  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
```
→ 端口发布（第八章：镜像里 `EXPOSE 80` 只是声明，真正的 `8080:80` 发布在这）。`depends_on` + `condition: service_healthy` 是关键：单靠 `depends_on` 只保证**启动顺序**、不保证 backend **就绪**；加上 healthcheck 条件后，frontend 会等到 backend 健康检查通过才启动，避免前端起来时后端还没监听端口。

### B.4 附录 A vs 附录 B 对照

| 维度 | python_learn（附录 A） | pipeline-fault-tracker（附录 B） |
|---|---|---|
| 形态 | 单体镜像 | 前后端双镜像 + compose 编排 |
| 构建阶段 | 单阶段 | frontend 两阶段（build → nginx） |
| 依赖锁 | `uv sync --no-install-project` | backend `uv sync --frozen`；frontend `npm ci` |
| uv 缓存 | BuildKit cache mount（不落层） | `--no-cache`（彻底不写缓存） |
| 启动方式 | venv 加 PATH 后直接 `uvicorn` | `uv run --no-sync uvicorn` |
| 数据持久化 | MySQL 独立容器 + dump 导入 | SQLite + bind mount 到宿主机 |
| 健康检查 | 无 | compose healthcheck + depends_on 就绪依赖 |
| 构建期变量 | 无 | frontend `ARG→ENV VITE_API_BASE_URL`（构建期内联） |

---

*文档整理日期：2026-09-29，基于 docker/dockerfile:1 语法与 BuildKit 特性；随 Docker 版本演进请以官方文档为准：https://docs.docker.com/reference/dockerfile/*

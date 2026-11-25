# Docker Compose 完整指令文档（通用手册 + 项目示例点缀）

> 适用版本：以 **Compose V2**（`docker compose` 子命令，Compose Specification 规范）为基准整理（2026-09），本机 WSL 内 Compose **v5.5.1** 已装好（2026-09-22 实测，安装步骤见 [docker.md](docker.md) 2.2 节）；涉及已废弃的 V1（`docker-compose` 连字符命令）差异处单独标注。
> 定位：**通用 Compose 指令与配置手册，不限于本项目**——第一~八节为不绑定项目的概念、YAML 字段与 CLI 命令大全；第九节把两个真实项目的 `docker-compose.yml` 逐字段解读为对照示例（案例一 = 本项目 pipeline-fault-tracker，案例二 = 同机另一仓库 python_learn 的 todo_api + MySQL）；Docker 基础概念（镜像/容器/卷/网络）不在本文重复，见 [docker.md](docker.md)。
> 可信度标注：「实测」= 本机执行验证过（第九节案例一的本项目 compose 已随 D4/D5 演练实测；案例二 python_learn 据其文件头注释与 [docker.md](docker.md) 记载为 2026-09-28 数据库容器化改造实测，本次会话未重跑，解读基于对 compose 文件的逐行核实）；其余命令与字段为 **Compose 官方文档/规范行为，未逐一实测**，以 `docker compose <命令> --help` 自查为准。
> 执行位置约定：本机 Docker 引擎装在 WSL 内，**bash** = WSL / Linux 内直接执行；**PowerShell** = Windows 终端，需经 `wsl -e bash -c "..."` 包装进入（见 [docker.md](docker.md) 12.3）。命令示例统一不含中文路径。

---

## 目录

1. [Compose 概览与核心概念](#一compose-概览与核心概念)
2. [compose.yaml 文件结构与顶层字段](#二composeyaml-文件结构与顶层字段)
3. [services 服务字段大全](#三services-服务字段大全)
4. [变量插值与 .env 文件](#四变量插值与-env-文件)
5. [CLI 命令全集](#五cli-命令全集)
6. [网络](#六网络)
7. [数据持久化](#七数据持久化)
8. [编排模式与进阶](#八编排模式与进阶)
9. [项目 docker-compose.yml 对照解读（两个真实案例）](#九项目-docker-composeyml-对照解读两个真实案例)
10. [常见坑点与排障](#十常见坑点与排障)
11. [命令速查表](#十一命令速查表)

---

## 一、Compose 概览与核心概念

### 1.1 Compose 是什么

Compose 是 Docker 的**多容器编排工具**：用一个 YAML 文件（`compose.yaml`）声明式描述多个服务（容器）的镜像/构建方式、网络、卷、环境变量、启动依赖，然后用一条命令（`docker compose up`）把整套系统拉起来。

解决的痛点：没有 Compose 时，启动一套「前端 + 后端 + 数据库」需要手敲多条 `docker run`，参数（网络、挂载、环境变量、启动顺序）全靠人脑记忆和 shell 脚本维护；Compose 把这些固化进一个可入库、可 diff、可复用的文件。

### 1.2 V1 与 V2 的差异

| 维度 | V1（已废弃） | V2（现行，本文基准） |
|---|---|---|
| 命令形态 | 独立二进制 `docker-compose`（连字符） | Docker CLI 插件 `docker compose`（空格） |
| 实现语言 | Python | Go（与 Docker CLI 一体发布） |
| 规范依据 | compose-file v2/v3 版本化格式 | **Compose Specification**（统一规范，不再分 v2/v3 文件版本） |
| 顶层 `version:` 字段 | 必填，决定语法 | **已废弃**：忽略并告警（`attribute version is obsolete`） |
| 默认容器命名 | `项目_服务_1`（下划线） | `项目-服务-1`（连字符） |
| 孤儿容器 | `up` 默认不处理，需手动加 `--remove-orphans` | `up` / `down` 默认自动清理孤儿容器 |

迁移要点：把脚本里的 `docker-compose` 全部替换为 `docker compose` 即可，绝大多数 YAML 字段兼容；V2 还支持 `include`、`watch`、`depends_on` 长语法等 V1 没有的能力（见第八节）。

### 1.3 五个核心对象：项目 / 服务 / 容器 / 网络 / 卷

| 对象 | 是什么 | 类比 |
|---|---|---|
| **项目（Project）** | 一份 compose 文件定义的整体，所有资源以项目名为前缀隔离 | 命名空间 / 数据库 schema |
| **服务（Service）** | compose 文件里 `services:` 下的一个条目，是**容器的模板** | 类（Class） |
| **容器（Container）** | 服务的运行实例，一个服务默认起 1 个容器（可 scale 多个） | 实例（Object） |
| **网络（Network）** | 项目默认自建一个 bridge 网络，所有服务加入后可用**服务名互访** | 同一局域网 |
| **卷（Volume）** | 独立于容器生命周期的持久化存储，`down` 默认不删 | 外接硬盘 |

### 1.4 项目名（Project Name）

项目名决定所有资源的命名前缀，取值优先级从高到低：

1. 全局参数 `-p / --project-name`；
2. 顶层 `name:` 字段（见 2.2）；
3. 环境变量 `COMPOSE_PROJECT_NAME`；
4. **compose 文件所在目录名**（默认，最常用）。

推论：
- 在不同目录执行同名 compose 文件 = 两个互不干扰的项目；
- 同一目录重复 `up` = 更新同一个项目（不会另起一套）；
- 资源实际命名形如：容器 `myapp-backend-1`、网络 `myapp_default`、卷 `myapp_data`。

### 1.5 文件查找规则

在项目目录执行 `docker compose up` 时，CLI 按以下顺序查找 compose 文件：

1. `-f` 显式指定的文件（可多次 `-f` 叠加，见 8.4）；
2. 当前目录下的 `compose.yaml` → `compose.yml` → `docker-compose.yaml` → `docker-compose.yml`（按此优先序取第一个命中的）。

官方推荐文件名是 **`compose.yaml`**；本项目沿用早期惯例 `docker-compose.yml`，两者等效。

---

## 二、compose.yaml 文件结构与顶层字段

### 2.1 最小示例

```yaml
services:
  web:
    image: nginx:alpine
    ports:
      - "8080:80"
```

```bash
docker compose up -d      # 拉起
docker compose down       # 停止并清理
```

### 2.2 顶层字段一览

| 字段 | 作用 | 备注 |
|---|---|---|
| `services` | **必填**，服务定义集合 | 核心，见第三节 |
| `networks` | 自定义网络声明 | 不写则自动创建 `<项目名>_default`，见第六节 |
| `volumes` | 命名卷声明 | 服务里引用前必须在此声明，见第七节 |
| `configs` | 配置文件对象（内容或外部文件） |  swarm 场景更常用，单机可用 `content` 内联 |
| `secrets` | 敏感信息对象，以文件形式挂进 `/run/secrets/` | 比明文 environment 更安全 |
| `include` | 引入其他 compose 文件（各自独立解析后合并） | V2 专属，见 8.4 |
| `name` | 显式指定项目名 | 优先级低于 `-p`，高于目录名 |
| `x-*` | 扩展字段（YAML 锚点复用的落点） | Compose 忽略，仅供 YAML 自身引用，见 8.6 |
| ~~`version`~~ | ~~文件语法版本~~ | **已废弃**：写了会被忽略并告警，新文件不要写 |
| ~~`depends_on`（顶层）~~ | — | 不存在顶层 depends_on，它只能写在服务内 |

### 2.3 secrets 与 configs 示例

```yaml
services:
  backend:
    image: myapp:1.0
    secrets:
      - db_password          # 挂载为 /run/secrets/db_password 文件
    configs:
      - source: app_settings
        target: /etc/myapp/settings.json

secrets:
  db_password:
    file: ./secrets/db_password.txt   # 或 external: true 引用已存在对象

configs:
  app_settings:
    content: |
      { "debug": false, "workers": 4 }
```

要点：secret 以**文件**形式进容器（应用需支持从文件读密码，如 `*_FILE` 约定），避免密码出现在 `docker inspect` 的环境变量里。

---

## 三、services 服务字段大全

按用途分组列出常用字段；完整清单以 [Compose Specification](https://github.com/compose-spec/compose-spec/blob/master/spec.md) 为准。

### 3.1 镜像与构建：image / build / pull_policy

```yaml
services:
  # 形态 A：直接用现成镜像
  db:
    image: postgres:16-alpine

  # 形态 B：从 Dockerfile 构建（短语法）
  backend:
    build: ./backend            # 指向 Dockerfile 所在目录（= build context）

  # 形态 C：构建长语法
  frontend:
    build:
      context: ./frontend       # 构建上下文
      dockerfile: Dockerfile    # 相对 context 的 Dockerfile 路径
      args:                     # 构建期变量（对应 Dockerfile 的 ARG）
        VITE_API_BASE_URL: ""
      target: builder           # 多阶段构建只构建到某 stage
      cache_from:
        - type=registry,ref=myapp/frontend:buildcache
    image: myapp/frontend:0.1   # build + image 同写 = 构建产物打上该标签
    pull_policy: build          # up 时总是重新构建（另可选 always / never / missing / if_not_present）
```

- `image` 与 `build` 可**同时写**：构建后按 `image` 命名，方便推送；
- `args` 只在构建期生效，运行期不可见（区别于 `environment`）；
- `pull_policy: always` 适合标签会漂移的场景（如 `latest`），保证每次 up 都拉新。

### 3.2 容器命名与启动命令：container_name / command / entrypoint / working_dir / user / init

```yaml
services:
  worker:
    image: myapp:1.0
    container_name: myapp-worker   # 固定容器名（默认是 项目-服务-序号）
    entrypoint: ["/bin/sh", "-c"]  # 覆盖镜像的 ENTRYPOINT
    command: ["python worker.py"]  # 覆盖镜像的 CMD
    working_dir: /srv              # 覆盖工作目录
    user: "1000:1000"              # 覆盖运行用户
    init: true                     # 注入 tini 作为 PID 1，回收僵尸进程、转发信号
    tty: true                      # 分配伪终端
    stdin_open: true               # 保持 stdin 打开（docker run -i）
```

注意：`container_name` 写死后该服务**无法 scale 多副本**（名字冲突），一般不建议写。

### 3.3 端口映射：ports / expose

```yaml
services:
  frontend:
    ports:
      - "8080:80"                       # 宿主机:容器（短语法，务必带引号）
      - "127.0.0.1:9000:9000"           # 只绑本机回环，不对外网暴露
      - "3000-3005"                     # 只暴露容器端口，宿主机端口随机
      - target: 80                      # 长语法
        published: 8080
        protocol: tcp
        mode: host                      # host=直接绑宿主机；ingress=swarm 负载均衡
    expose:
      - "8000"    # 仅对项目内其他容器可见（其实同网络默认可达，此字段多为文档性声明）
```

- **端口映射不是必须的**：同一项目网络内容器互访走服务名+容器端口（如 `backend:8000`），只有需要从宿主机/外部访问的端口才要 `ports`；
- 短语法端口**必须加引号**：YAML 会把 `80:80` 之类含冒号的裸值解析出问题，且 `60:80` 这种会被当成六十进制数字（经典坑）。

### 3.4 挂载：volumes（服务级）

```yaml
services:
  backend:
    volumes:
      - ./app:/srv/app                    # bind mount：宿主机路径:容器路径
      - ~/pft-bind:/app/data              # bind mount，宿主机家目录
      - db-data:/var/lib/postgresql/data  # 命名卷：卷名:容器路径（卷须在顶层 volumes 声明）
      - ./conf:/etc/app:ro                # 追加 :ro 只读挂载
      - cache:/tmp/cache                  # 命名卷
      - type: bind                        # 长语法
        source: ./scripts
        target: /scripts
        read_only: true
      - type: tmpfs                       # 内存盘，容器停即失
        target: /scratch
        tmpfs:
          size: 104857600
```

bind mount 与命名卷的选择、生命周期差异见第七节。

### 3.5 环境变量：environment / env_file

```yaml
services:
  backend:
    environment:                    # 形态 A：字典
      DATABASE_URL: sqlite:///./data/app.db
      DEBUG: "true"                 # 布尔/数字要加引号，否则类型不是字符串
    env_file:                       # 形态 B：从文件批量注入
      - .env.local                  # 相对 compose 文件所在目录
      - path: .env.secret           # 长语法（可标 required: false 允许文件缺失）
        required: false
```

优先级：`environment` > `env_file` > 镜像内 `ENV`。变量插值（`${VAR}` 语法）见第四节。

### 3.6 健康检查：healthcheck

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s       # 探测间隔
      timeout: 3s        # 单次探测超时
      retries: 5         # 连续失败几次判 unhealthy
      start_period: 10s  # 启动宽限期：期间的失败不计入 retries
```

`test` 两种形态：
- `["CMD", 可执行文件, 参数...]`：直接 exec，不经 shell；
- `["CMD-SHELL", "curl -f http://localhost/ || exit 1"]`：经 `/bin/sh -c`，可用管道等 shell 语法。

退出码 0 = 健康。镜像也可以自带 `HEALTHCHECK` 指令，服务级 `healthcheck` 会覆盖它；`healthcheck: { disable: true }` 可禁用。健康状态是 `depends_on: condition: service_healthy` 的基础（见 8.1）。

### 3.7 重启策略与资源：restart / deploy / mem_limit / cpus

```yaml
services:
  app:
    restart: unless-stopped   # no（默认）/ always / on-failure[:次数] / unless-stopped
    mem_limit: 512m           # 非 swarm 下的内存上限（compose-spec 兼容字段）
    cpus: 1.0                 # 非 swarm 下的 CPU 上限
    deploy:                   # 长语法（V2 在本地 compose 下也识别部分键）
      replicas: 2             # 副本数（等效 docker compose up --scale 服务=2）
      resources:
        limits:
          cpus: "1.0"
          memory: 512M
        reservations:
          memory: 128M
      restart_policy:
        condition: on-failure
        max_attempts: 3
```

单机 Compose 场景优先用服务级 `restart` / `mem_limit` / `cpus` / `deploy.replicas`，其余 `deploy.*` 子键（如滚动更新）主要面向 swarm。

### 3.8 网络与依赖：networks / depends_on / links

```yaml
services:
  frontend:
    networks: [frontend-net]        # 指定加入哪些自定义网络（不写则加入 default）
    depends_on:
      backend:
        condition: service_healthy  # 长语法，见 8.1
  backend:
    networks: [frontend-net, db-net]
```

`links` 已废弃（服务名互访由网络天然提供），不要用。

### 3.9 日志与运行细节：logging / extra_hosts / devices / cap_add / security_opt / stop_* / labels / profiles / annotations

```yaml
services:
  app:
    logging:
      driver: json-file
      options:
        max-size: "10m"       # 单文件上限，防日志撑爆磁盘
        max-file: "3"
    extra_hosts:
      - "host.docker.internal:host-gateway"   # 容器内访问宿主机的标准写法（Linux 需要显式加）
    devices:
      - "/dev/ttyUSB0:/dev/ttyUSB0"           # 透传宿主机设备
    cap_add:
      - NET_ADMIN                             # 追加 Linux capability
    security_opt:
      - no-new-privileges:true
    stop_signal: SIGTERM        # docker compose stop 发的信号
    stop_grace_period: 30s      # 发信号后等多久强杀
    labels:
      com.example.owner: "team-a"
    profiles: ["debug"]         # 默认不启动，--profile debug 才拉起（见 8.2）
    annotations:
      com.example.notes: "nightly build"
```

### 3.10 其他常用字段速览

| 字段 | 一句话 |
|---|---|
| `hostname` / `domainname` | 容器主机名 |
| `dns` / `dns_search` | 自定义 DNS |
| `tmpfs` | 内存文件系统挂载点（简写形态） |
| `ulimits` | 覆盖进程资源限制（如 `nofile`） |
| `sysctls` | 内核参数 |
| `shm_size` | `/dev/shm` 大小（跑浏览器/数据库常调大） |
| `read_only` | 根文件系统只读（配合 tmpfs 写临时文件） |
| `platform` | 指定镜像架构（如 `linux/amd64`，ARM 机器跑 x86 镜像） |
| `privileged` | 特权模式（尽量别用） |
| `network_mode` | `bridge` / `host` / `none` / `service:其他服务`（共享网络栈） |
| `pid` | `host`（共享宿主机 PID 命名空间） |
| `scale` | 已废弃，改用 `deploy.replicas` 或 `--scale` |
| `extends` | 继承同文件/其他文件的服务定义（见 8.5） |
| `develop.watch` | 文件变更自动重建/同步（见 8.8） |
| `secrets` / `configs` | 见 2.3 |
| `credential_spec` | Windows 容器专用 |

---

## 四、变量插值与 .env 文件

### 4.1 插值语法

compose 文件里的 `${VAR}` 会在解析时替换为变量值：

```yaml
services:
  db:
    image: postgres:${PG_VERSION:-16-alpine}   # 未设置时用默认值
    environment:
      POSTGRES_PASSWORD: ${PG_PASSWORD:?必须设置 PG_PASSWORD}  # 未设置直接报错终止
      POSTGRES_USER: ${PG_USER-postgres}       # 仅「未定义」时用默认（定义了但为空则取空串）
      LITERAL: $$HOME                           # $$ 转义：原样输出 $HOME，不插值
```

| 语法 | 含义 |
|---|---|
| `${VAR}` | 取值；未设置为空串（会有告警） |
| `${VAR:-default}` | 未设置**或为空**时用 default |
| `${VAR-default}` | 仅未设置时用 default |
| `${VAR:?err}` | 未设置或为空时报错退出 |
| `${VAR?err}` | 仅未设置时报错退出 |
| `$$` | 转义为字面量 `$` |

### 4.2 插值变量的来源与 .env 文件

插值取值来源，优先级从高到低：

1. **当前 shell 的环境变量**；
2. **项目 `.env` 文件**（默认与 compose 文件同目录，可用全局 `--env-file` 换）。

`.env` 文件是 `KEY=VALUE` 纯文本（不是 shell 脚本，别写 `export`）：

```dotenv
# .env
PG_VERSION=16-alpine
PG_PASSWORD=secret
COMPOSE_PROFILES=debug
```

**两个易混点**：
- `.env` 文件里的变量**不会自动注入容器**——它只服务于 compose 文件里的 `${VAR}` 插值；要进容器还得在 `environment` 或 `env_file` 里显式引用；
- `.env` 文件常含密码，**应加入 `.gitignore`**，入库的是 `.env.example` 模板（本项目前后端均为此模式）。

### 4.3 environment 的插值与透传

```yaml
services:
  app:
    environment:
      DATABASE_URL: ${DATABASE_URL}   # 插值后注入
      PATH_VAR:                       # 只写名不写值 = 透传宿主机同名变量
```

---

## 五、CLI 命令全集

### 5.1 全局参数

全局参数写在 `compose` 与子命令之间：

```bash
docker compose [全局参数] <子命令> [子命令参数] [服务...]
```

| 全局参数 | 作用 |
|---|---|
| `-f, --file` | 指定 compose 文件，可多次（叠加合并，见 8.4） |
| `-p, --project-name` | 指定项目名（见 1.4） |
| `--env-file` | 指定插值用 .env 文件（默认 compose 同目录 `.env`） |
| `--profile` | 激活指定 profile 的服务（可多次，见 8.2） |
| `--project-directory` | 指定项目目录（影响相对路径解析与默认 .env 位置） |
| `--progress` | 输出形态：`auto` / `plain` / `tty` / `json` |
| `--no-ansi` | 关闭彩色输出（脚本采集日志时用） |
| `--dry-run` | 只打印将执行的动作，不真执行 |
| `--verbose` | 输出调试级日志 |
| `--compatibility` | 把 deploy.* 键翻译为 V1 兼容字段 |

### 5.2 生命周期命令

| 命令 | 作用 | 常用参数 |
|---|---|---|
| `up` | 创建并启动服务（不存在则建网络/卷，代码变了自动重建） | `-d` 后台；`--build` 强制先构建；`--force-recreate` 强制重建容器；`--no-deps` 不连带依赖服务；`--scale 服务=N`；`--wait` 阻塞到全部 healthy；`--abort-on-container-failure` 任一容器退出即停全部；`--remove-orphans`（V2 已默认）；`--no-start` 只建不启；`服务...` 只操作指定服务 |
| `down` | 停止并删除容器、默认网络 | `-v / --volumes` 连**命名卷**一起删（数据丢失风险！）；`--rmi all\|local` 连镜像一起删；`--remove-orphans`；`-t 秒` 停止宽限 |
| `start` / `stop` | 启动 / 停止**已存在**的容器（不创建不删除） | `-t 秒`（stop 的宽限期）；服务名可选 |
| `restart` | 重启 | 服务名可选 |
| `pause` / `unpause` | 冻结 / 恢复进程（容器不重启） | |
| `kill` | 发信号强杀 | `-s SIGNAL` |
| `rm` | 删除**已停止**的容器 | `-f` 强制（先 kill）；`-s` 连卷 |
| `create` | 只创建容器不启动（up --no-start 的等价物） | |

`up` 与 `start/stop` 的本质区别：`up` 是**声明式对账**（比对期望状态与实际状态，缺什么补什么、变什么重建什么），`start/stop` 只操作既有容器的运行状态。日常一律用 `up -d` / `down`。

### 5.3 查看与排障命令

| 命令 | 作用 | 常用参数 |
|---|---|---|
| `ps` | 列出项目容器及状态 | `-a` 含已停止；`--format json`；`--services` 只列服务名；`--status running` 过滤 |
| `logs` | 看服务日志 | `-f` 跟随；`--tail N` 末尾 N 行；`--since 10m`；`-t` 带时间戳；`--no-color`；服务名可选 |
| `exec` | 在**运行中**容器内执行命令 | `-it` 交互终端；`-u 用户`；`-w 目录`；`-e K=V` 注入变量；`-T` 禁用 tty（脚本用） |
| `top` | 看各容器内进程 | |
| `port` | 查询容器端口映射到的宿主机端口 | `docker compose port 服务 容器端口` |
| `images` | 列出项目使用的镜像 | |
| `events` | 实时打印容器事件流 | |
| `stats` | 实时资源占用（CPU/内存/IO） | `--no-stream` 单次快照 |
| `config` | **渲染最终合并配置**（插值完成、多文件合并后），排「YAML 到底被解析成什么」的第一工具 | `-q` 只校验不输出；`--images` 列出涉及镜像；`--services`；`--hash` 各服务配置哈希 |
| `ls` | 列出本机所有 compose 项目 | `-a` 含已停止 |

### 5.4 构建与镜像命令

| 命令 | 作用 | 常用参数 |
|---|---|---|
| `build` | 构建带 `build:` 的服务镜像 | `--no-cache` 不用缓存；`--pull` 先拉新基础镜像；`--build-arg K=V`；`--parallel` 并行构建（默认）；`--progress plain` 看完整输出（含 CACHED 标记）；服务名可选 |
| `pull` | 拉取服务的镜像 | `--ignore-buildable` 跳过可构建的；`--include-deps` 连带依赖 |
| `push` | 推送镜像（需配 `image:` 名） | `--include-deps` |

### 5.5 运行与扩缩命令

| 命令 | 作用 | 常用参数 |
|---|---|---|
| `run` | 起一个**一次性**容器执行命令（调试/迁移脚本利器） | `--rm` 用完即删；`--no-deps` 不连带依赖；`-e K=V`；`-w 目录`；`--service-ports` 启用端口映射；`-T` 禁用 tty |
| `scale` | 调整副本数（等效 `up --scale`） | `scale 服务=N` |
| `cp` | 容器与宿主机间拷文件 | `cp 服务:容器路径 宿主路径` |
| `wait` | 阻塞等待容器退出/健康 | `--status healthy` |

`run` 与 `exec` 的区别：`run` **新起**一个容器（可带不同 command），`exec` 进入**已在运行**的容器。

### 5.6 项目管理命令

| 命令 | 作用 |
|---|---|
| `down` / `up` / `ps` / `ls` | 见上 |
| `watch` | 监视文件变更自动 rebuild/sync（见 8.8） |
| `viz` | 输出服务依赖关系的 DOT 图（较新版本） |
| `init` | 交互式生成 compose 文件骨架（较新版本） |
| `alpha *` | 实验性命令（如 `alpha prompt`、`alpha viz` 早期形态），版本间变动大 |

### 5.7 典型工作流示例

```bash
# 日常起停
docker compose up -d --build          # 构建并后台拉起全部服务
docker compose ps                     # 确认状态
docker compose logs -f backend        # 跟踪某服务日志
docker compose down                   # 停止并清理（保留卷）

# 调试
docker compose config -q              # 先校验 YAML 与插值
docker compose run --rm backend alembic upgrade head   # 一次性跑迁移
docker compose exec backend sh        # 进入运行中容器
docker compose up -d --scale worker=3 # worker 扩到 3 副本

# 彻底清理（危险操作，确认数据不需要了再执行）
docker compose down -v --rmi local    # 连命名卷和本地构建镜像一起删
```

---

## 六、网络

### 6.1 默认网络

不写 `networks:` 时，Compose 自动创建一个 `<项目名>_default` 的 bridge 网络，所有服务加入：

- 服务间用**服务名作为主机名**互访（DNS 由 Docker 内置提供），如 `http://backend:8000`；
- 容器重启 IP 会变，**永远用服务名不要用 IP**；
- 服务名同时注册网络别名，`container_name` 不影响服务名解析。

### 6.2 自定义网络

```yaml
services:
  frontend:
    networks: [web-net]              # 只进 web-net
  backend:
    networks: [web-net, db-net]      # 两边都进（应用层是唯一桥梁）
  db:
    networks: [db-net]               # 只进 db-net，frontend 无法直连 db

networks:
  web-net:                           # 空配置 = 默认 bridge 驱动
  db-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

自定义网络的意义：**网络分段隔离**——上例中 frontend 与 db 不同网，即使 db 有漏洞也无法从前端容器直达。

### 6.3 外部网络与既有容器互通

```yaml
networks:
  shared:
    external: true      # 引用已存在的网络（docker network create shared 先建好）
    name: shared        # 实际网络名与声明名不同时用 name 指定
```

典型场景：多个 compose 项目需要互访时，共同加入一个外部网络。

---

## 七、数据持久化

### 7.1 两种挂载形态对比

| 维度 | 命名卷（named volume） | bind mount |
|---|---|---|
| 写法 | `- 卷名:/容器路径` + 顶层 `volumes:` 声明 | `- 宿主路径:/容器路径` |
| 实际位置 | Docker 管理区（`/var/lib/docker/volumes/<项目>_<卷名>/_data`） | 宿主机任意指定路径 |
| 创建 | 不存在自动创建 | 宿主机路径不存在时 Linux 下自动建空目录（易掩盖路径写错） |
| 首次挂载 | 卷为空时把镜像内该路径的**既有内容拷入卷** | 宿主机目录内容**直接覆盖**容器内路径（镜像内原内容被遮住） |
| 权限 | Docker 处理，较少踩权限坑 | 受宿主机 uid/gid 影响，常见 permission denied |
| `down -v` | **会被删除** | 不受影响（数据在宿主机） |
| 适用 | 数据库数据等「交给 Docker 管」的持久化 | 开发期代码热挂载、需要直接 ls/备份的数据 |

### 7.2 命名卷声明与生命周期

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:                 # 实际卷名 = <项目名>_db-data
    # driver: local
    # driver_opts: { type: none, device: /opt/data, o: bind }   # 给命名卷绑定固定宿主路径
    # external: true       # 引用 docker volume create 已建好的卷
    # name: my-shared-db   # 显式指定实际卷名（脱离项目前缀）
```

- `docker compose down`：卷**保留**；
- `docker compose down -v`：删除本项目命名卷（**数据不可逆丢失**，执行前想清楚）；
- bind mount 任何 down 都不碰（本项目即因此从命名卷切到 bind mount，见 9.2）。

### 7.3 卷操作命令（非 compose 专属）

```bash
docker volume ls                       # 列出全部卷
docker volume inspect 项目名_卷名      # 看挂载点等详情
docker volume rm 项目名_卷名           # 手动删卷
docker volume prune                    # 清理无容器引用的卷（危险，逐一确认）
```

---

## 八、编排模式与进阶

### 8.1 启动顺序与就绪：depends_on

```yaml
services:
  frontend:
    depends_on:
      backend:
        condition: service_healthy       # 等 backend 健康检查通过才启动
      migrate:
        condition: service_completed_successfully   # 等一次性任务成功退出
  backend:
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"]
      interval: 5s
      timeout: 3s
      retries: 5
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      retries: 10
  migrate:
    image: myapp:1.0
    command: ["alembic", "upgrade", "head"]
    restart: "no"                        # 一次性任务不要自动重启
```

三种 condition：
- `service_started`：容器启动即算（**短语法 `- backend` 等价于这个**，只保证顺序不保证就绪）；
- `service_healthy`：依赖方 healthcheck 通过；
- `service_completed_successfully`：依赖方以退出码 0 结束（适合 init/migration 任务）。

核心认知：**depends_on 只解决启动时序，不解决业务就绪**；要「就绪」必须给被依赖方配 healthcheck。`up --wait` 则让 CLI 阻塞到所有服务 healthy/completed。

### 8.2 profiles：按需启动

```yaml
services:
  app:
    image: myapp:1.0            # 无 profiles = 永远启动
  debug-tools:
    image: netshoot
    profiles: ["debug"]         # 仅激活 debug profile 时启动
```

```bash
docker compose --profile debug up -d     # app + debug-tools
docker compose up -d                     # 只有 app
COMPOSE_PROFILES=debug docker compose up # 环境变量方式
```

适用：把调试工具、可选监控组件从默认启动集中摘出去。

### 8.3 一次性任务与 init 容器

Compose 没有 K8s 的 initContainer 概念，惯用做法是 8.1 中 `migrate` 模式：独立服务 + `command` 跑任务 + `restart: "no"` + 被依赖方用 `service_completed_successfully` 等它。也可用 `docker compose run --rm 服务 命令` 手动触发（不进启动流程）。

### 8.4 多文件组合：-f 叠加与 include

**`-f` 叠加**（同一项目分层覆盖）：

```bash
docker compose -f compose.yaml -f compose.override.yaml up
```

- 后面的文件对同名服务/字段做**合并覆盖**（标量覆盖、映射合并、列表追加）；
- 约定俗成：`compose.override.yaml` 放本地开发差异（挂源码、开调试端口），**自动加载**（与 compose.yaml 同目录时无需 -f）；生产用 `-f compose.yaml -f compose.prod.yaml`；
- 合并结果不确定时用 `docker compose config` 渲染查看。

**`include`**（V2 专属，模块化拆分）：

```yaml
include:
  - path: ./monitoring/compose.yaml     # 被包含文件独立解析（自己的 .env、相对路径基准）
    env_file: ./monitoring/.env
  - path:
      - ./db/compose.yaml
      - ./db/compose.override.yaml
```

与 `-f` 的区别：include 的文件是**独立项目片段**（相对路径、.env 以各自目录为基准），适合复用别人发布的组件；`-f` 是同项目的配置分层。

### 8.5 extends：服务继承

```yaml
services:
  app:
    extends:
      file: common-services.yaml    # 可省略 = 本文件内
      service: base-app
    environment:
      MODE: production              # 在继承基础上覆盖/追加
```

适合多个服务共享大段相同配置；与 YAML 锚点（8.6）二选一即可，锚点更轻、extends 跨文件更整洁。

### 8.6 YAML 锚点与 x-* 扩展字段

```yaml
x-logging: &default-logging        # x- 前缀字段 Compose 忽略，专供锚点复用
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"

services:
  backend:
    image: myapp:1.0
    logging: *default-logging      # 引用锚点
  worker:
    image: myapp:1.0
    logging: *default-logging
    environment: &worker-env
      QUEUE: default
  scheduler:
    image: myapp:1.0
    environment:
      <<: *worker-env              # 映射合并
      QUEUE: cron
```

### 8.7 develop.watch：文件变更自动响应

```yaml
services:
  backend:
    build: ./backend
    develop:
      watch:
        - action: sync             # 文件同步进容器（不重启）
          path: ./backend/app
          target: /srv/app
        - action: rebuild          # 变更触发重建容器
          path: ./backend/pyproject.toml
```

```bash
docker compose watch    # 启动监视（自动先 up）
```

三种 action：`sync`（同步文件）、`sync+restart`（同步并重启容器进程）、`rebuild`（重建镜像）。适合替代「改一行代码手动 build+up」的开发循环。

### 8.8 与 docker run 参数的对应关系

| docker run | compose 服务字段 |
|---|---|
| `-p 8080:80` | `ports: ["8080:80"]` |
| `-v ~/data:/app/data` | `volumes: ["~/data:/app/data"]` |
| `-e KEY=VALUE` / `--env-file` | `environment` / `env_file` |
| `--name` | `container_name` |
| `-d` | `up -d` |
| `--rm` | `run --rm` |
| `--network` | `networks` |
| `--add-host` | `extra_hosts` |
| `--restart` | `restart` |
| `--health-cmd` 等 | `healthcheck` |
| `-it` | `tty: true` + `stdin_open: true` |
| `--mount type=bind,...` | volumes 长语法 |
| `--memory` / `--cpus` | `mem_limit` / `cpus` |

---

## 九、项目 docker-compose.yml 对照解读（两个真实案例）

> 本节收录两个真实项目的 compose 对照解读，互为补充：**案例一（9.1–9.2）** 是本项目 pipeline-fault-tracker（双 build 服务 + SQLite + bind mount），解读与仓库根目录 `docker-compose.yml`（commit `e847e88`，已实测跑通 D4/D5 演练）逐字对应，构建细节见 [docker.md](docker.md) 第十二节；**案例二（9.3–9.4）** 是同机另一仓库 `python_learn`（`E:\python_learn\docker-compose.yml`，todo_api + MySQL 数据库容器化，2026-09-28 实测），演示独立数据库服务、命名卷与 `.env`/`${VAR:?}` 密钥管理；9.5 给两案例横向对照。案例二 YAML 为忠实节选（完整文件含更详注释）。

### 9.1 案例一（本项目 pipeline-fault-tracker）：文件全貌与逐字段解读

```yaml
services:
  backend:
    build: ./backend                        # 3.1 形态 B：从 backend/Dockerfile 构建
    environment:
      DATABASE_URL: sqlite:///./data/fault_tracker.db   # 3.5：与挂载点对齐
    volumes:
      - ~/pft-bind:/app/data                # 7.1 bind mount：数据落宿主机家目录
    healthcheck:                            # 3.6
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]
      interval: 5s
      timeout: 3s
      retries: 5

  frontend:
    build: ./frontend
    ports:
      - "8080:80"                           # 3.3：宿主机 8080 → nginx 容器 80
    depends_on:
      backend:
        condition: service_healthy          # 8.1：等后端探活通过才起前端
```

对照本文知识点的四个设计决策：

1. **backend 不写 `ports`**：后端只被 frontend 的 nginx 经项目默认网络以 `http://backend:8000` 反代访问（服务名互访，见 6.1），无需暴露到宿主机——少一个端口就少一个攻击面。
2. **healthcheck 用 python urllib 而非 curl**：后端基础镜像 `python:3.14-slim` 不带 curl，`test` 用 `CMD` 形态（不经 shell）直接调镜像内已有的 python（见 3.6）。
3. **bind mount 而非命名卷**：数据库文件直接落在 WSL 家目录 `~/pft-bind`，可 `ls`/备份；`down -v` 不会删它（`down -v` 只删命名卷，见 7.2）。
4. **`depends_on` 长语法 + `service_healthy`**：短语法只保证「backend 容器先启动」，不保证 uvicorn 已就绪；配 healthcheck 后 frontend 真正等到后端可服务（见 8.1）。

### 9.2 案例一配套约定

- `frontend/nginx.conf` 中 `proxy_pass http://backend:8000;` 的服务名 `backend` 即 compose 服务名——容器互访核心规则的落地（见 6.1）；
- 常用操作（在 WSL 内仓库目录执行）：

```bash
docker compose up -d --build   # 起双服务
docker compose ps              # backend 应为 healthy，frontend running
curl -s http://localhost:8080/api/health   # 经 nginx 同源反代验证后端
docker compose logs -f backend
docker compose down            # 数据仍在 ~/pft-bind，不受影响
```

### 9.3 案例二（python_learn：todo_api + MySQL）：文件全貌与逐字段解读

案例二来自同机另一学习仓库 `python_learn`（不在本工作区，文件位于 `E:\python_learn\docker-compose.yml`）。场景：把一个 todo_api 应用与它的 MySQL 数据库**一起容器化**——数据库不再跑在宿主机，而是独立服务，应用用服务名 `mysql` 作 `DB_HOST`（拓扑 C），从而摆脱「Docker 引擎在 WSL2 内时 host-gateway 指向 WSL 虚拟机、须手填 Windows 虚拟网卡 IP 且重启漂移」的老问题。以下为 services/volumes 的忠实节选（保留原文件关键注释）：

```yaml
services:
  mysql:
    image: mysql:8.4                        # 3.1 形态 A：现成镜像；版本须 ≥ 宿主机 MySQL 保证 dump 可导入
    environment:                            # 4.1/4.2：口令全部来自 .env 插值，不入库不进镜像
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:?请在 .env 中设置 MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE:?请在 .env 中设置 MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER:?请在 .env 中设置 MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD:?请在 .env 中设置 MYSQL_PASSWORD}
    command:                                # 3.2：覆盖启动参数，钉死 utf8mb4 与应用 charset 一致
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
    ports:
      - "127.0.0.1:3307:3306"               # 3.3：只绑回环 3307，与宿主机 MySQL 3306 并存；容器间通信不经此端口
    volumes:
      - mysql_data:/var/lib/mysql           # 7.2 命名卷：down 不丢，down -v 才删
    healthcheck:                            # 3.6 CMD 形态；test 内还嵌了 ${} 插值
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uroot", "-p${MYSQL_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s                     # 3.6：给 MySQL 初始化 30s 宽限，期间失败不计入 retries
    restart: unless-stopped                 # 3.7：异常自动拉起（除非手动 stop）

  todo-api:
    build: .                                # 3.1 形态 C：build 与 image 同写 = 构建产物打标签
    image: todo-api:0.1
    depends_on:
      mysql:
        condition: service_healthy          # 8.1：等 MySQL 探活通过再起应用
    ports:
      - "127.0.0.1:8000:8000"               # 3.3：只绑回环，与既有「仅监听 127.0.0.1」安全约定一致
    extra_hosts:
      - "host.docker.internal:host-gateway" # 3.9/6.1：Linux 引擎下打通容器→宿主机（对 DB 已非必需，保留备用）
    volumes:
      - ./day15_orm/db_config_local_container.py:/app/day15_orm/db_config_local.py:ro   # 3.4/7.1：单文件只读 bind mount 顶替镜像内配置，口令不落镜像层
    healthcheck:                            # 3.6：slim 镜像无 curl，urllib 探根路径
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s

volumes:
  mysql_data:                               # 7.2：顶层声明命名卷，实际卷名 python_learn_mysql_data
```

启动前置条件（一次性，PowerShell，摘自文件头注释；`.env` 含真实口令属敏感文件，不入库也不作为文档上下文）：

```powershell
Copy-Item .env.example .env                                                          # 填真实口令（.env 已被 .gitignore/.dockerignore 排除）
Copy-Item day15_orm\db_config_local_container.example.py day15_orm\db_config_local_container.py   # DB_HOST 写 "mysql"、DB_PORT 写 3306
```

其中 `.env` 的 `MYSQL_DATABASE/USER/PASSWORD` 须与 `db_config_local_container.py` 的 `DB_NAME/DB_USER/DB_PASSWORD` 一致；首次启动 MySQL 后导入宿主机现有数据（mysqldump）或走 `alembic upgrade head`，应用启动不做 `create_all`。

### 9.4 案例二设计决策与关键坑点

案例二在案例一基础上多演示的知识点：

1. **数据库独立成服务 + 服务名互访（6.1）**：`DB_HOST=mysql`，应用与库同处项目默认网络，靠服务名 DNS 解析。相比「应用连宿主机 MySQL」，规避了 WSL2 下 host-gateway 指向虚拟机、Windows 虚拟网卡 IP 重启漂移的顽疾（2026-09-28 实测确认）。
2. **`${VAR:?err}` 强制插值 + `.env` 管密钥（4.1/4.2）**：口令缺失时 `:?` 直接报错拒绝启动，避免带着空口令把命名卷初始化坏（初始化只有一次机会，见下方坑点）；`.env` 不入库、不进镜像层。这是案例一（SQLite、无敏感口令）用不上的安全模式。
3. **`image:` 与 `build:` 两种服务来源并存（3.1）**：mysql 用现成 `image`，todo-api 用 `build: .` 且同写 `image: todo-api:0.1` 给构建产物打标签。
4. **`command:` 覆盖启动参数（3.2）**：给 mysqld 追加 `--character-set-server=utf8mb4`，与应用侧 charset 对齐，避免中文乱码。
5. **端口只绑 127.0.0.1（3.3）**：mysql 映射到宿主 3307 与本机既有 MySQL 3306 并存不冲突；todo-api 8000 也只本机可达——两个服务都不对外网暴露。
6. **命名卷持久化（7.2）**：`mysql_data` 命名卷，`down` 不丢数据、`down -v` 才删；对比案例一为「可直接 ls/备份」而选 bind mount，这里数据库文件交给 Docker 管更省心。
7. **单文件只读 bind mount 顶替配置（3.4/7.1）**：把 `db_config_local_container.py` 以 `:ro` 盖到镜像内 `db_config_local.py` 的位置，运行期注入配置而口令不进镜像；对比案例一用构建期 `ARG`（`VITE_API_BASE_URL`）注入——一个是运行期挂载、一个是构建期参数。
8. **healthcheck 的 `start_period` 与嵌套插值（3.6）**：mysql 初始化慢，`start_period: 30s` 给足宽限；探活命令里直接嵌 `${MYSQL_ROOT_PASSWORD}` 插值。
9. **`restart: unless-stopped`（3.7）**：数据库异常自动重启，手动 `docker compose stop` 后则不自动拉起。

案例二特有的关键坑点（与第十节互补）：

- **官方 MySQL 镜像只在「空卷首启」时用 `MYSQL_*` 初始化库和账号**：`mysql_data` 卷一旦建好，之后再改 `.env` 里的口令/库名**不会生效**——必须删卷（`docker volume rm python_learn_mysql_data` 或 `down -v`）重新初始化，而删卷是**破坏性操作**，会丢光库内数据，须单独确认并先备份（不可逆操作须人工执行并配回退）。
- **镜像版本须 ≥ 宿主机 MySQL 版本**：否则 `mysqldump` 导出的 SQL 可能含目标版本不认的语法而无法导入；导入前用 `mysql --version` 核对。
- **`.env` 缺失时 `:?` 会让整个 `up` 直接失败**：这是刻意的「快速失败」，报错信息即中文提示，按提示补 `.env` 即可，不要改成 `:-` 给空默认值掩盖问题。

配套操作命令（案例二；PowerShell 用 `;` 不用 `&&`）：

```bash
docker compose up -d mysql          # 先只起数据库，便于导入宿主机现有数据
docker compose up -d --build        # 起全栈（todo-api 等 mysql healthy 后启动）
docker compose ps                   # 两服务均应 healthy
curl http://127.0.0.1:8000/         # WSL/bash 验证；PowerShell 用 Invoke-RestMethod http://127.0.0.1:8000/
docker compose down                 # 不带 -v，mysql_data 命名卷保留数据
```

### 9.5 两案例对照小结

| 维度 | 案例一 · pipeline-fault-tracker（本项目） | 案例二 · python_learn（todo_api + MySQL） |
|---|---|---|
| 服务构成 | 2 个都 `build`（backend + frontend） | 1 个 `image`（mysql:8.4）+ 1 个 `build`（todo-api） |
| 数据库 | SQLite（单文件，无独立服务） | MySQL 8.4（独立容器服务） |
| 持久化方式 | bind mount `~/pft-bind`（7.1） | 命名卷 `mysql_data`（7.2） |
| 密钥/敏感值 | 无（仅 SQLite 路径，明文 environment） | `.env` + `${VAR:?}` 强制插值（4.1/4.2） |
| 端口暴露 | 仅 frontend `8080:80`；backend 不暴露 | 两个都只绑 `127.0.0.1`（3307、8000） |
| 服务间互访 | nginx `proxy_pass http://backend:8000` | 应用 `DB_HOST=mysql:3306`（6.1） |
| 启动依赖 | frontend → backend `service_healthy` | todo-api → mysql `service_healthy`（8.1） |
| 健康检查 | urllib（slim 无 curl，3.6） | mysqladmin ping + urllib（均 CMD 形态，含 `start_period`） |
| 配置注入 | 构建期 `ARG VITE_API_BASE_URL`（3.1） | 运行期单文件只读 bind mount（3.4/7.1） |
| `command` 覆盖 | 无 | mysql 钉死 utf8mb4 charset（3.2） |
| `restart` 策略 | 未设（默认 `no`） | mysql `unless-stopped`（3.7） |
| 典型收获 | 同源反代、SPA 回退、最小暴露面 | 数据库容器化、密钥管理、命名卷初始化坑 |

一句话总结：案例一是「无独立数据库、构建期注入、bind mount」的轻量前后端编排；案例二是「独立数据库服务、运行期注入、命名卷 + `.env` 密钥」的数据层编排。两者合起来覆盖了 Compose 单机编排最常见的两类拓扑。

---

## 十、常见坑点与排障

1. **`depends_on` ≠ 就绪**：短语法只保证启动顺序；被依赖服务没配 healthcheck 时，依赖方可能在数据库还没监听端口时就启动并报连接失败。解法见 8.1。
2. **顶层 `version:` 告警**：新文件写了 `version: "3"` 会收到 `the attribute version is obsolete` 告警——删掉即可，不影响运行（见 1.2）。
3. **端口短语法不加引号**：`- 80:80` 可能被 YAML 解析为六十进制整数（`80:80` → 4880）。`ports` 条目**永远加引号**（见 3.3）。
4. **`down -v` 删数据**：命名卷随 `-v` 不可逆删除；重要数据要么用 bind mount，要么 down 前先备份卷（见 7.2）。
5. **`.env` 不会注入容器**：`.env` 只服务 compose 文件插值；容器要拿到变量必须经 `environment` / `env_file` 显式声明（见 4.2）。
6. **bind mount 路径写错静默成功**：宿主机路径不存在时 Linux 下自动建空目录，应用报「数据怎么全没了」而不是「路径错了」——挂载前核对路径（见 7.1）。
7. **容器内 `localhost` 不是宿主机**：容器访问宿主机服务要用 `host.docker.internal`（Linux 需 `extra_hosts: ["host.docker.internal:host-gateway"]`）；访问同项目其他容器用**服务名**（见 6.1、3.9）。
8. **`container_name` 写死导致无法 scale**：固定名与多副本冲突；需要扩缩的服务不要写 `container_name`（见 3.2）。
9. **改了 Dockerfile 但 `up` 没重建**：`up -d` 只在检测到配置/镜像变化时重建；显式加 `--build`，或 `docker compose build` 后再 up。缓存层看不清时加 `--progress=plain`（见 5.2、5.4）。
10. **多文件合并结果与预期不符**：`-f a.yaml -f b.yaml` 的列表字段是追加不是覆盖、映射是深合并——不确定就 `docker compose config` 渲染最终态再判断（见 8.4、5.3）。
11. **排障三板斧**：
    - `docker compose config -q`：YAML/插值层错误（语法、未定义变量）；
    - `docker compose ps` + `docker compose logs 服务`：容器层错误（起不来、崩溃循环看退出原因）;
    - `docker compose exec 服务 sh`：进入容器核对文件、环境变量、网络连通（`wget -qO- http://其他服务:端口`）。

---

## 十一、命令速查表

```bash
# ── 生命周期 ──────────────────────────────────────────────
docker compose up -d                        # 后台拉起（自动对账重建）
docker compose up -d --build                # 先构建再拉起
docker compose up -d --wait                 # 阻塞到全部 healthy
docker compose up -d --scale worker=3       # 指定副本数
docker compose down                         # 停止并删容器/默认网络（留卷）
docker compose down -v                      # 连命名卷一起删（危险）
docker compose down --rmi local             # 连本地构建镜像一起删
docker compose stop / start / restart       # 只动运行状态，不建不删
docker compose restart 服务名

# ── 查看与排障 ────────────────────────────────────────────
docker compose ps -a                        # 容器状态（含已停止）
docker compose logs -f --tail 100 服务名    # 跟随日志
docker compose config                       # 渲染最终合并配置
docker compose config -q                    # 仅校验
docker compose exec -it 服务名 sh           # 进入运行中容器
docker compose run --rm 服务名 命令         # 一次性容器
docker compose port 服务名 80               # 查端口映射
docker compose stats                        # 资源占用
docker compose ls                           # 本机所有项目

# ── 镜像与构建 ────────────────────────────────────────────
docker compose build --no-cache             # 无缓存重建
docker compose build --progress=plain       # 完整输出（看 CACHED）
docker compose pull                         # 拉取全部服务镜像
docker compose push                         # 推送（需 image: 名）

# ── 全局参数 ──────────────────────────────────────────────
docker compose -f a.yaml -f b.yaml up -d    # 多文件叠加
docker compose -p 项目名 up -d              # 指定项目名
docker compose --env-file .env.prod up -d   # 指定插值 env 文件
docker compose --profile debug up -d        # 激活 profile
docker compose --dry-run up                 # 演习模式

# ── 开发效率 ──────────────────────────────────────────────
docker compose watch                        # 文件变更自动 sync/rebuild
docker compose up -d --force-recreate 服务  # 强制重建单个服务
docker compose logs -f 服务A 服务B          # 多服务日志合流
```

---

> 参考出处：Compose Specification（github.com/compose-spec/compose-spec）、Docker 官方文档 Compose 章节（docs.docker.com/compose/）。字段与参数以本机 `docker compose <命令> --help` 为最终依据。

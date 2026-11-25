# Docker 练习计划（载体：pipeline-fault-tracker）

> 来源：2026-09-18 阶段评估邮件方向⑤「工程化能力……后续按实际项目需要学习 Docker 和 Docker Compose」+ 王潼老师「WSL 贴近部署环境、配合 Docker 容器化减少环境差异」建议。
> 定位：接替 `_next_week_plan.md` 的「延伸——Docker」槽位；在现有项目上练，不另起新仓库。
> 制定日期：2026-09-21。

## 0. 现状基线（2026-09-21 全部实测）

| 项 | 结论 | 证据 |
|---|---|---|
| Docker | **未安装** | `docker --version` → CommandNotFoundException |
| WSL | Ubuntu（WSL2）已装、Stopped | `wsl -l -v` → `* Ubuntu Stopped 2` |
| 建表路径 | 启动仍走 `lifespan → init_models() = create_all(checkfirst=True)`；alembic 目录已存在但**未接入启动路径** | `backend/app/main.py` L26-41 |
| 配置 env 名 | `DATABASE_URL` / `HOST` / `PORT` / `CORS_ORIGINS`（pydantic-settings，大小写不敏感） | `backend/app/config.py` L27-36 |
| 探活端点 | `/` 与 `/api/health`（compose healthcheck 直接用） | `backend/app/main.py` L85-98 |
| 依赖路线 | pip + `requirements.lock.txt`（项目 `.gitignore` 明确声明不用 uv，镜像内不得用 uv） | `.gitignore` |
| 前端构建约束 | Node 16 锁定（node:16 系镜像）；`VITE_API_BASE_URL` 为**构建期**替换，undefined 会拼出 `undefined/api/...` | stage-7 实测坑 |
| Docker 产物 | 无（`backend/Dockerfile`、根 `docker-compose.yml` 均不存在） | Test-Path |

## 1. 目标与非目标

- **目标**：前后端容器化 + Compose 编排 + SQLite 持久化；吃透镜像/容器/卷/网络四件套；能独立排障。
- **非目标**：TLS、镜像签名、CI 推 registry、K8s、多环境配置分离——本次不碰。

## 2. Session 0 —— 环境准备（安装属环境变更，须先经用户确认，规则 2.5）

- **路线 B（推荐主线）**：WSL Ubuntu 内装 Docker Engine + compose 插件（`/etc/wsl.conf` 启用 systemd）。最贴近 Linux 部署形态，顺带练 Linux 命令，呼应王潼老师建议。
- **路线 A（兜底）**：Windows 装 Docker Desktop（WSL2 后端），PowerShell 直接用 `docker`，省事。
- **验证**：`docker --version`；`docker compose version`；`docker run --rm hello-world`
- **概念清单**：镜像 vs 容器 vs registry；Dockerfile 指令集（FROM/WORKDIR/COPY/RUN/EXPOSE/CMD/ENTRYPOINT/ARG/ENV）；层与构建缓存；bind mount vs named volume；bridge 网络与服务名解析；compose 与 docker run 的分工。

## 3. 分节安排

### D1 —— backend 镜像

- `backend/.dockerignore`：`.venv/`、`__pycache__/`、`*.db`、`.env`、`.idea/`
- `backend/Dockerfile`（pip 路线）：

  ```dockerfile
  FROM python:3.14-slim
  WORKDIR /app
  COPY requirements.lock.txt .
  RUN pip install --no-cache-dir -r requirements.lock.txt
  COPY app/ ./app/
  COPY alembic/ ./alembic/
  COPY alembic.ini .
  EXPOSE 8000
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- **三个考点**：先 COPY lock 再 COPY 代码（层缓存，改代码不重装依赖）；`--no-cache-dir` 瘦身；必须绑 `0.0.0.0`（容器内 `127.0.0.1` 外部不可达）。
- **验证**：`docker build -t pft-backend:0.1 backend/` → `docker run --rm -p 8000:8000 pft-backend:0.1` → 宿主机 `curl http://127.0.0.1:8000/api/health`
- **验收**：返回 `{"status":"ok"}`；能说清三考点；`docker image ls` 对比 slim 与默认 tag 体积。

### D2 —— 数据持久化（volume）

- **丢失演示**：登记一条故障 → `docker rm -f` 容器 → 重启 → 数据没了（db 文件在容器可写层）。
- **named volume**：`docker run --rm -p 8000:8000 -v pft-data:/app/data -e DATABASE_URL=sqlite:///./data/fault_tracker.db pft-backend:0.1`
- 删容器、同卷重建 → 数据仍在；`docker volume ls` / `docker volume inspect pft-data`；对比 bind mount（`-v 宿主路径:/app/data`）的适用差异。
- **不可逆演练**（规则 2.6 心智）：`docker volume rm` = 删数据；练「先备份再删」（`docker cp` 或临时 busybox 容器导出 tar）。
- **验收**：跨容器重建数据不丢；能说清 named volume 与 bind mount 的差异与选型。

### D3 —— frontend 两阶段构建 + nginx 同源代理

- `frontend/Dockerfile`：

  ```dockerfile
  # ---- stage 1：构建（必须 Node 16 系，项目锁定） ----
  FROM node:16.20.2-alpine AS build
  WORKDIR /app
  COPY package.json package-lock.json ./
  RUN npm ci
  COPY . .
  ARG VITE_API_BASE_URL=
  ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
  RUN npm run build

  # ---- stage 2：仅 nginx + 静态产物 ----
  FROM nginx:alpine
  COPY --from=build /app/dist /usr/share/nginx/html
  COPY nginx.conf /etc/nginx/conf.d/default.conf
  ```

- `frontend/.dockerignore`：`node_modules/`、`dist/`、`.env`
- `frontend/nginx.conf`：`location /api/ { proxy_pass http://backend:8000; }`（compose 网络内）；D3 单容器试跑阶段改用 `proxy_pass http://host.docker.internal:8000;`（路线 B 的引擎需给容器加 `--add-host=host.docker.internal:host-gateway`）。
- **坑点警示**：`VITE_*` 是构建期替换；ARG 不传 = undefined = 请求路径变 `undefined/api/...`（stage-7 踩过的坑），**必须显式传空串**走同源。
- **考点**：同源代理后浏览器不再跨域，CORS 配置不再需要（对比 dev 模式 5173→8000 跨源 + CORS 白名单）。
- **验收**：浏览器开 nginx 端口走通列表/登记/详情；Network 面板无 CORS 报错；能说清两阶段构建为何镜像小（终镜像不含 node 工具链）。

### D4 —— Compose 编排

- 根 `docker-compose.yml`：

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

  （healthcheck 用 python urllib：slim 镜像无 curl。）
- **命令集**：`docker compose up -d --build` / `ps` / `logs -f backend` / `down` / `down -v`（**警示：`-v` 连卷一起删**）。
- **核心概念**：容器互访用**服务名** `backend:8000`，不是 localhost。
- **验收**：一条命令起双服务走通全闭环；`down`（不带 -v）再 `up` 数据仍在；能说清 depends_on 只管启动顺序、不管就绪（配 healthcheck 才管就绪）。

### D5 —— 运维排障 + 镜像优化 + 产物归属

- **排障三件套**：`docker logs` / `docker exec -it <c> sh` / `docker inspect`；`docker system df`。
- **埋雷演练**：故意改坏 CMD 端口或 nginx conf → 靠 logs 定位并修复。
- **优化对照表**：有无 `.dockerignore`、有无 `--no-cache-dir`、slim vs bookworm 基镜像 → 镜像体积表；改一行代码重建，观察 pip 层缓存命中。
- **可选进阶**：entrypoint.sh 先 `alembic upgrade head` 再启 uvicorn；讨论其与 `create_all(checkfirst=True)` 的分工与表结构漂移风险（涉代码改动，按规则 2.2 另行确认）。
- **归属决策**：练稳后 Dockerfile / nginx.conf / docker-compose.yml 以**独立提交**（`feat(docker):` 或 `chore(docker):`）入 target 仓库——正好回应评估「缺少 Git 历史记录」扣分点；或仅留练习产物不入库。由用户定。
- **验收**：独立定位并修复一个埋雷；产出镜像体积对照表。

## 4. 压缩变体（时间紧时 3 次）

- S1 = D0 + D1；S2 = D2 + D3；S3 = D4 + D5（略优化对照与埋雷演练）。

## 5. 与原计划衔接

- 接替 `_next_week_plan.md`「延伸——Docker」槽位。
- 路线 B 建议在本周 D5（WSL 跑通）完成后启动（依赖 WSL）；路线 A 可与本周计划并行。
- 全程保持约定式提交；Docker 产物若入库须独立提交，不与功能改动混合（规则 3.5 精神）。

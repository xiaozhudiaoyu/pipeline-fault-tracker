# frontend 镜像：两阶段构建（Node 构建 → nginx 托管静态产物）。
# 构建：cd frontend && docker build -t pft-frontend:0.1 .
# 运行：docker run --rm -p 8080:80 --add-host=host.docker.internal:host-gateway pft-frontend:0.1

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

# ============================================================
# NaviRoom 前端 — 多阶段构建
# 阶段 1: Node.js 20 + npm 编译（国内默认走 npmmirror）
# 阶段 2: Nginx 静态文件服务
# ============================================================

# ==================== 阶段 1: 构建 ====================
FROM node:20-alpine AS builder

WORKDIR /app

# npm 镜像（默认淘宝源，海外部署覆盖为 https://registry.npmjs.org）
ARG NPM_REGISTRY=https://registry.npmmirror.com

# 先复制依赖配置文件（利用缓存）
COPY frontend/package.json ./
COPY frontend/package-lock.json ./

# 安装依赖（使用国内镜像）
RUN npm ci --registry=${NPM_REGISTRY}

# 复制源码
COPY frontend/ ./

# 生产构建
RUN npm run build

# ==================== 阶段 2: 运行 ====================
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx SPA 配置
COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

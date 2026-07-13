# NaviRoom Docker 化部署指南

> **适用版本**：NaviRoom 3.0.0+
> **最后更新**：2026-07-13
> **目标读者**：NaviRoom 项目的开发者、运维人员

---

## 目录

- [一、概述](#一概述)
- [二、前置条件](#二前置条件)
- [三、架构设计](#三架构设计)
- [四、目录结构](#四目录结构)
- [五、Dockerfile 定义](#五dockerfile-定义)
  - [5.1 API 服务（Python/FastAPI）](#51-api-服务pythonfastapi)
  - [5.2 前端（多阶段构建）](#52-前端多阶段构建)
  - [5.3 数据管道（一次性运行）](#53-数据管道一次性运行)
  - [5.4 Nginx 反向代理](#54-nginx-反向代理)
- [六、Docker Compose 编排](#六docker-compose-编排)
  - [6.1 主编排文件](#61-主编排文件)
  - [6.2 生产环境覆盖](#62-生产环境覆盖)
  - [6.3 环境变量文件](#63-环境变量文件)
- [七、MySQL 初始化](#七mysql-初始化)
- [八、Nginx 配置](#八nginx-配置)
- [九、操作手册](#九操作手册)
  - [9.1 环境准备](#91-环境准备)
  - [9.2 首次部署](#92-首次部署)
  - [9.3 生产部署](#93-生产部署)
  - [9.4 日常运维](#94-日常运维)
  - [9.5 更新部署](#95-更新部署)
  - [9.6 备份与恢复](#96-备份与恢复)
  - [9.7 水平扩展](#97-水平扩展)
  - [9.8 回滚](#98-回滚)
- [十、故障排查](#十故障排查)
- [十一、Docker vs Ansible 对比](#十一docker-vs-ansible-对比)
- [十二、安全建议](#十二安全建议)
- [十三、附录](#十三附录)

---

## 一、概述

NaviRoom 当前使用 Ansible 进行部署，目标环境为 Ubuntu 22.04。本指南提供完整的 Docker 化替代方案，实现：

- **一键部署**：`docker compose up -d` 即可启动全部服务
- **环境一致**：开发、测试、生产环境完全一致
- **跨平台**：支持 Linux、macOS（Apple Silicon/Intel）、Windows（WSL2）
- **易于扩展**：`docker compose up -d --scale api=3` 直接水平扩容
- **快速回滚**：指定旧版镜像即可回退

### 容器服务映射关系

| 原 Ansible Role | Docker 服务 | 镜像 | 端口 |
|---|---|---|---|
| `mysql` | `mysql` | `mysql:8.0` | 3306 |
| `app` | `api` | 自定义（Python 3.11） | 8000 |
| `frontend` | `frontend` | 自定义（Nginx + 构建产物） | 3000 |
| `nginx` | `nginx` | `nginx:alpine` | 80/443 |
| —（无对应） | `data-pipeline` | 自定义（一次性运行） | — |

### 容器间通信

```
                    ┌──────────────┐
                    │   nginx      │  :80/:443 (HTTPS)
                    │   (反向代理)   │──────── 外部用户
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            │
     ┌──────────┐  ┌────────────┐      │
     │ frontend │  │    api     │      │
     │ (静态文件) │  │ (FastAPI)  │      │
     │ :3000    │  │ :8000      │      │
     └──────────┘  └─────┬──────┘      │
                         │             │
                         ▼             │
                  ┌──────────┐        │
                  │  mysql   │        │
                  │  :3306   │        │
                  └──────────┘        │
                         │            │
                  ┌──────────────┐    │
                  │ data-pipeline│    │
                  │ (一次性运行)   │    │
                  └──────────────┘    │
                                      │
   所有容器通过 naviroom-network bridge 网络互联
   内部 DNS 自动解析容器名（mysql、api、frontend、nginx）
```

---

## 二、前置条件

### 2.1 软件要求

| 软件 | 最低版本 | 安装指南 |
|---|---|---|
| Docker Engine | 24.0+ | https://docs.docker.com/engine/install/ |
| Docker Compose | v2.20+ | 随 Docker Desktop 附带，或 `apt install docker-compose-plugin` |
| Git | 2.30+ | https://git-scm.com/downloads |

### 2.2 硬件要求

| 环境 | CPU | 内存 | 磁盘 |
|---|---|---|---|
| 开发/测试 | 2 核 | 4 GB | 10 GB 可用 |
| 生产（最小） | 2 核 | 8 GB | 50 GB SSD |
| 生产（推荐） | 4 核 | 16 GB | 100 GB SSD |

### 2.3 安装 Docker（Ubuntu 快速指南）

```bash
# 卸载旧版本（如有）
sudo apt remove docker docker-engine docker.io containerd runc

# 安装依赖
sudo apt update
sudo apt install -y ca-certificates curl gnupg

# 添加 Docker GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 添加 Docker 仓库
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine 和 Compose 插件
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 将当前用户加入 docker 组（避免每次 sudo）
sudo usermod -aG docker $USER
newgrp docker

# 验证安装
docker --version        # Docker version 24.x+
docker compose version  # Docker Compose version v2.x+
docker run hello-world  # 测试运行
```

### 2.4 克隆项目

```bash
git clone <repository-url> NaviRoom
cd NaviRoom

# 项目结构确认
ls -l
# 应看到：
#   Data_processing/
#   recommendation/
#   frontend/
#   "NaviRoom Homepage Upload Interface Version2"/
#   deploy/
#   README.md
```

---

## 三、架构设计

### 3.1 服务分层

```
┌──────────────────────────────────────────────────┐
│                    接入层                          │
│  ┌────────────┐                    ┌───────────┐ │
│  │   Nginx    │ ← TLS 终结        │  Frontend  │ │
│  │ (反向代理)  │ ← 请求路由         │  (开发直连) │ │
│  └─────┬──────┘                    └───────────┘ │
└────────┼──────────────────────────────────────────┘
         │
┌────────┼──────────────────────────────────────────┐
│        ▼                API 层                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │   API    │  │   API    │  │   API    │  ...   │
│  │ (实例 1)  │  │ (实例 2)  │  │ (实例 N)  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
└───────┼──────────────┼─────────────┼──────────────┘
        │              │             │
        └──────────────┼─────────────┘
                       │
┌──────────────────────┼──────────────────────────────┐
│                      ▼           数据层              │
│  ┌──────────┐                    ┌───────────────┐  │
│  │  MySQL   │ ← 持久化存储       │ Data Pipeline │  │
│  │  :3306   │                    │ (一次性任务)   │  │
│  └──────────┘                    └───────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 3.2 数据卷设计

| 卷名 | 类型 | 用途 | 持久化 |
|---|---|---|---|
| `mysql_data` | named volume | MySQL 数据文件 | ✅ 是 |
| `./Data_processing/output` | bind mount | 处理后的 JSON 数据集 | ✅ 是（共享） |
| `./Data_processing/data` | bind mount | 原始数据文件（只读） | ✅ 是（共享） |
| `./docker/nginx/certs` | bind mount | TLS 证书（生产） | ✅ 是 |

### 3.3 网络隔离

所有容器加入同一个 `naviroom-network` bridge 网络：
- 容器间通过服务名互相访问（如 `api:8000`、`mysql:3306`）
- 宿主机通过 `localhost:<port>` 访问暴露的端口
- 生产环境仅暴露 nginx（80/443），其他服务端口不对外

---

## 四、目录结构

部署前需要在项目中创建以下 Docker 相关文件：

```
NaviRoom/
├── docker/
│   ├── api/
│   │   └── Dockerfile              # FastAPI 后端镜像
│   ├── frontend/
│   │   ├── Dockerfile              # 前端多阶段构建镜像
│   │   └── nginx.conf              # 前端 Nginx 配置（SPA 路由）
│   ├── nginx/
│   │   ├── Dockerfile              # 生产反向代理镜像
│   │   └── nginx.conf              # 反向代理配置
│   ├── data-pipeline/
│   │   ├── Dockerfile              # 数据管道镜像
│   │   └── entrypoint.sh           # 管道入口脚本
│   └── mysql/
│       └── init/
│           └── 01-init-tables.sql  # 数据库初始化 DDL
├── docker-compose.yml              # 主编排文件
├── docker-compose.prod.yml         # 生产环境覆盖配置
├── .env.docker                     # 环境变量模板
└── .gitignore                      # 需添加 .env 排除规则
```

创建以上目录：

```bash
mkdir -p docker/{api,frontend,nginx,data-pipeline,mysql/init}
```

---

## 五、Dockerfile 定义

### 5.1 API 服务（Python/FastAPI）

**文件**：`docker/api/Dockerfile`

```dockerfile
# ============================================================
# NaviRoom API 服务
# 基于 Python 3.11，运行 FastAPI 应用
# ============================================================
FROM python:3.11-slim-bookworm

# 系统依赖
# gcc/g++: 编译 spaCy 的 C 扩展（thinc、blis 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- 依赖安装（利用 Docker 层缓存） ----------
COPY Data_processing/requirements.txt /app/requirements-data.txt

RUN pip install --no-cache-dir -r /app/requirements-data.txt && \
    pip install --no-cache-dir \
    fastapi==0.135.1 \
    uvicorn[standard]==0.42.0 \
    python-multipart==0.0.22 \
    sqlalchemy==2.0.48 \
    pymysql==1.1.2 \
    bcrypt==5.0.0 \
    python-jose[cryptography]==3.5.0 \
    python-dotenv==1.1.0 \
    openai==1.93.2 \
    pandas==2.2.3

# 下载 spaCy 英文模型（最耗时，尽量放前面利用缓存）
RUN python -m spacy download en_core_web_sm

# ---------- 应用代码 ----------
COPY Data_processing/ /app/Data_processing/
COPY recommendation/ /app/recommendation/

# ---------- 运行时配置 ----------
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

# 非 root 用户运行（安全最佳实践）
RUN useradd --create-home --shell /bin/bash naviroom && \
    chown -R naviroom:naviroom /app
USER naviroom

CMD ["uvicorn", "recommendation.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 5.2 前端（多阶段构建）

**文件**：`docker/frontend/Dockerfile`

```dockerfile
# ============================================================
# NaviRoom 前端 — 多阶段构建
# 阶段 1: Node.js 20 + pnpm 编译
# 阶段 2: Nginx 静态文件服务
# ============================================================

# ==================== 阶段 1: 构建 ====================
FROM node:20-alpine AS builder

WORKDIR /app

# 启用 pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# 先复制依赖配置文件（利用缓存）
# 注意：使用 "NaviRoom Homepage Upload Interface Version2" 目录
COPY "NaviRoom Homepage Upload Interface Version2/package.json" ./
COPY "NaviRoom Homepage Upload Interface Version2/pnpm-workspace.yaml" ./
# 如有 pnpm-lock.yaml，一并复制
COPY "NaviRoom Homepage Upload Interface Version2/pnpm-lock.yaml" ./ 2>/dev/null || true

# 安装依赖
RUN pnpm install --frozen-lockfile || pnpm install --no-frozen-lockfile

# 复制源码
COPY "NaviRoom Homepage Upload Interface Version2/" ./

# 生产构建
RUN pnpm run build

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
```

**前端 Nginx 配置**：`docker/frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;
    gzip_min_length 1000;

    # SPA 路由：所有非文件请求回退到 index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源长期缓存（文件名带 hash）
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API 请求代理到后端
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /recommend/ {
        proxy_pass http://api:8000/recommend/;
        proxy_set_header Host $host;
    }

    location /auth/ {
        proxy_pass http://api:8000/auth/;
        proxy_set_header Host $host;
    }

    location /data/ {
        proxy_pass http://api:8000/data/;
        proxy_set_header Host $host;
    }

    location /healthz {
        proxy_pass http://api:8000/healthz;
    }

    # 上传大小限制
    client_max_body_size 20M;
}
```

### 5.3 数据管道（一次性运行）

**文件**：`docker/data-pipeline/Dockerfile`

```dockerfile
# ============================================================
# NaviRoom 数据管道 — 一次性运行容器
# 用于执行数据清洗流水线，生成结构化 JSON 数据集
# ============================================================
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Data_processing/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
    python -m spacy download en_core_web_sm

COPY Data_processing/ /app/Data_processing/

VOLUME ["/app/Data_processing/output"]

COPY docker/data-pipeline/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

**管道入口脚本**：`docker/data-pipeline/entrypoint.sh`

```bash
#!/bin/bash
# NaviRoom 数据管道入口
# 通过环境变量控制输入输出
set -e

echo "=========================================="
echo "  NaviRoom Data Pipeline"
echo "=========================================="

# 默认值
ROOMS_INPUT="${ROOMS_INPUT:-Data_processing/data/dku_room_data/rooms.csv}"
RESERVATIONS_INPUT="${RESERVATIONS_INPUT:-}"
OUTPUT_PATH="${OUTPUT_PATH:-Data_processing/output/dataset.json}"

# 构建命令
CMD="python Data_processing/scripts/pipeline.py"
CMD="$CMD --rooms ${ROOMS_INPUT}"
CMD="$CMD --output ${OUTPUT_PATH}"

if [ -n "$RESERVATIONS_INPUT" ]; then
    CMD="$CMD --reservations ${RESERVATIONS_INPUT}"
    echo "[INFO] 预订数据: ${RESERVATIONS_INPUT}"
fi

if [ "${SAVE_TO_DB:-false}" = "true" ]; then
    CMD="$CMD --save-to-db --db-password ${DB_PASSWORD}"
    echo "[INFO] 将写入 MySQL 数据库"
fi

echo "[INFO] 房间数据: ${ROOMS_INPUT}"
echo "[INFO] 输出路径: ${OUTPUT_PATH}"
echo "[RUN]  $CMD"
echo ""

exec $CMD
```

### 5.4 Nginx 反向代理

**文件**：`docker/nginx/Dockerfile`

```dockerfile
# ============================================================
# NaviRoom 生产环境 Nginx 反向代理
# ============================================================
FROM nginx:alpine

# 复制站点配置
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost:80/healthz || exit 1

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
```

---

## 六、Docker Compose 编排

### 6.1 主编排文件

**文件**：`docker-compose.yml`

```yaml
version: "3.8"

# ============================================================
# NaviRoom Docker 编排
# ============================================================

services:
  # ==================== MySQL 数据库 ====================
  mysql:
    image: mysql:8.0
    container_name: naviroom-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    ports:
      - "${MYSQL_PORT:-3306}:3306"
    volumes:
      # 数据持久化
      - mysql_data:/var/lib/mysql
      # 初始化脚本（首次启动时自动执行 .sql / .sh 文件）
      - ./docker/mysql/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test:
        [
          "CMD",
          "mysqladmin",
          "ping",
          "-h",
          "localhost",
          "-u",
          "root",
          "-p${MYSQL_ROOT_PASSWORD}"
        ]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 40s
    networks:
      - naviroom-network
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

  # ==================== FastAPI 后端 ====================
  api:
    build:
      context: .
      dockerfile: docker/api/Dockerfile
    container_name: naviroom-api
    restart: unless-stopped
    environment:
      # 数据库连接
      DB_HOST: mysql
      DB_PORT: "3306"
      DB_NAME: ${DB_NAME}
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      # 推荐引擎配置
      RECO_SEMANTIC_MODE: ${RECO_SEMANTIC_MODE:-hybrid}
      RECO_REQUIREMENTS_MODE: ${RECO_REQUIREMENTS_MODE:-merge}
      RECO_LLM_TOP_K: ${RECO_LLM_TOP_K:-8}
      RECO_RECENCY_HALF_LIFE_DAYS: ${RECO_RECENCY_HALF_LIFE_DAYS:-30}
      RECO_DATASET_PATH: ${RECO_DATASET_PATH:-Data_processing/output/dku_dataset.json}
      # LLM API（DeepSeek）
      LLM_API_KEY: ${LLM_API_KEY:-}
      # JWT 认证
      SECRET_KEY: ${SECRET_KEY}
      ALGORITHM: HS256
      ACCESS_TOKEN_EXPIRE_MINUTES: ${ACCESS_TOKEN_EXPIRE_MINUTES:-1440}
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      # 数据文件共享
      - ./Data_processing/output:/app/Data_processing/output
      - ./Data_processing/data:/app/Data_processing/data:ro
    depends_on:
      mysql:
        condition: service_healthy
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
        ]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
    networks:
      - naviroom-network
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "3"

  # ==================== 数据管道（一次性运行） ====================
  data-pipeline:
    build:
      context: .
      dockerfile: docker/data-pipeline/Dockerfile
    container_name: naviroom-pipeline
    # 仅在指定 profile 时运行
    profiles:
      - init
      - pipeline
    environment:
      ROOMS_INPUT: ${PIPELINE_ROOMS:-Data_processing/data/dku_room_data/rooms.csv}
      RESERVATIONS_INPUT: ${PIPELINE_RESERVATIONS:-}
      OUTPUT_PATH: ${PIPELINE_OUTPUT:-Data_processing/output/dku_dataset.json}
      SAVE_TO_DB: "${PIPELINE_SAVE_TO_DB:-false}"
      DB_HOST: mysql
      DB_USER: ${DB_USER}
      DB_PASSWORD: ${DB_PASSWORD}
      DB_NAME: ${DB_NAME}
    volumes:
      - ./Data_processing/output:/app/Data_processing/output
      - ./Data_processing/data:/app/Data_processing/data:ro
    depends_on:
      mysql:
        condition: service_healthy
    networks:
      - naviroom-network

  # ==================== 前端 ====================
  frontend:
    build:
      context: .
      dockerfile: docker/frontend/Dockerfile
    container_name: naviroom-frontend
    restart: unless-stopped
    ports:
      - "${FRONTEND_PORT:-3000}:80"
    depends_on:
      api:
        condition: service_healthy
    networks:
      - naviroom-network
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

  # ==================== Nginx 反向代理（生产环境） ====================
  nginx:
    build:
      context: .
      dockerfile: docker/nginx/Dockerfile
    container_name: naviroom-nginx
    restart: unless-stopped
    profiles:
      - production
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ${TLS_CERT_DIR:-./docker/nginx/certs}:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - api
    networks:
      - naviroom-network
    logging:
      driver: "json-file"
      options:
        max-size: "20m"
        max-file: "3"

volumes:
  mysql_data:
    driver: local

networks:
  naviroom-network:
    driver: bridge
```

### 6.2 生产环境覆盖

**文件**：`docker-compose.prod.yml`

```yaml
version: "3.8"

# ============================================================
# NaviRoom 生产环境覆盖配置
# 使用方式：docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# ============================================================

services:
  mysql:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M

  api:
    # 生产环境不直接暴露 API 端口（仅通过 nginx 访问）
    ports: []
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
    environment:
      RECO_SEMANTIC_MODE: hybrid

  frontend:
    # 生产环境不直接暴露前端端口
    ports: []

  nginx:
    # 生产环境总是启用 nginx
    profiles: []
    ports:
      - "80:80"
      - "443:443"
    volumes:
      # 使用 Let's Encrypt 签发的正式证书
      - /etc/letsencrypt/live/naviroom.cn/fullchain.pem:/etc/nginx/ssl/fullchain.crt:ro
      - /etc/letsencrypt/live/naviroom.cn/privkey.pem:/etc/nginx/ssl/privkey.key:ro
```

### 6.3 环境变量文件

**文件**：`.env.docker`（模板）

```bash
# ============================================================
# NaviRoom Docker 环境变量
# 使用方法：cp .env.docker .env，然后编辑 .env 填入实际值
# ⚠️  .env 文件包含敏感信息，不要提交到 Git！
# ============================================================

# ==================== MySQL ====================
MYSQL_ROOT_PASSWORD=changeme_root_password
DB_NAME=navi_room_db
DB_USER=navi_user
DB_PASSWORD=changeme_user_password
MYSQL_PORT=3306

# ==================== API 服务 ====================
API_PORT=8000
SECRET_KEY=change_me_to_a_random_secret_key_at_least_32_chars
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ==================== 推荐引擎 ====================
# 语义匹配模式: lexical | llm | hybrid | zero_shot
RECO_SEMANTIC_MODE=hybrid
# 需求提取模式: manual | llm | merge
RECO_REQUIREMENTS_MODE=merge
# LLM rerank 最大候选数
RECO_LLM_TOP_K=8
# 行为评分半衰期（天）
RECO_RECENCY_HALF_LIFE_DAYS=30
# 默认数据集路径（容器内路径，不要修改）
RECO_DATASET_PATH=Data_processing/output/dku_dataset.json

# ==================== LLM API（DeepSeek） ====================
# 如果不使用 LLM 功能，可以留空
LLM_API_KEY=sk-your-deepseek-api-key-here

# ==================== 前端 ====================
FRONTEND_PORT=3000

# ==================== 数据管道 ====================
# 房间数据源（容器内路径）
PIPELINE_ROOMS=Data_processing/data/dku_room_data/rooms.csv
# 预订数据源（如无预订数据则留空）
PIPELINE_RESERVATIONS=
# 输出路径
PIPELINE_OUTPUT=Data_processing/output/dku_dataset.json
# 是否写入数据库（首次导入设为 true）
PIPELINE_SAVE_TO_DB=false

# ==================== TLS 证书 ====================
# 本地开发可使用自签名证书，生产环境指向 Let's Encrypt 目录
TLS_CERT_DIR=./docker/nginx/certs
```

---

## 七、MySQL 初始化

**文件**：`docker/mysql/init/01-init-tables.sql`

此文件在 MySQL 容器**首次启动**时自动执行。仅在数据库数据目录为空时运行。

```sql
-- NaviRoom 数据库初始化
USE navi_room_db;

-- 房间表
CREATE TABLE IF NOT EXISTS rooms (
    room_id VARCHAR(120) NOT NULL PRIMARY KEY,
    floor VARCHAR(40) DEFAULT NULL,
    capacity INT DEFAULT NULL,
    room_type VARCHAR(80) DEFAULT NULL,
    equipment TEXT DEFAULT '[]',
    layout TEXT DEFAULT '[]',
    use_cases TEXT DEFAULT '[]',
    accessibility TEXT DEFAULT '[]',
    raw_description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_room_type (room_type),
    INDEX idx_capacity (capacity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 预订记录表
CREATE TABLE IF NOT EXISTS reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    room_id VARCHAR(120) NOT NULL,
    start_time VARCHAR(64) NOT NULL,
    end_time VARCHAR(64) NOT NULL,
    duration_minutes INT DEFAULT NULL,
    status VARCHAR(64) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_room_id (room_id),
    INDEX idx_start_time (start_time),
    CONSTRAINT fk_reservation_room
        FOREIGN KEY (room_id) REFERENCES rooms(room_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 数据集表
CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(120) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    CONSTRAINT fk_dataset_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户房间记录表
CREATE TABLE IF NOT EXISTS user_rooms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    room_id VARCHAR(120) NOT NULL,
    floor VARCHAR(40) DEFAULT NULL,
    capacity INT DEFAULT NULL,
    room_type VARCHAR(80) DEFAULT NULL,
    equipment TEXT DEFAULT '[]',
    layout TEXT DEFAULT '[]',
    use_cases TEXT DEFAULT '[]',
    accessibility TEXT DEFAULT '[]',
    raw_description TEXT DEFAULT '',
    INDEX idx_dataset_id (dataset_id),
    INDEX idx_room_id (room_id),
    CONSTRAINT fk_userroom_dataset
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 用户预订记录表
CREATE TABLE IF NOT EXISTS user_reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    room_id VARCHAR(120) NOT NULL,
    start_time VARCHAR(64) DEFAULT NULL,
    end_time VARCHAR(64) DEFAULT NULL,
    duration_minutes INT DEFAULT NULL,
    status VARCHAR(64) DEFAULT 'completed',
    INDEX idx_dataset_id (dataset_id),
    INDEX idx_room_id (room_id),
    CONSTRAINT fk_userreservation_dataset
        FOREIGN KEY (dataset_id) REFERENCES datasets(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

---

## 八、Nginx 配置

**文件**：`docker/nginx/nginx.conf`

```nginx
# ============================================================
# NaviRoom 生产环境 Nginx 反向代理
# ============================================================

upstream api_backend {
    # Docker Compose 内部 DNS 自动解析 api 服务
    server api:8000;
}

upstream frontend_server {
    server frontend:80;
}

# HTTP → HTTPS 重定向（可选，如启用 HTTPS 则取消注释）
# server {
#     listen 80;
#     server_name naviroom.cn www.naviroom.cn;
#     return 301 https://$host$request_uri;
# }

server {
    listen 80;
    server_name _;

    # 上传文件大小限制
    client_max_body_size 20M;

    # ==================== API 代理 ====================
    location /api/ {
        proxy_pass http://api_backend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # 超时配置
        proxy_read_timeout 60s;
        proxy_connect_timeout 10s;
    }

    location /recommend/ {
        proxy_pass http://api_backend/recommend/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 60s;
    }

    location /auth/ {
        proxy_pass http://api_backend/auth/;
        proxy_set_header Host $host;
    }

    location /data/ {
        proxy_pass http://api_backend/data/;
        proxy_set_header Host $host;
    }

    location /healthz {
        proxy_pass http://api_backend/healthz;
    }

    # ==================== 前端静态文件 ====================
    location / {
        proxy_pass http://frontend_server;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

# HTTPS 配置（生产环境启用）
# server {
#     listen 443 ssl http2;
#     server_name naviroom.cn www.naviroom.cn;
#
#     ssl_certificate     /etc/nginx/ssl/fullchain.crt;
#     ssl_certificate_key /etc/nginx/ssl/privkey.key;
#
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#     ssl_prefer_server_ciphers on;
#
#     client_max_body_size 20M;
#
#     # ...同上的 location 配置...
# }
```

---

## 九、操作手册

### 9.1 环境准备

```bash
# 1. 确认 Docker 已正确安装
docker --version
docker compose version

# 2. 进入项目目录
cd /path/to/NaviRoom

# 3. 创建 Docker 相关目录
mkdir -p docker/{api,frontend,nginx,data-pipeline,mysql/init}

# 4. 创建上述所有文件（Dockerfile、配置、脚本等）
#    ...按照第五至八节的内容创建各文件...

# 5. 配置环境变量
cp .env.docker .env
vim .env   # 修改密码和 API Key

# 6. 确认 .gitignore 排除了 .env
echo ".env" >> .gitignore

# 7. 生成 JWT 密钥（Linux/macOS）
# 如果没有 openssl，可以手动输入一个长随机字符串
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
```

### 9.2 首次部署

```bash
# Step 1: 启动 MySQL 数据库
docker compose up -d mysql

# 等待 MySQL 健康检查通过（约 30-40 秒）
docker compose ps mysql
# 状态应为 "healthy"

# Step 2: 构建并启动 API 服务
docker compose up -d --build api

# 等待 API 健康检查通过
docker compose logs -f api
# 看到 "Application startup complete" 后 Ctrl+C

# Step 3: 验证 API
curl http://localhost:8000/healthz
# 应返回: {"status":"ok"}

# Step 4: 导入初始数据
docker compose --profile init run --rm data-pipeline

# 或者导入带预订的 Kaggle 数据
PIPELINE_ROOMS=Data_processing/data/kaggle_university_room_dataset/rooms_clean.csv \
PIPELINE_RESERVATIONS=Data_processing/data/kaggle_university_room_dataset/reservations.csv \
PIPELINE_OUTPUT=Data_processing/output/kaggle_dataset.json \
docker compose --profile init run --rm data-pipeline

# Step 5: 构建并启动前端
docker compose up -d --build frontend

# Step 6: 验证全栈
curl http://localhost:3000/          # 前端首页
curl http://localhost:8000/healthz   # API 健康检查

# 测试推荐接口
curl -X POST http://localhost:8000/recommend/dataset \
  -H "Content-Type: application/json" \
  -d '{"user_query":"need a study room with screen","requirements":{"capacity":4}}'

# Step 7: 查看所有服务状态
docker compose ps
```

### 9.3 生产部署

```bash
# 1. 准备 TLS 证书
sudo mkdir -p /etc/letsencrypt/live/naviroom.cn
# 使用 certbot 获取证书
sudo certbot certonly --standalone -d naviroom.cn -d www.naviroom.cn

# 2. 更新 .env 中的 TLS 路径
echo "TLS_CERT_DIR=/etc/letsencrypt/live/naviroom.cn" >> .env

# 3. 使用生产配置启动
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. 验证
curl -I https://naviroom.cn/
curl https://naviroom.cn/healthz
```

### 9.4 日常运维

```bash
# ==================== 查看状态 ====================
docker compose ps                  # 所有服务状态
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# ==================== 查看日志 ====================
docker compose logs -f api         # 实时跟踪 API 日志
docker compose logs -f --tail=200 api   # 最近 200 行
docker compose logs --since 1h api      # 最近 1 小时
docker compose logs mysql | grep ERROR  # 搜索错误

# ==================== 重启服务 ====================
docker compose restart api         # 重启 API
docker compose restart nginx       # 重启 Nginx（使配置生效）

# ==================== 停止服务 ====================
docker compose stop                # 停止所有（保留数据）
docker compose down                # 停止并删除容器（保留数据卷）
docker compose down -v             # ⚠️ 停止并删除数据卷（数据库数据丢失！）

# ==================== 进入容器调试 ====================
docker compose exec api bash                            # API 容器 shell
docker compose exec api python -c "..."                 # 在容器内运行 Python
docker compose exec mysql mysql -u navi_user -p navi_room_db   # MySQL 交互式终端

# ==================== 清理 ====================
docker system prune -a            # 清理未使用的镜像、容器、网络
docker volume prune               # 清理未使用的数据卷
docker builder prune              # 清理构建缓存
```

### 9.5 更新部署

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 检查变更
git log --oneline -5

# 3. 重新构建并启动变更的服务
#    仅后端代码变更
docker compose up -d --build api

#    仅前端代码变更
docker compose up -d --build frontend

#    全量更新
docker compose up -d --build

# 4. 清理旧镜像
docker image prune -f

# 5. 验证
docker compose ps
curl http://localhost:8000/healthz
```

### 9.6 备份与恢复

```bash
# ==================== 数据库备份 ====================
# 导出 SQL
docker compose exec mysql mysqldump \
  -u root -p${MYSQL_ROOT_PASSWORD} \
  --single-transaction \
  --routines \
  --triggers \
  navi_room_db > backup_$(date +%Y%m%d_%H%M%S).sql

# 压缩备份
gzip backup_*.sql

# 保留最近 7 天的备份
find . -name "backup_*.sql.gz" -mtime +7 -delete

# 定时备份（添加到 crontab）
# 0 2 * * * cd /path/to/NaviRoom && docker compose exec -T mysql mysqldump -u root -p<PASSWORD> navi_room_db | gzip > backup_$(date +\%Y\%m\%d).sql.gz

# ==================== 数据库恢复 ====================
# ⚠️ 这会覆盖现有数据！
gunzip backup_20260710.sql.gz
docker compose exec -T mysql mysql -u root -p${MYSQL_ROOT_PASSWORD} navi_room_db < backup_20260710.sql

# ==================== 数据卷备份 ====================
# 备份 MySQL 数据卷
docker run --rm -v naviroom_mysql_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/mysql_data_backup.tar.gz -C /data .

# 恢复 MySQL 数据卷
docker run --rm -v naviroom_mysql_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/mysql_data_backup.tar.gz -C /data
```

### 9.7 水平扩展

```bash
# API 服务水平扩展至 3 个实例
docker compose up -d --scale api=3

# 查看所有 API 实例
docker compose ps api

# 注意：
# - 开发环境中端口 8000 只能绑定一个实例，需要移除 ports 配置或使用负载均衡
# - 生产环境中通过 nginx upstream 自动负载均衡
# - 可在 docker-compose.prod.yml 中指定 replicas: 3

# 在 nginx 配置中使用轮询负载均衡
# upstream api_backend {
#     server api:8000;   # Docker DNS 自动轮询解析
# }
```

### 9.8 回滚

```bash
# 方法 1: 使用 Git 回退代码后重建
git revert <commit-hash>
docker compose up -d --build

# 方法 2: 使用之前的镜像（需要先打 tag）
# 构建时给镜像打 tag
docker compose build api
docker tag naviroom-api:latest naviroom-api:v3.0.0

# 回滚时指定旧 tag
docker tag naviroom-api:v2.9.0 naviroom-api:latest
docker compose up -d api

# 方法 3: 重新构建指定 commit
git checkout <known-good-commit>
docker compose up -d --build
git checkout main
```

---

## 十、故障排查

### 10.1 MySQL 容器启动失败

```bash
# 查看日志
docker compose logs mysql

# 常见问题 1: 端口冲突
sudo lsof -i :3306
# 解决：修改 .env 中 MYSQL_PORT=3307

# 常见问题 2: 数据卷权限问题
sudo chown -R 999:999 /var/lib/docker/volumes/naviroom_mysql_data/

# 常见问题 3: 初始化脚本语法错误
# 检查 docker/mysql/init/*.sql 文件语法
# 如已创建过数据，需要清除卷后重建
docker compose down -v mysql
docker compose up -d mysql
```

### 10.2 API 容器启动失败

```bash
# 查看启动日志
docker compose logs api

# 常见问题 1: spaCy 模型未安装
docker compose exec api python -c "import spacy; print(spacy.load('en_core_web_sm'))"
# 解决：检查 Dockerfile 中 spacy download 步骤

# 常见问题 2: 数据库连接失败
docker compose exec api python -c "
import pymysql
conn = pymysql.connect(host='mysql', user='navi_user', password='...', database='navi_room_db')
print('OK')
"
# 解决：确认 mysql 服务 healthy，检查密码

# 常见问题 3: 端口冲突
sudo lsof -i :8000
# 解决：修改 .env 中 API_PORT=8001

# 常见问题 4: 代码修改未生效
# Dockerfile 中 COPY 层有缓存，强制重建
docker compose build --no-cache api
docker compose up -d api
```

### 10.3 前端构建失败

```bash
# 查看构建日志
docker compose build frontend

# 常见问题 1: pnpm-lock.yaml 不存在
# Dockerfile 中已使用 || pnpm install --no-frozen-lockfile 降级

# 常见问题 2: 源码路径错误
# 确认 "NaviRoom Homepage Upload Interface Version2" 目录存在
ls -la "NaviRoom Homepage Upload Interface Version2/"

# 常见问题 3: 内存不足
# Node.js 构建可能消耗 1GB+ 内存
docker system df
docker builder prune -f
```

### 10.4 Nginx 502 Bad Gateway

```bash
# 检查上游服务
docker compose ps api frontend
# 确保状态为 "healthy"

# 检查 Nginx 配置
docker compose exec nginx nginx -t

# 检查 Nginx 日志
docker compose logs nginx

# 测试内部连通性
docker compose exec nginx wget -qO- http://api:8000/healthz
docker compose exec nginx wget -qO- http://frontend:80/

# 常见问题：api 容器名解析失败
# 确保所有容器在同一网络
docker network inspect naviroom_naviroom-network
```

### 10.5 常用诊断命令合集

```bash
# 资源使用
docker stats                             # 所有容器 CPU/内存
docker compose top                       # 每个容器的进程

# 网络诊断
docker compose exec api ping mysql       # 容器间连通性
docker network inspect naviroom_naviroom-network | grep -A 5 "Containers"

# 卷诊断
docker volume ls | grep naviroom
docker volume inspect naviroom_mysql_data

# 镜像诊断
docker images | grep naviroom
docker compose images                    # 当前项目使用的镜像

# 完全重置
docker compose down -v                   # 删除容器+卷
docker system prune -a --volumes         # 清理一切
docker compose up -d --build             # 重新开始
```

---

## 十一、Docker vs Ansible 对比

| 维度 | Ansible（当前方案） | Docker（本指南方案） |
|---|---|---|
| **部署速度** | 首次 10-30 分钟 | 首次构建 3-5 分钟，启动 30 秒 |
| **环境一致性** | 依赖 Ubuntu 版本 | 容器内完全一致 |
| **跨平台** | 仅 Linux 目标机器 | Linux / macOS / Windows (WSL2) |
| **依赖管理** | 手动安装 Python 3.11、MySQL、Node.js | 每个镜像自包含 |
| **水平扩展** | 需额外配置 HAProxy/Nginx upstream | `--scale api=3` |
| **回滚** | 依赖 Ansible 回滚策略 | 切换镜像 tag |
| **学习曲线** | Ansible YAML + Jinja2 + SSH | Dockerfile + Compose YAML |
| **配置管理** | `group_vars/all.yml` | `.env` 文件 |
| **密钥管理** | Ansible Vault（可选） | `.env` 或 Docker Secrets |
| **监控集成** | 手动配置 | 原生支持 `docker stats`、Prometheus exporter |
| **CI/CD 集成** | 需安装 Ansible | GitHub Actions 等原生支持 |
| **适用场景** | 大批量物理服务器管理 | 单机或小集群服务部署 |

### 推荐策略

对于 NaviRoom 项目：

- **开发/测试环境**：纯 Docker Compose，简单高效
- **生产环境（单机）**：Docker Compose + nginx proxy
- **生产环境（多机）**：Docker Swarm / Kubernetes + 保留 Ansible 做宿主机管理

两个工具可以**混合使用**：Ansible 管理 Docker 宿主机的基础配置（防火墙、Docker 安装、内核参数），Docker Compose 管理应用生命周期。

---

## 十二、安全建议

### 12.1 密钥管理

```bash
# 不要将 .env 文件提交到 Git
echo ".env" >> .gitignore

# 生产环境使用 Docker Secrets（Swarm 模式）
# docker secret create naviroom_db_password ./db_password.txt
# docker secret create naviroom_secret_key ./secret_key.txt
```

### 12.2 容器安全

```yaml
# docker-compose 安全加固
services:
  api:
    # 以非 root 用户运行（Dockerfile 中已配置）
    # USER naviroom

    # 只读根文件系统（如适用）
    # read_only: true

    # 限制资源
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2'

    # 禁止提权
    security_opt:
      - no-new-privileges:true
```

### 12.3 网络安全

```bash
# 生产环境不暴露不必要的端口
# docker-compose.prod.yml 中:
#   api:    ports: []   (仅通过 nginx 访问)
#   frontend: ports: [] (仅通过 nginx 访问)
#   mysql:   ports: []  (仅容器内访问)

# 启用防火墙
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### 12.4 定期更新

```bash
# 更新基础镜像
docker compose pull mysql
docker compose build --no-cache api frontend nginx

# 扫描镜像漏洞（使用 Docker Scout 或 Trivy）
docker scout quickview naviroom-api:latest
```

---

## 十三、附录

### A. 快速启动脚本

```bash
#!/bin/bash
# quickstart.sh — NaviRoom 一键启动脚本
set -e

echo "=========================================="
echo "  NaviRoom Docker Quick Start"
echo "=========================================="

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "[INFO] 创建 .env 文件..."
    cp .env.docker .env
    echo "[WARN] 请编辑 .env 文件，修改默认密码和 API Key"
    echo "[WARN] 然后重新运行此脚本"
    exit 0
fi

# 启动服务
echo "[INFO] 启动 MySQL..."
docker compose up -d mysql
echo "[INFO] 等待 MySQL 就绪..."
until docker compose exec -T mysql mysqladmin ping -h localhost --silent 2>/dev/null; do
    sleep 2
done

echo "[INFO] 构建并启动 API..."
docker compose up -d --build api

echo "[INFO] 构建并启动前端..."
docker compose up -d --build frontend

echo ""
echo "=========================================="
echo "  NaviRoom 已启动!"
echo "  API:      http://localhost:8000"
echo "  前端:      http://localhost:3000"
echo "  API 文档:  http://localhost:8000/docs"
echo "=========================================="
```

### B. 开发环境额外配置

```yaml
# docker-compose.override.yml（开发环境，自动加载）
services:
  api:
    # 开发模式：代码热重载
    command: uvicorn recommendation.server:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      # 挂载源码目录，修改即时生效
      - ./recommendation:/app/recommendation
      - ./Data_processing:/app/Data_processing

  frontend:
    # 开发模式：Vite dev server + HMR
    build:
      target: builder
    command: pnpm run dev --host 0.0.0.0
    ports:
      - "5173:5173"
    volumes:
      - "./NaviRoom Homepage Upload Interface Version2/src:/app/src"
```

### C. 常用环境变量速查

| 变量 | 默认值 | 说明 |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | *必填* | MySQL root 密码 |
| `DB_NAME` | `navi_room_db` | 数据库名 |
| `DB_USER` | `navi_user` | 应用数据库用户 |
| `DB_PASSWORD` | *必填* | 应用数据库密码 |
| `API_PORT` | `8000` | API 对外端口 |
| `SECRET_KEY` | *必填* | JWT 签名密钥 |
| `RECO_SEMANTIC_MODE` | `hybrid` | 语义匹配模式 |
| `RECO_REQUIREMENTS_MODE` | `merge` | 需求提取模式 |
| `RECO_LLM_TOP_K` | `8` | LLM rerank 候选数 |
| `LLM_API_KEY` | 空 | DeepSeek API Key |
| `FRONTEND_PORT` | `3000` | 前端开发端口 |
| `TLS_CERT_DIR` | `./docker/nginx/certs` | TLS 证书目录 |

---

> **下一步**：创建所有文件后，执行 `bash quickstart.sh` 即可一键部署。如有问题，参考[第十节故障排查](#十故障排查)。

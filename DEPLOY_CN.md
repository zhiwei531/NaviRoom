# NaviRoom 国内服务器部署完整教程

> 适用于腾讯云/阿里云等国内 Ubuntu 服务器，已预判并解决所有网络问题。

---

## 全局问题清单：国内服务器会遇到的所有网络障碍

| 环节 | 被墙/慢的服务 | 国内替代方案 |
|------|-------------|------------|
| 安装 Docker | `get.docker.com` 被墙 | 阿里云/中科大 apt 镜像 |
| 拉取 Docker 镜像 | `docker.io` 极慢 | 配置 registry-mirrors |
| pip 安装 Python 包 | `pypi.org` 极慢 | 清华/阿里云 PyPI 镜像 |
| npm 安装前端依赖 | `npmjs.org` 极慢 | npmmirror.com（淘宝源） |
| spaCy 模型下载 | GitHub Releases 慢 | pip + 镜像优先，spacy download 兜底 |
| Git 克隆 | `github.com` SSH 端口可能被封 | 使用 HTTPS + 可选 ghproxy |
| DeepSeek API | `api.deepseek.com` | 国内服务，不受影响 ✅ |
| Let's Encrypt TLS | `acme-v02.api.letsencrypt.org` | 国内可用 ✅ |

**关键原则**：以上所有问题已在本教程和 Dockerfile 中预判处理，不需要部署时临时找方案。

---

## 第一步：服务器基础准备

### 1.1 安装 Docker（国内镜像）

```bash
# 卸载旧版本（如有）
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# 创建 keyrings 目录
sudo mkdir -p /etc/apt/keyrings

# 方式 A：阿里云镜像源（推荐，速度最快）
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 方式 B：中科大镜像源（备选）
# curl -fsSL https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu/gpg | \
#   sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
# echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
#   https://mirrors.ustc.edu.cn/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | \
#   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 免 sudo 运行
sudo usermod -aG docker $USER

# ⚠️ 必须退出重新登录才生效
exit
```

### 1.2 配置 Docker 镜像加速器

重新登录后执行：

```bash
# 创建配置目录
sudo mkdir -p /etc/docker

# 写入镜像加速器配置
sudo tee /etc/docker/daemon.json << 'EOF'
{
    "registry-mirrors": [
        "https://docker.1panel.live",
        "https://dockerpull.org",
        "https://docker.rainbond.cc"
    ],
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "50m",
        "max-file": "3"
    },
    "storage-driver": "overlay2"
}
EOF

# 重启 Docker 使配置生效
sudo systemctl daemon-reload
sudo systemctl restart docker

# 验证
docker info | grep -A 5 "Registry Mirrors"
```

### 1.3 验证 Docker 安装

```bash
docker --version        # 应显示 24.x+
docker compose version  # 应显示 v2.x+
docker run --rm hello-world  # 测试镜像拉取
```

---

## 第二步：获取代码

### 2.1 Git 克隆

```bash
# 方式 A：HTTPS 克隆到家目录（推荐，无需额外配置）
cd ~
git clone https://github.com/zhiwei531/NaviRoom.git NaviRoom-Docker
cd NaviRoom-Docker

# 方式 B：如果 GitHub 也被墙，用 ghproxy 镜像
# cd ~
# git clone https://ghproxy.com/https://github.com/zhiwei531/NaviRoom.git NaviRoom-Docker
# cd NaviRoom-Docker

# 方式 C：SSH 克隆（需要先配置 SSH Key 并添加到 GitHub）
# cd ~
# git clone git@github.com:zhiwei531/NaviRoom.git NaviRoom-Docker
# cd NaviRoom-Docker
```

### 2.2 如果克隆到 `/opt` 需要权限

```bash
# 方式一：给 /opt 赋权
sudo chown -R $USER:$USER /opt
git clone https://github.com/zhiwei531/NaviRoom.git /opt/NaviRoom-Docker

# 方式二：用 sudo 克隆再 chown
sudo git clone https://github.com/zhiwei531/NaviRoom.git /opt/NaviRoom-Docker
sudo chown -R $USER:$USER /opt/NaviRoom-Docker
```

---

## 第三步：配置环境变量

```bash
cd ~/NaviRoom-Docker

# 从模板创建 .env
cp .env.docker .env

# 自动生成安全密钥
python3 -c "
import secrets
print(f'SECRET_KEY={secrets.token_hex(32)}')
print(f'MYSQL_ROOT_PASSWORD={secrets.token_hex(16)}')
print(f'DB_PASSWORD={secrets.token_hex(16)}')
" > /tmp/naviroom_secrets.txt
source /tmp/naviroom_secrets.txt

# 写入 .env
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
sed -i "s/^MYSQL_ROOT_PASSWORD=.*/MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD/" .env
sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=$DB_PASSWORD/" .env

# 可选：配置 LLM API Key（DeepSeek）
# vi .env  # 编辑 LLM_API_KEY=sk-your-key-here
```

---

## 第四步：启动服务

### 4.1 启动 MySQL

```bash
# 启动数据库（首次会自动建表）
docker compose up -d mysql

# 等待 MySQL 健康检查通过
echo "等待 MySQL 就绪..."
until docker compose exec -T mysql mysqladmin ping -h localhost --silent 2>/dev/null; do
    echo -n "."
    sleep 2
done
echo " MySQL 已就绪"
```

### 4.2 构建并启动 API

```bash
# 构建 API 镜像（pip 已配置清华源，spaCy 模型走镜像优先）
docker compose up -d --build api

# 等待 API 就绪
echo "等待 API 就绪..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
        echo " API 已就绪"
        break
    fi
    echo -n "."
    sleep 3
done

# 验证
curl http://localhost:8000/healthz
```

### 4.3 导入数据

```bash
# 导入 DKU 数据集（无预定记录，纯房间数据）
docker compose --profile init run --rm data-pipeline

# 可选：导入 Kaggle 数据集（含预定记录，更丰富的推荐依据）
# PIPELINE_ROOMS=Data_processing/data/kaggle_university_room_dataset/rooms_clean.csv \
# PIPELINE_RESERVATIONS=Data_processing/data/kaggle_university_room_dataset/reservations.csv \
# PIPELINE_OUTPUT=Data_processing/output/kaggle_dataset.json \
# RECO_DATASET_PATH=Data_processing/output/kaggle_dataset.json \
# docker compose --profile init run --rm data-pipeline
```

### 4.4 构建并启动前端

```bash
# 构建前端（npm 已配置淘宝源）
docker compose up -d --build frontend

# 验证
curl -s -o /dev/null -w "前端 HTTP %{http_code}\n" http://localhost:3000/
```

### 4.5 验证全栈

```bash
# 全栈状态检查
docker compose ps

# 应看到：mysql (healthy), api (healthy), frontend (running)

# 推荐 API 功能测试
curl -X POST http://localhost:8000/recommend/dataset \
  -H "Content-Type: application/json" \
  -d '{"user_query":"need a quiet study room with screen for 3 people","requirements":{"capacity":3}}'

# 前端页面测试
curl -s -o /dev/null -w "前端: HTTP %{http_code}\n" http://localhost:3000/
```

---

## 第五步：对外开放访问

### 5.1 开放防火墙

```bash
# 腾讯云需要在"安全组"中额外开放端口！
# 路径：云服务器 → 安全组 → 添加规则

sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 3000/tcp  # 前端（开发/测试阶段）
sudo ufw enable
```

### 5.2 启动生产模式（Nginx 反向代理）

```bash
# 生产模式：前端 + API 统一走 Nginx 80 端口
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 5.3 配置 HTTPS（可选，需要域名）

```bash
# 1. 确保域名 DNS 指向本服务器 IP
# 2. 安装 certbot
sudo apt install -y certbot

# 3. 获取证书（先停掉占用 80 端口的 nginx）
docker compose stop nginx
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com
docker compose start nginx

# 4. 编辑 docker/nginx/nginx.conf，取消 HTTPS server block 注释
# 5. 重启 nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart nginx

# 6. 设置证书自动续期
sudo crontab -l > /tmp/crontab
echo "0 3 * * * certbot renew --quiet --pre-hook 'docker compose -f ~/NaviRoom-Docker/docker-compose.yml -f ~/NaviRoom-Docker/docker-compose.prod.yml stop nginx' --post-hook 'docker compose -f ~/NaviRoom-Docker/docker-compose.yml -f ~/NaviRoom-Docker/docker-compose.prod.yml start nginx'" >> /tmp/crontab
sudo crontab /tmp/crontab
```

---

## 日常运维命令

```bash
# ===== 查看状态 =====
docker compose ps                          # 所有服务状态
docker compose logs -f api --tail=50       # API 实时日志
docker compose logs mysql | grep ERROR     # 数据库错误日志

# ===== 重启服务 =====
docker compose restart api                 # 重启 API
docker compose up -d --build api           # 重新构建并启动 API

# ===== 更新代码 =====
cd ~/NaviRoom-Docker
git pull origin main
docker compose up -d --build               # 全量重建

# ===== 备份数据库 =====
docker compose exec mysql mysqldump \
  -u root -p"$(grep MYSQL_ROOT_PASSWORD .env | cut -d= -f2)" \
  --single-transaction navi_room_db | gzip > backup_$(date +%Y%m%d_%H%M).sql.gz

# ===== 停止服务 =====
docker compose down                        # 停止（保留数据卷）
docker compose down -v                     # ⚠️ 停止并删除数据卷
```

---

## 故障排查

| 症状 | 原因 | 解决 |
|------|------|------|
| `docker compose` 报 command not found | Docker Compose 插件没装 | `sudo apt install docker-compose-plugin` |
| 拉取 Docker 镜像超时 | registry mirror 未配置 | 重新执行 1.2 节 |
| `pip install` 超时 | 未使用 ARG 默认走清华源 | Dockerfile 中 `PIP_INDEX` 默认值已配置 |
| `npm ci` 超时 | 未走淘宝源 | Dockerfile 中 `NPM_REGISTRY` 默认值已配置 |
| spaCy 模型下载失败 | GitHub 慢 | Dockerfile 已配置 pip+镜像优先策略 |
| MySQL 端口冲突 | 宿主机已有 MySQL | 修改 .env 中 `MYSQL_PORT=3307` |
| 端口 3000/8000 不通 | 腾讯云安全组拦截 | 在腾讯云控制台开放端口 |
| 502 Bad Gateway | API 服务未就绪 | `docker compose logs api` 查看错误 |
| 内存不足 | 构建消耗大量内存 | 临时增加 swap：`sudo fallocate -l 2G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile` |

---

## 部署架构总结

```
外部用户
    │
    ▼
腾讯云安全组（开放 80/443）
    │
    ▼
Nginx 容器 (:80)
    ├─ / → 前端静态页面
    ├─ /api/* → API 容器 :8000
    ├─ /recommend/* → API 容器 :8000
    └─ /healthz → API 容器 :8000
    │
    ▼
API 容器 (FastAPI + uvicorn :8000)
    │
    ├─ RoomParser (spaCy NLP) 解析房间数据
    ├─ DeepSeek LLM (api.deepseek.com) 语义匹配
    └─ 6阶段推荐管线
    │
    ▼
MySQL 容器 (:3306, 数据卷持久化)
    └─ named volume: mysql_data
```

**所有国内网络问题已在 Dockerfile 和 deploy.sh 中预判处理**，服务器上只需按上述步骤执行，无需额外配置。

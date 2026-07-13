#!/bin/bash
# ============================================================
# NaviRoom Docker 一键部署脚本
# 在目标服务器上执行此脚本
# ============================================================
set -e

echo "=========================================="
echo "  NaviRoom Docker Deploy"
echo "=========================================="
echo ""

# ---- 检查 Docker ----
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker 未安装。请先执行:"
    echo "  curl -fsSL https://get.docker.com | sudo sh"
    echo "  sudo usermod -aG docker \$USER"
    echo "  重新登录后再运行此脚本"
    exit 1
fi
echo "[OK] Docker $(docker --version | cut -d' ' -f3 | cut -d',' -f1)"

# ---- 配置环境变量 ----
if [ ! -f .env ]; then
    echo ""
    echo "[SETUP] 创建 .env 文件..."
    cp .env.docker .env

    # 生成随机密钥
    SECRET=$(openssl rand -hex 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(32))")
    MYSQL_ROOT_PW=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")
    MYSQL_USER_PW=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))")

    # 替换默认值
    sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET/" .env
    sed -i "s/^MYSQL_ROOT_PASSWORD=.*/MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PW/" .env
    sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=$MYSQL_USER_PW/" .env

    echo "[WARN] 自动生成了密码，保存在 .env 文件中"
    echo "[WARN] 如需使用 LLM 功能，请编辑 .env 填入 LLM_API_KEY"
else
    echo "[OK] .env 已存在"
fi

# ---- 启动服务 ----
echo ""
echo "=========================================="
echo "  Step 1/4: 启动 MySQL"
echo "=========================================="
docker compose up -d mysql
echo "[INFO] 等待 MySQL 就绪..."
until docker compose exec -T mysql mysqladmin ping -h localhost --silent 2>/dev/null; do
    echo -n "."
    sleep 2
done
echo ""
echo "[OK] MySQL 已就绪"

echo ""
echo "=========================================="
echo "  Step 2/4: 构建并启动 API"
echo "=========================================="
docker compose up -d --build api
echo "[INFO] 等待 API 就绪..."
sleep 5
for i in $(seq 1 15); do
    if curl -sf http://localhost:${API_PORT:-8000}/healthz > /dev/null 2>&1; then
        echo "[OK] API 已就绪"
        break
    fi
    echo -n "."
    sleep 2
done
curl -s http://localhost:${API_PORT:-8000}/healthz

echo ""
echo "=========================================="
echo "  Step 3/4: 导入初始数据"
echo "=========================================="
if [ -f Data_processing/output/dku_dataset.json ]; then
    echo "[SKIP] 数据集已存在: Data_processing/output/dku_dataset.json"
else
    echo "[RUN] 运行数据管道..."
    docker compose --profile init run --rm data-pipeline
    echo "[OK] 数据导入完成"
fi

echo ""
echo "=========================================="
echo "  Step 4/4: 构建并启动前端"
echo "=========================================="
docker compose up -d --build frontend
echo "[OK] 前端已启动"

# ---- 验证 ----
echo ""
echo "=========================================="
echo "  部署验证"
echo "=========================================="
echo ""
echo "健康检查:"
curl -s http://localhost:${API_PORT:-8000}/healthz | python3 -m json.tool 2>/dev/null || curl -s http://localhost:${API_PORT:-8000}/healthz
echo ""

echo "推荐 API 测试:"
curl -s -X POST http://localhost:${API_PORT:-8000}/recommend/dataset \
  -H "Content-Type: application/json" \
  -d '{"user_query":"need a quiet study room with screen for 3 people","requirements":{"capacity":3}}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  返回 {len(d)} 条推荐'); [print(f'  {i+1}. {r[\"room_id\"]} — {r[\"final_score\"]:.0%}') for i,r in enumerate(d[:5])]" 2>/dev/null || \
  curl -s -X POST http://localhost:${API_PORT:-8000}/recommend/dataset \
    -H "Content-Type: application/json" \
    -d '{"user_query":"need a quiet study room with screen for 3 people","requirements":{"capacity":3}}'

echo ""
echo "前端页面:"
curl -s -o /dev/null -w "  HTTP %{http_code} — http://localhost:${FRONTEND_PORT:-3000}/" http://localhost:${FRONTEND_PORT:-3000}/
echo ""

echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "  访问地址:"
echo "    前端:  http://localhost:${FRONTEND_PORT:-3000}"
echo "    API:   http://localhost:${API_PORT:-8000}"
echo "    文档:  http://localhost:${API_PORT:-8000}/docs"
echo ""
echo "  常用命令:"
echo "    docker compose ps                 查看服务状态"
echo "    docker compose logs -f api        查看 API 日志"
echo "    docker compose restart api        重启 API"
echo "    docker compose down               停止所有服务"
echo ""

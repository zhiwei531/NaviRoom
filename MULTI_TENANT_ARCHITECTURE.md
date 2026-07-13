# NaviRoom 多租户架构与生产部署方案

> **背景**：前两份文档（`DOCKER_DEPLOY.md`、`DEPLOYMENT_IMPROVEMENT_PLAN.md`）解决了"怎么部署"的问题。本文档回答"部署出去后，怎么让多个客户/机构同时使用同一个 NaviRoom 实例"。
>
> **核心结论**：Docker 基础设施层已经为生产环境做好了准备。但要真正上线服务多个客户，应用层需要引入多租户架构。好消息是——代码库中已经埋下了多租户的种子。

---

## 目录

1. [先回答核心问题](#一先回答核心问题)
2. [代码库现状：多租户的"胚胎"](#二代码库现状多租户的胚胎)
3. [基础设施层：Docker 已经准备好了](#三基础设施层docker-已经准备好了)
4. [应用层：多租户架构设计](#四应用层多租户架构设计)
5. [租户数据隔离策略](#五租户数据隔离策略)
6. [API 层改造：租户上下文注入](#六api-层改造租户上下文注入)
7. [推荐引擎的多租户改造](#七推荐引擎的多租户改造)
8. [多租户 Docker 部署架构](#八多租户-docker-部署架构)
9. [租户生命周期管理](#九租户生命周期管理)
10. [实施路线图](#十实施路线图)

---

## 一、先回答核心问题

### "Docker 部署后续也支持真正上线吗？"

**支持。** 前两份文档中的 Docker Compose 方案从一开始就是按生产标准设计的：

| 生产特性 | 是否已规划 |
|---------|:---:|
| 多副本 API（水平扩展） | ✅ `docker-compose.prod.yml` `replicas: 2` |
| HTTPS + TLS 终结 | ✅ Nginx 443 + Let's Encrypt |
| 健康检查 + 自动重启 | ✅ Docker HEALTHCHECK + `restart: unless-stopped` |
| 数据库持久化 | ✅ named volume `mysql_data` |
| 资源限制 | ✅ `deploy.resources.limits` |
| 日志轮转 | ✅ `json-file` driver + max-size/max-file |
| 自动备份 | ✅ `scripts/backup.sh` + crontab |
| 零停机更新 | ✅ `docker compose up -d --build` 滚动替换 |

### "不只是本地页面吧？"

**不只是。** 但"多租户"这个能力，当前代码库**只做了一半**：

- ✅ **数据库层**：`User` → `Dataset` → `RoomRecord`/`ReservationRecord` 的租户隔离模型已经建好
- ✅ **认证层**：JWT token 生成/验证已实现
- ❌ **API 层**：所有端点都是公开的，没有注入租户上下文
- ❌ **推荐层**：推荐引擎不知道"租户"的存在，只加载一个全局数据集
- ❌ **前端层**：未与认证系统对接

**总结**：Docker 提供的是"壳"（能跑在生产环境），多租户提供的是"魂"（能服务多个客户）。两者需要配合。

---

## 二、代码库现状：多租户的"胚胎"

### 2.1 已经建好的数据模型

`auth_store.py` 中有一条完整的数据归属链：

```
User (用户/租户管理员)
  │  id, username, password_hash
  │
  └── Dataset (每个用户可上传多个数据集)
        │  id, user_id → users.id, name
        │
        ├── RoomRecord (数据集下的房间)
        │     id, dataset_id, room_id, capacity, equipment, ...
        │
        └── ReservationRecord (数据集下的预订)
              id, dataset_id, room_id, start_time, end_time, ...
```

这意味着数据库层面已经支持：

- 用户 A 上传 DKU 图书馆数据 → `dataset_id=1`
- 用户 B 上传公司会议室数据 → `dataset_id=2`
- 两个数据集完全隔离，互不可见

### 2.2 已经实现但未使用的认证

```python
# auth_store.py — JWT 已经写好
create_access_token(data={"sub": username, "user_id": user.id})
decode_access_token(token)  # → {"sub": "alice", "user_id": 1, "exp": ...}

# server.py — 但目前没有在任何路由中使用！
@app.post("/recommend/upload")  # 无 Depends(get_current_user)
async def recommend_upload(...):  # 任何人都能调
```

### 2.3 缺口：推荐引擎是"单租户思维"

```python
# server.py L105-113 — 回退到全局数据集，不考虑当前用户
dataset_path = os.getenv("RECO_DATASET_PATH", "Data_processing/output/dku_dataset.json")
dataset = _load_dataset(dataset_path)  # 所有人共享同一个文件
```

---

## 三、基础设施层：Docker 已经准备好了

### 3.1 生产拓扑图

```
                          ┌──────────────┐
                          │   Cloudflare  │  DNS + DDoS Protection
                          │   (可选)      │
                          └──────┬───────┘
                                 │
                          ┌──────▼───────┐
                          │   Nginx      │  TLS 终结 + 限流 + 静态资源
                          │   :443       │
                          └──┬──────┬───┘
                             │      │
                   /api/*    │      │  /assets/*, SPA
                             │      │
                   ┌─────────▼─┐  ┌─▼──────────┐
                   │ API (x2)  │  │  Frontend   │
                   │ :8000     │  │  :80        │
                   │           │  │             │
                   │ ┌───────┐ │  └────────────┘
                   │ │JWT    │ │
                   │ │Auth   │ │
                   │ └───────┘ │
                   └──┬────┬───┘
                      │    │
            ┌─────────▼┐   └──────────┐
            │  MySQL   │              │
            │  :3306   │    外部 API   │
            │          │    DeepSeek  │
            │ ┌──────┐ │    (LLM)    │
            │ │租户数据│ │              │
            │ │隔离   │ │              │
            │ └──────┘ │              │
            └──────────┘              │
                                      │
     ┌────────────────────────────────┘
     ▼
┌─────────────┐     ┌─────────────────┐
│ 定时备份     │     │  监控 & 告警     │
│ (crontab)  │     │  (Prometheus    │
│             │     │   + Grafana)    │
└─────────────┘     └─────────────────┘
```

### 3.2 生产环境需要补充的基础设施

| 组件 | 作用 | 实施方式 |
|------|------|---------|
| **MySQL 主从** | 读写分离，防止单点故障 | `mysql:8.0` 主库 + `mysql:8.0` 从库 |
| **Redis** | Session 缓存、限流计数器 | `redis:7-alpine` + 密码认证 |
| **Prometheus** | 采集 API 指标（QPS、延迟、错误率） | `prom/prometheus` + FastAPI `prometheus_fastapi_instrumentator` |
| **Grafana** | 可视化监控面板 | `grafana/grafana` + MySQL/Prometheus 数据源 |
| **Watchtower** | 自动拉取并更新 Docker 镜像 | `containrrr/watchtower`（可选，推荐手动控制） |
| **Certbot** | TLS 证书自动续期 | `certbot/certbot` + cron |

### 3.3 补充后的 docker-compose.prod.yml

```yaml
# 在现有基础上增加
services:
  mysql-slave:
    image: mysql:8.0
    # 配置为 MySQL 主库的只读副本
    # 推荐引擎的只读查询走从库

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data

  prometheus:
    image: prom/prometheus
    volumes:
      - ./docker/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    ports:
      - "3001:3000"  # Grafana 自己的 UI（内部使用）
```

---

## 四、应用层：多租户架构设计

### 4.1 多租户是什么

想象三个客户同时使用 NaviRoom：

| 租户 | 机构 | 房间数据 | 用户 | 数据集 |
|------|------|---------|------|--------|
| Tenant A | 昆山杜克大学 | DKU 图书馆自习室 | 3000+ 学生 | 50 间房 + 2000 条预订 |
| Tenant B | 某科技公司 | 办公室会议室 | 500 员工 | 20 间会议室 + 1000 条预订 |
| Tenant C | 某共享办公空间 | 热桌 + 私人隔间 | 100 会员 | 30 间 + 500 条预订 |

**核心要求**：
1. Tenant A 的用户看不到 Tenant B 的房间
2. Tenant A 的推荐只基于 Tenant A 的历史数据（行为评分）
3. Tenant B 即使数据量小（冷启动），推荐质量也不能崩
4. 每个租户可以使用自己的 LLM API Key（费用独立结算）

### 4.2 推荐的租户模型

当前 `auth_store.py` 中的 `User → Dataset` 模型是**以用户为中心**的——一个用户上传数据。生产环境应扩展为**以组织为中心**：

```
Organization (租户/机构)
  │  id, name, slug, plan (free/pro/enterprise)
  │  llm_api_key (每个租户可用自己的 Key)
  │  reco_config (租户级推荐配置)
  │
  ├── User (多个用户属于一个组织)
  │     id, org_id, username, password_hash, role (admin/member)
  │
  └── Dataset (多个数据集属于一个组织)
        id, org_id, name, created_at
        │
        ├── RoomRecord
        └── ReservationRecord
```

### 4.3 需新增的表

```sql
-- 组织（租户）
CREATE TABLE organizations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    slug VARCHAR(60) NOT NULL UNIQUE,       -- URL 标识: dku, acme-corp
    plan ENUM('free', 'pro', 'enterprise') DEFAULT 'free',
    llm_api_key VARCHAR(255) DEFAULT NULL,  -- 租户自己的 LLM Key（可选）
    reco_semantic_mode VARCHAR(20) DEFAULT 'hybrid',
    max_rooms INT DEFAULT 500,              -- 配额
    max_users INT DEFAULT 10,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户表增加 org_id
ALTER TABLE users ADD COLUMN org_id INT;
ALTER TABLE users ADD FOREIGN KEY (org_id) REFERENCES organizations(id);
ALTER TABLE users ADD COLUMN role ENUM('admin', 'member') DEFAULT 'member';

-- 数据集表 user_id 改为 org_id（或同时保留）
ALTER TABLE datasets ADD COLUMN org_id INT;
ALTER TABLE datasets ADD FOREIGN KEY (org_id) REFERENCES organizations(id);
```

---

## 五、租户数据隔离策略

三种主流策略对比：

### 策略对比

| 策略 | 原理 | 隔离强度 | 成本 | NaviRoom 适用性 |
|------|------|:---:|------|:---:|
| **共享表 + tenant_id** | 所有租户数据在同一张表，用 `org_id` 列区分 | ⭐⭐ | 最低 | ✅ **推荐** |
| **Schema per tenant** | 每个租户一个 PostgreSQL Schema | ⭐⭐⭐ | 中 | ❌ MySQL 的 Schema ≠ PostgreSQL |
| **Database per tenant** | 每个租户一个独立数据库 | ⭐⭐⭐⭐ | 最高 | ⚠️ 仅 enterprise 版需要 |

### 推荐方案：共享表 + tenant_id 列

NaviRoom 的数据规模不大（单个租户通常 < 1000 间房），共享表足够：

```python
# 所有查询自动带 org_id 过滤
# ✅ 开发简单，一个连接池
# ✅ 可以跨租户做全局分析（如总使用率统计）
# ⚠️ 必须在应用层保证绝不漏加 org_id 过滤

# 反面例子（危险！）
rooms = session.execute(select(RoomRecord)).all()  # 返回所有租户的数据

# 正面例子
rooms = session.execute(
    select(RoomRecord).where(RoomRecord.dataset.has(org_id=current_org_id))
).all()
```

### 隔离保障机制

```python
# 使用 FastAPI Dependency 强制注入租户上下文，杜绝遗漏
from fastapi import Depends

async def get_current_org(
    token: str = Depends(oauth2_scheme),
    session = Depends(get_db)
) -> Organization:
    payload = decode_access_token(token)
    org = session.get(Organization, payload["org_id"])
    if not org or not org.is_active:
        raise HTTPException(status_code=403, detail="Tenant not active")
    return org

# 所有业务路由自动获得租户上下文
@app.post("/recommend/upload")
async def recommend_upload(
    org: Organization = Depends(get_current_org),  # ← 强制注入
    ...
):
    # org.id 就是当前租户 ID，后续所有操作都限定在这个范围
```

---

## 六、API 层改造：租户上下文注入

### 6.1 改造前的 server.py 路由

```
当前：所有端点公开访问，无租户概念
  GET  /healthz                             → 公开
  POST /recommend/upload                    → 公开（任何人上传 CSV）
  POST /recommend/payload                   → 公开
  POST /recommend/dataset                   → 公开
```

### 6.2 改造后的路由结构

```
公开端点（无需认证）：
  GET  /healthz                             → 存活检查
  GET  /api/health/ready                    → 就绪检查
  POST /api/auth/register                   → 注册（创建 org + admin user）
  POST /api/auth/login                      → 登录（返回 JWT）

认证端点（需要 JWT）：
  GET  /api/tenant/datasets                 → 获取当前租户的所有数据集
  POST /api/tenant/datasets/upload          → 上传新数据集（CSV/文本）
  POST /api/tenant/recommend                → 基于租户数据推荐
  POST /api/tenant/recommend/dataset/{id}   → 基于指定数据集推荐
  GET  /api/tenant/rooms                    → 租户的房间列表
  GET  /api/tenant/reservations             → 租户的预订列表

管理端点（需要 admin role）：
  PUT  /api/tenant/settings                 → 修改租户配置（LLM Key 等）
  POST /api/tenant/users/invite             → 邀请成员
  GET  /api/tenant/usage                    → 查看使用统计
```

### 6.3 改造代码示例

```python
# server.py — 多租户版关键路由

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from recommendation.auth_store import (
    decode_access_token, get_password_hash, verify_password,
    SessionLocal, User, Organization, Dataset, RoomRecord
)

security = HTTPBearer()

# ---- 依赖注入：获取当前用户 ----
async def get_current_user(
    token: str = Depends(security),
) -> User:
    payload = decode_access_token(token.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    with SessionLocal() as session:
        user = session.get(User, payload["user_id"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user

# ---- 依赖注入：获取当前租户 ----
async def get_current_org(
    user: User = Depends(get_current_user),
) -> Organization:
    with SessionLocal() as session:
        org = session.get(Organization, user.org_id)
        if not org or not org.is_active:
            raise HTTPException(status_code=403, detail="Organization not active")
        return org

# ---- 注册（创建租户 + 管理员） ----
@app.post("/api/auth/register")
def register(username: str, password: str, org_name: str):
    with SessionLocal() as session:
        # 创建组织
        org = Organization(name=org_name, slug=org_name.lower().replace(" ", "-"))
        session.add(org)
        session.flush()

        # 创建管理员
        user = User(
            username=username,
            password_hash=get_password_hash(password),
            org_id=org.id,
            role="admin",
        )
        session.add(user)
        session.commit()

        token = create_access_token({"user_id": user.id, "org_id": org.id})
        return {"token": token, "org_slug": org.slug}

# ---- 租户内推荐 ----
@app.post("/api/tenant/recommend")
def tenant_recommend(
    req: PayloadRequest,
    org: Organization = Depends(get_current_org),
):
    """只推荐当前租户数据内的房间"""
    with SessionLocal() as session:
        # 从数据库加载租户的房间和预订（而非全局 JSON 文件）
        rooms = session.execute(
            select(RoomRecord).where(
                RoomRecord.dataset.has(org_id=org.id)
            )
        ).scalars().all()
        reservations = []  # 同理

    payload = {
        "user_query": req.user_query,
        "requirements": req.requirements,
        "rooms": [_room_to_dict(r) for r in rooms],
        "reservations": reservations,
    }
    return recommend_rooms_payload(payload)
```

---

## 七、推荐引擎的多租户改造

### 7.1 当前问题

推荐引擎有三个地方是"全局思维"：

1. `recommend_top5()` 直接从 `RecommendInput` 接收 rooms/reservations —— **这个没问题**（只要上游传入租户限定后的数据）
2. `_behavior_model()` 中的行为评分 —— **需要确保预订数据只来自当前租户**
3. `semantic_match()` 中 LLM reranking —— **每个租户可以用自己的 API Key**

### 7.2 改造方案

```python
# engine.py — 增加租户参数
def recommend_top5(inp: RecommendInput, org_id: int | None = None) -> list[ScoredRoom]:
    # ... 现有逻辑 ...

# api.py — 确保只传入租户数据
def recommend_for_tenant(
    user_query: str,
    requirements: UserRequirements,
    org_id: int,
) -> list[ScoredRoom]:
    # 从数据库加载该租户的 rooms + reservations
    rooms = load_rooms_for_org(org_id)
    reservations = load_reservations_for_org(org_id)

    inp = RecommendInput(
        user_query=user_query,
        requirements=requirements,
        rooms=rooms,
        reservations=reservations,
    )
    return recommend_top5(inp, org_id=org_id)
```

### 7.3 租户级 LLM 隔离

```python
# llm.py — 支持按租户使用不同的 API Key
def llm_score_relevance(
    *, user_query, room_features,
    org_llm_api_key: str | None = None,  # ← 租户自己的 Key
    cfg=None,
):
    api_key = org_llm_api_key or settings.llm_api_key  # 优先租户 Key
    # ... 调用 LLM ...
```

### 7.4 冷启动在多租户下的特殊处理

多租户场景中，新注册的租户必然没有历史数据：

```python
# engine.py — 已有的冷启动支持，在多租户下自动生效
def _score_weights(requirements, history_count):
    if history_count <= 0:
        # 无历史 → 语义匹配占主导
        return 0.55, 0.35, 0.10  # sem, rule, behavior
```

这意味着新租户 A（刚上传数据，无历史预订）和老租户 B（有 5000 条预订）走的是**同一套引擎但自动适配不同权重**，不需要额外的"冷启动模式"开关。

---

## 八、多租户 Docker 部署架构

### 8.1 最终生产拓扑

```
                          Internet
                             │
                    ┌────────▼────────┐
                    │  Cloudflare DNS │  (可选) DDoS 防护 + CDN
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │        VM / 云主机           │
              │  Ubuntu 22.04 / Debian 12   │
              │                             │
              │  ┌───────────────────────┐  │
              │  │  Nginx (TLS 终结)      │  │
              │  │  limit_req: 10r/s     │  │
              │  └───┬─────────────┬─────┘  │
              │      │             │        │
              │  ┌───▼────┐  ┌────▼─────┐  │
              │  │ API #1 │  │ API #2   │  │
              │  │ (JWT)  │  │ (JWT)    │  │
              │  └───┬────┘  └────┬─────┘  │
              │      │            │         │
              │      └─────┬──────┘         │
              │            │                │
              │  ┌─────────▼──────────┐    │
              │  │     MySQL 8.0      │    │
              │  │  ┌──────────────┐  │    │
              │  │  │ organizations │  │    │
              │  │  │ users         │  │    │
              │  │  │ datasets      │  │    │
              │  │  │ rooms         │  │    │
              │  │  │ reservations  │  │    │
              │  │  └──────────────┘  │    │
              │  └────────────────────┘    │
              │                             │
              │  ┌──────────┐ ┌──────────┐ │
              │  │  Backups │ │ 日志收集  │ │
              │  │  (cron)  │ │ (loguru) │ │
              │  └──────────┘ └──────────┘ │
              └─────────────────────────────┘
```

### 8.2 最小成本生产方案

| 资源 | 规格 | 月费（参考） |
|------|------|:---:|
| 云主机 1 台 | 4 核 8 GB，100 GB SSD | ¥200-400 |
| 数据库 | MySQL 8.0（同主机 Docker） | ¥0 |
| CDN + DNS | Cloudflare Free | ¥0 |
| LLM API | DeepSeek API（按量） | ¥50-200 |
| TLS 证书 | Let's Encrypt（自动续） | ¥0 |
| **合计** | | **¥250-600/月** |

> 对比：SaaS 化后如果按每个租户 ¥99/月 收费，3-5 个客户即可覆盖成本。

---

## 九、租户生命周期管理

### 9.1 租户状态流转

```
注册 (free trial)
  │  is_active=true, plan=free, max_rooms=500
  │
  ├── 活跃使用
  │     │
  │     ├── 升级到 pro → plan=pro, max_rooms=5000
  │     │
  │     └── 过期/欠费 → is_active=false
  │           │
  │           ├── 续费 → is_active=true
  │           │
  │           └── 超过保留期 → 数据归档 → 彻底删除
  │
  └── 主动注销 → 数据导出 → 30天后删除
```

### 9.2 租户管理 CLI

```bash
# 通过 CLI 管理租户（参考 recommendation/cli.py 的模式）
python -m recommendation.cli tenant create \
    --name "DKU Library" \
    --slug "dku" \
    --plan "pro"

python -m recommendation.cli tenant stats --slug dku
# → {"rooms": 50, "reservations": 2000, "users": 15, "active_since": "2026-01-15"}

python -m recommendation.cli tenant suspend --slug dku
# → is_active = false, API 返回 403
```

---

## 十、实施路线图

```
Phase 1: 单租户完善（2 周）          Phase 2: 多租户基础（3 周）        Phase 3: 生产上线（2 周）
─────────────────────────────────────────────────────────────────────────────────────
□ 配置系统改造 (config.py)           □ 新增 organizations 表            □ Prometheus + Grafana 监控
□ 日志系统升级 (loguru)              □ users/datasets 增加 org_id      □ MySQL 主从/备份验证
□ 健康检查增强                       □ JWT 中间件注入租户上下文          □ 负载测试（100 并发租户）
□ systemd/Nginx 安全加固             □ API 路由改为租户隔离             □ TLS 证书 + DNS 配置
□ Docker Compose 本地跑通            □ 推荐引擎租户化                   □ 灰度上线（先邀请 2-3 个客户）
□ backup.sh 自动备份                 □ 前端登录/注册页对接              □ 文档：API 文档、租户上手指南
```

---

## 总结

| 问题 | 答案 |
|------|------|
| Docker 能上生产吗？ | ✅ 能。健康检查、TLS、限流、备份、滚动更新都已规划 |
| 能支持多租户吗？ | ⚠️ 基础设施能，应用层需要改造。但代码库已有数据模型基础 |
| 改造成本大吗？ | 中等。核心推荐引擎无需大改（它本来就是"输入房间+预订→输出推荐"的纯函数），主要工作是 API 层加 JWT 中间件和增加 organizations 表 |
| 什么时候能上线？ | 单租户版（一个客户）：1-2 周。多租户版（多个客户）：额外 3-4 周 |

> **关键洞察**：当前的推荐引擎设计有一个天然优势——它是**无状态的纯函数**（输入 rooms/reservations → 输出推荐列表）。多租户支持只需要在**数据输入侧**做隔离，推荐算法本身不需要感知"租户"这个概念。这让改造的复杂度大幅降低。

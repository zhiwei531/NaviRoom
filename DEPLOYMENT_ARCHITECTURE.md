# AI Marketing Matrix — 部署架构与逻辑详解

> **项目定位**：小红书（XHS）多账号 AI 营销矩阵自动化平台。支持 AI 内容生成、Chrome 浏览器自动化发布、评论监控与自动回复、关键词侦察、知识库 RAG 检索。

---

## 目录

1. [项目总览](#1-项目总览)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [后端架构详解](#4-后端架构详解)
5. [前端架构详解](#5-前端架构详解)
6. [Chrome 浏览器池机制](#6-chrome-浏览器池机制)
7. [部署逻辑详解](#7-部署逻辑详解)
8. [服务启动与控制](#8-服务启动与控制)
9. [数据流与关键业务流程](#9-数据流与关键业务流程)
10. [配置文件说明](#10-配置文件说明)
11. [安全注意事项](#11-安全注意事项)
12. [运维与监控](#12-运维与监控)

---

## 1. 项目总览

### 1.1 核心功能模块

| 模块 | 功能 | 驱动方式 |
|------|------|----------|
| **AI 写作 (Compose)** | 输入 Prompt → LLM 生成笔记草稿 → 人工审核确认 | LLM (DeepSeek) |
| **定时发帖 (daily_post)** | 自动选取就绪草稿，通过 Chrome 发布到 XHS | Chrome + browser-use Agent |
| **评论轮询 (poll_inbox)** | 定时扫描已发布笔记的新评论，写入收件箱 | Chrome + browser-use Agent |
| **自动回复 (auto_reply)** | 对收件箱中的评论生成 AI 回复并自动发送 | LLM + Chrome |
| **关键词侦察 (scout_keywords)** | 搜索 XHS 关键词，采集热门帖子 | Chrome + browser-use Agent |
| **每日数据反馈 (daily_feedback)** | 聚合当日运营数据，生成 LLM 日报摘要 | 纯 DB 查询 + LLM |
| **知识库 (Knowledge)** | 上传文档 → 切片 → 向量化 → HNSW 索引 → RAG 检索 | Embedding (DashScope) + pgvector |
| **账号管理 (Accounts)** | 添加/管理 XHS 账号、登录态维护、配额控制 | Chrome Profile |
| **风控守卫 (Guards)** | 敏感词过滤、相似度检测、频次控制、配额限制 | 应用层规则引擎 |

### 1.2 项目目录结构

```
ai-marketing/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口 + lifespan（启停 scheduler）
│   │   ├── config.py            # 配置模型（YAML → Pydantic Settings）
│   │   ├── scheduler.py         # Cron 调度引擎（5 种 Routine Handler）
│   │   ├── guards.py            # 风控守卫（敏感词/相似度/配额/频次）
│   │   ├── api/                 # REST API 路由
│   │   │   ├── accounts.py      # 账号 CRUD + 登录触发
│   │   │   ├── content.py       # AI 内容生成（SSE 流式）
│   │   │   ├── dashboard.py     # 仪表盘统计
│   │   │   ├── drafts.py        # 草稿管理
│   │   │   ├── inbox.py         # 收件箱
│   │   │   ├── knowledge.py     # 知识库（上传/检索/RAG）
│   │   │   ├── posts.py         # 已发布帖子
│   │   │   ├── publish.py       # 手动发布触发
│   │   │   ├── routines.py      # 定时任务配置
│   │   │   └── uploads.py       # 文件上传
│   │   ├── adapters/
│   │   │   ├── chrome.py        # Chrome 子进程管理（启动/CDP/关闭）
│   │   │   ├── xhs.py           # XHS 适配器（登录/发布/评论轮询/侦察）
│   │   │   ├── xhs_tools.py     # browser-use 自定义工具（正文粘贴等）
│   │   │   └── cdp_listener.py  # CDP 网络监听（抓取 noteId）
│   │   ├── bus/
│   │   │   ├── locks.py         # Redis 分布式锁（账号锁/剪贴板锁）
│   │   │   └── pubsub.py        # Redis Pub/Sub（SSE 事件广播）
│   │   ├── db/
│   │   │   ├── base.py          # AsyncSession 工厂
│   │   │   ├── models.py        # SQLAlchemy ORM 模型（12 张表）
│   │   │   └── seed.py          # 初始数据填充（Agent Roles）
│   │   ├── llm/
│   │   │   ├── chat.py          # LangChain Chat 模型工厂
│   │   │   ├── embed.py         # Embedding 模型工厂
│   │   │   ├── reply.py         # AI 回复生成
│   │   │   ├── rewrite.py       # 文案改写
│   │   │   └── browser_llm.py   # browser-use 专用 LLM 配置
│   │   └── schemas/             # Pydantic 请求/响应模型
│   ├── alembic/                 # 数据库迁移
│   ├── profiles/                # Chrome user-data-dir（每账号一个）
│   ├── uploads/                 # 用户上传文件
│   ├── scripts/                 # 运维脚本
│   ├── config.yaml              # 主配置文件
│   ├── pyproject.toml           # Python 项目定义 + 依赖
│   ├── docker-compose.yaml      # 本地 Redis（Docker profile）
│   └── uv.lock                  # 依赖锁定
├── frontend/
│   ├── src/
│   │   ├── main.ts              # Vue 入口
│   │   ├── router.ts            # 路由配置（Hash History）
│   │   ├── App.vue              # 根组件
│   │   ├── api/
│   │   │   ├── client.ts        # HTTP API 客户端
│   │   │   └── sse.ts           # SSE 连接管理
│   │   ├── views/               # 页面组件（12 个视图）
│   │   ├── components/          # 通用 UI 组件（16 个）
│   │   ├── composables/         # 组合式函数
│   │   ├── mobile/              # 移动端适配组件
│   │   └── data/                # 静态数据
│   ├── package.json             # 前端依赖
│   ├── vite.config.ts           # Vite 构建配置 + 开发代理
│   └── tsconfig.json
├── service.ps1                  # Windows 后端服务控制脚本
├── service.bat                  # 服务控制批处理入口
├── DEPLOYMENT.md                # 详细生产部署指南
└── logs/                        # 运行日志
```

---

## 2. 技术栈

### 2.1 后端

| 组件 | 技术 | 版本要求 |
|------|------|----------|
| 运行时 | Python | ≥ 3.11 |
| Web 框架 | FastAPI | ≥ 0.118 |
| ASGI 服务器 | uvicorn | ≥ 0.34 |
| ORM | SQLAlchemy (async) | ≥ 2.0.36 |
| 数据库驱动 | asyncpg | ≥ 0.30 |
| 向量扩展 | pgvector | ≥ 0.8 |
| 迁移工具 | Alembic | ≥ 1.16 |
| 缓存/锁 | Redis | ≥ 7 |
| 浏览器自动化 | browser-use | ≥ 0.12.6 |
| LLM 框架 | LangChain + LangGraph | ≥ 1.3 |
| 包管理 | uv | ≥ 0.5 |
| 任务调度 | croniter | ≥ 6.0 |
| 日志 | loguru | ≥ 0.7 |
| 配置文件 | YAML + Pydantic | — |

### 2.2 前端

| 组件 | 技术 | 版本要求 |
|------|------|----------|
| 框架 | Vue 3 | ^3.4.27 |
| 路由 | Vue Router | ^4.3.2 |
| 构建工具 | Vite | ^5.2.11 |
| 类型检查 | TypeScript + vue-tsc | ^5.4.5 |
| Node.js | — | ≥ 18 LTS |

### 2.3 基础设施

| 组件 | 用途 | 部署方式 |
|------|------|----------|
| PostgreSQL 16+ | 业务数据 + 向量存储 | 裸机 / Docker |
| pgvector 0.8+ | HNSW 向量索引 | PostgreSQL 扩展 |
| Redis 7+ | 分布式锁 + Pub/Sub | 裸机 / Docker |
| Google Chrome 130+ | 浏览器自动化 | 裸机安装 |
| Nginx 1.24+ | 反向代理 + SSL + 静态资源 | 裸机 / Docker |
| Xvfb | Linux 无头虚拟显示 | 裸机 systemd |

---

## 3. 系统架构

### 3.1 部署拓扑图

```
                        ┌──────────────┐
                        │   用户浏览器   │
                        └──────┬───────┘
                               │ HTTPS (443)
                        ┌──────▼───────┐
                        │   Nginx      │  反向代理 + SSL 终结 + 静态资源
                        │   :443/80    │
                        └──┬──────┬───┘
                           │      │
                 /api/*    │      │  /assets/*, /* (SPA fallback)
                           │      │
                 ┌─────────▼─┐  ┌─▼──────────┐
                 │ FastAPI   │  │ 静态文件    │
                 │ uvicorn   │  │ (dist/)     │
                 │ :8000     │  └────────────┘
                 │           │
                 │ ┌───────┐ │
                 │ │Sched- │ │  ← asyncio background task（同进程）
                 │ │uler   │ │    每 15s 扫描 account_routines 表
                 │ └───────┘ │
                 └──┬──┬──┬─┘
                    │  │  │
           ┌────────▼┐ │  └──────────────┐
           │PostgreSQL│ │                 │
           │+pgvector │ │  ┌──────────────▼─┐
           │  :5432   │ │  │  Chrome 浏览器  │
           └──────────┘ │  │  (每账号一个     │
                        │  │   独立 profile)  │
           ┌──────────▼─┐ │  │  port=9300+id  │
           │   Redis     │ │  └────────────────┘
           │   :6379     │ │
           │ ┌─────────┐ │ │  LLM API (外部)
           │ │ Pub/Sub  │ │ └── DeepSeek (chat)
           │ │ Locks    │ │    DashScope (embedding)
           │ └─────────┘ │
           └────────────┘
```

### 3.2 核心组件职责

| 组件 | 职责 | 关键约束 |
|------|------|----------|
| **Nginx** | SSL 终结、反向代理 `/api/` → uvicorn、静态文件服务、SPA fallback | SSE 需关闭 proxy_buffering |
| **uvicorn** | ASGI 服务器，承载 FastAPI 应用 + scheduler 后台任务 | 单实例（scheduler 不能重复执行） |
| **FastAPI** | REST API、SSE 流式端点、CORS 中间件、lifespan 管理 | — |
| **Scheduler** | 每 15s 扫描 `account_routines` 表，匹配 cron 表达式并触发 handler | 同进程 asyncio Task |
| **PostgreSQL** | 业务数据存储 + pgvector HNSW 向量索引 | 需要 pgvector 扩展 |
| **Redis** | 账号互斥锁（SET NX EX）+ Pub/Sub 事件广播（驱动 SSE） | 密码认证 |
| **Chrome** | 真实浏览器实例，通过 CDP 协议被 browser-use Agent 驱动 | 必须真实 Chrome（非 Chromium） |
| **Xvfb** | Linux 虚拟 X11 显示（Chrome 需要 display） | :99 |

---

## 4. 后端架构详解

### 4.1 应用生命周期（`app/main.py`）

```
启动流程：
  1. FastAPI 实例化 → lifespan 进入
  2. 创建 profiles_dir 目录
  3. seed_roles() — 写入 agent_roles 初始数据（main/seeder/support/scout/engager）
  4. asyncio.create_task(scheduler_loop()) — 启动调度器后台任务
  5. uvicorn 开始接受请求
  6. /api/health 就绪

关闭流程：
  1. lifespan yield 之后
  2. scheduler_task.cancel() — 取消调度器
  3. 等待 CancelledError → 优雅退出
```

### 4.2 配置系统（`app/config.py`）

配置加载链：`config.yaml` → `yaml.safe_load()` → Pydantic `Settings.model_validate()`

```yaml
# config.yaml 六大配置块
postgresql:  # 数据库连接（host/port/user/password/database/pool）
llm:         # LLM API（DeepSeek base_url/api_key/model/temperature）
embedding:   # Embedding API（DashScope base_url/api_key/model/dimension）
redis:       # Redis 连接（host/port/password/key_prefix）
app:         # 应用设置（host/port/profiles_dir/cors_origins）
guards:      # 风控参数（配额/频次/相似度阈值/敏感词列表）
```

**生产环境改造建议**：将 `config.yaml` 中的明文 API Key 替换为 `${ENV_VAR}` 占位符，在 `get_settings()` 中递归替换环境变量值。

### 4.3 数据库模型（`app/db/models.py`）

共 **12 张表**，分为 5 个逻辑域：

#### 核心域
| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `agent_roles` | Agent 角色定义 | code, name, system_prompt, default_routines, persona |
| `accounts` | XHS 账号 | nickname, xhs_uid, role_code, profile_dir, status, last_login_at, quotas |
| `account_routines` | 账号级定时任务 | account_id, routine_code, cron, schedule_at, params, enabled |

#### 内容与工作流
| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `content_drafts` | AI 生成的内容草稿 | title, body_blocks, prompt, status (draft/ready/used) |
| `tasks` | 批量发布/互动任务 | kind, draft_id, publishers, engagers, params, status |
| `task_runs` | 任务执行记录 | task_id, account_id, role, state, progress, error |
| `agent_events` | 浏览器 Agent 事件流 | task_id, account_id, level, message, url |
| `posts` | 已发布帖子记录 | account_id, xhs_note_id, title, url, posted_at, likes/comments/collects |

#### 收件箱与评论
| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `comments_seen` | 评论去重表 | account_id, xhs_comment_id (唯一约束), author, body |
| `inbox_items` | 收件箱消息 | account_id, source, payload, status, ai_draft, sent_text |

#### 知识库
| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `knowledge_documents` | 上传的文档 | title, source_type, content, metadata |
| `knowledge_chunks` | 文档切片 + 向量 | doc_id, text, token_count, embedding (Vector 1024d, HNSW 索引) |

#### 风控
| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `guard_log` | 风控拦截日志 | account_id, kind, subject, decision (block/allow), reason |

### 4.4 调度引擎（`app/scheduler.py`）

#### 调度循环
```
scheduler_loop():
  while True:
    1. 查询 account_routines WHERE enabled = true
    2. 对每条 routine 用 croniter 判断 _should_fire()
       - 一次性任务: schedule_at 已过且 last_run_at 为空 → 触发
       - 周期性任务: 当前时间 ≥ next_run_at → 触发
    3. 更新 last_run_at / next_run_at（触发前更新，避免重复触发）
    4. asyncio.create_task(_safe_invoke(handler, r)) → 异步执行 handler
    5. sleep(15s) → 下一轮扫描
```

#### 五种 Handler

| routine_code | Handler | Chrome | 流程简述 |
|---|---|---|---|
| `daily_post` | `handle_daily_post` | ✅ | 查配额 → 选取就绪草稿 → XHSAdapter.publish_note() → 写 Post 行 |
| `poll_inbox` | `handle_poll_inbox` | ✅ | 查 7 日内帖子 → XHSAdapter.poll_inbox_comments() → 去重写 inbox_items |
| `scout_keywords` | `handle_scout_keywords` | ✅ | 读取 keywords → XHSAdapter.scout_search() → 写 inbox_items |
| `daily_feedback_check` | `handle_daily_feedback` | ❌ | 聚合当日数据 → LLM 生成日报 → 写 inbox_items |
| `daily_summary` | `handle_daily_summary` | ❌ | 委托到 daily_feedback（预留周报/月报扩展） |

#### 错误处理机制
- `_safe_invoke` 捕获 handler 异常 → 写 `inbox_items` (source=`routine_error`)，用户可在 UI 中查看失败原因
- 一次性任务失败后自动 `enabled=False` + `last_run_at=None`，用户可重新启用以重试
- 周期性任务失败不 disable，下一轮 cron 触发时自动重试

### 4.5 Redis 基础设施（`app/bus/`）

#### 账号互斥锁（`locks.py`）
```
account_lock(account_id, ttl=600):
  使用 Redis SET NX EX，确保同一账号不被两个 Chrome 同时驱动
  - 锁 key: "matrix:lock:account:{id}"
  - 释放: Lua 脚本 compare-and-delete（只删自己持有的锁）
  - XHSAdapter.chrome() 上下文管理器自动获取/释放
```

#### Pub/Sub 广播（`pubsub.py`）
```
用于 SSE 事件广播：
  - 后端 publish(channel, payload) → Redis PUBLISH
  - 前端通过 /api/sse/{channel} 端点订阅
  - 所有 Redis key 带前缀 "matrix:"（可配置）
```

---

## 5. 前端架构详解

### 5.1 路由结构

| 路由 | 视图组件 | 功能 |
|------|----------|------|
| `/dashboard` | Dashboard.vue | 仪表盘（统计数据总览） |
| `/accounts` | Accounts.vue | 账号列表管理 |
| `/accounts/:id` | AccountDetail.vue | 单个账号详情 + 登录操作 |
| `/compose` | Flow.vue (step=1) | AI 写作 — 输入 Prompt |
| `/compose/setup` | Flow.vue (step=2) | 发布设置 — 选择账号和定时 |
| `/compose/monitor` | Flow.vue (step=3) | 任务监控 — 发布进度实时展示 |
| `/drafts` | Drafts.vue | 草稿管理 |
| `/knowledge` | Knowledge.vue | 知识库管理 |
| `/routines` | Routines.vue | 定时任务配置 |
| `/inbox` | Inbox.vue | 收件箱（评论/侦察结果/日报） |
| `/mobile` | MobilePreview.vue | 移动端预览 |

### 5.2 关键前端机制

- **Hash History**：使用 `createWebHashHistory()`，兼容 Nginx 静态文件部署，刷新不 404
- **开发代理**：Vite dev server 将 `/api` 代理到 `http://localhost:8000`
- **SSE 连接**：用于 AI 写作流式输出和任务执行实时进度
- **移动端适配**：`/mobile` 路由提供移动端专用界面

---

## 6. Chrome 浏览器池机制

### 6.1 设计决策：为什么使用真实 Chrome

| 对比维度 | Playwright Chromium | 真实 Google Chrome |
|----------|---------------------|---------------------|
| Cookie 持久化 | ❌ `launch_persistent_context` 会丢失 XHS session cookies | ✅ Chrome 原生管理 profile，cookies 正确 flush |
| 反爬检测 | ❌ 特征明显，XHS 会静默关闭标签页 | ✅ 真实浏览器指纹，XHS 不封禁 |
| 登录态保持 | ❌ 重新打开后登录态丢失 | ✅ 登录态持久化，重启后仍有效 |

### 6.2 Chrome 实例管理

```
核心参数：
  - 端口: 9300 + account_id（每个账号独立 CDP 端口）
  - Profile: ./profiles/account_{id}/（独立 user-data-dir）
  - CDP URL: http://127.0.0.1:{port}

启动流程（chrome.py launch_chrome）：
  1. 检查端口是否已有 Chrome 在运行（wait_for_cdp）
     → 如果有：复用（reuse），open_cdp_tab 打开目标 URL
     → 如果没有：subprocess.Popen 启动新 Chrome
  2. 传入参数：
     --remote-debugging-port={port}
     --user-data-dir={profile_dir}
     --no-first-run
     --no-default-browser-check
  3. 轮询 /json/version 直到 CDP 就绪（最长 20s）
  4. 返回 cdp_url → 交给 browser-use Agent

关闭流程（graceful_close_chrome）：
  1. 通过 CDP WebSocket 发送 Browser.close（优雅关闭，flush cookies）
  2. 轮询端口直到不可达（最长 8s）
  3. 超时后 fallback: kill_chrome_on_port（强制杀进程）
```

### 6.3 Chrome 与 browser-use 的协作

```
XHSAdapter.publish_note():
  async with self.chrome(initial_url=...) as cdp_url:  # 获取账号锁 + 启动 Chrome
    1. 生成任务 Prompt（图文上传 或 文字配图 模式）
    2. 创建 browser-use Agent(task, llm, Browser(cdp_url=...), tools)
    3. agent.run(max_steps=60) — Agent 自主决策执行步骤
    4. 从 Agent history 提取结果（note_id, user_id）
    5. 返回 NoteRef(success, profile_url, note_id)
  # 退出上下文 → 释放账号锁 + 关闭 Chrome
```

### 6.4 Linux 服务器上的 Chrome

- **需要 Xvfb**：Chrome 需要 X11 display，即使在 headless 模式下
- **推荐 `--headless=new`**：Chrome 112+ 的新 headless 模式，行为与 GUI 一致
- **Profile 管理**：不要手动删除正在使用的 profile；单个 profile 不应超过 500MB

---

## 7. 部署逻辑详解

### 7.1 部署模式对比

| 模式 | 适用场景 | 复杂度 |
|------|----------|:---:|
| **本地开发** | 单机 Windows/Mac，前后端分离运行 | 低 |
| **Docker Compose** | 单机生产，容器化全栈部署 | 中 |
| **裸机 systemd** | 单机生产，systemd 管理进程 | 中 |
| **水平扩容** | 多 API 实例 + 独立 Scheduler + Chrome 宿主机 | 高 |

### 7.2 本地开发部署

```bash
# 1. 启动 PostgreSQL + Redis（Docker 或本地）
docker run -d --name pg -p 5432:5432 -e POSTGRES_PASSWORD=test123 pgvector/pgvector:pg17
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 2. 后端
cd backend
uv sync                    # 安装依赖
uv run alembic upgrade head  # 数据库迁移
uv run uvicorn app.main:app --port 8000 --reload

# 3. 前端
cd frontend
npm install
npm run dev                # Vite dev server → http://localhost:5173
```

### 7.3 Docker Compose 部署（推荐生产方案）

详见 `DEPLOYMENT.md` 第 7 节，核心要点：

```yaml
# docker-compose.prod.yml 四大服务
services:
  postgres:  # pgvector/pgvector:pg17
  redis:     # redis:7-alpine + 密码认证
  api:       # FastAPI + uvicorn（构建自 backend.Dockerfile）
  nginx:     # nginx:1.27-alpine（反向代理 + 静态文件）
```

关键 volumes 挂载：
- `profiles:/app/profiles` — Chrome profiles 持久化（不能丢失，含登录态）
- `uploads:/app/uploads` — 用户上传文件持久化
- `config.yaml:/app/config.yaml:ro` — 配置文件只读挂载

### 7.4 裸机 systemd 部署

详见 `DEPLOYMENT.md` 第 4 节，关键点：

1. **创建专用用户** `matrix-ops`（`/bin/false` 无 shell）
2. **systemd service 文件**：`ai-marketing-api.service`
   - `Type=simple`，`Restart=always`
   - `EnvironmentFile` 加载 `.env`
   - 安全加固：`NoNewPrivileges=yes`、`ProtectSystem=strict`、`ReadWritePaths` 限制
3. **Xvfb 服务**：`xvfb.service` 提供虚拟 display `:99`
4. **日志**：`journald` + Nginx access/error log + logrotate 轮转

### 7.5 Nginx 反向代理关键配置

```nginx
# API 代理 — SSE 关键配置
location /api/ {
    proxy_pass http://api_backend;
    proxy_http_version 1.1;        # HTTP/1.1 长连接
    proxy_buffering off;            # 关闭缓冲（SSE 必须）
    proxy_cache off;                # 关闭缓存
    proxy_read_timeout 3600s;       # 长超时（SSE 连接可能持续数分钟）
    proxy_send_timeout 3600s;
    client_max_body_size 50m;       # 大文件上传
}

# SPA fallback — 所有非 /api 路由返回 index.html
location / {
    try_files $uri $uri/ /index.html;
}

# 静态资源长期缓存（Vite 构建产出带内容 hash）
location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

---

## 8. 服务启动与控制

### 8.1 Windows 本地（`service.ps1` / `service.bat`）

```
service.bat {start|stop|restart|status|log}

  start    → 后台启动 uvicorn，tail 日志
  stop     → 杀进程 + 清理孤儿端口占用
  restart  → stop + start
  status   → 显示 pid / 端口 / /api/health 状态
  log      → tail backend.log
```

实现要点：
- `cmd /c uv run uvicorn ... 1>>log 2>&1` — stdout/stderr 合并到一个日志文件
- 启动后轮询 `/api/health` 最多 30s 确认就绪
- `Stop-ProcessTree` 递归杀子进程（uv → uvicorn → workers）
- 检测并清理占用 8000 端口的孤儿进程

### 8.2 Linux systemd

```bash
sudo systemctl start ai-marketing-api    # 启动
sudo systemctl stop ai-marketing-api     # 停止
sudo systemctl restart ai-marketing-api  # 重启
sudo systemctl status ai-marketing-api   # 状态
journalctl -u ai-marketing-api -f        # 实时日志
```

---

## 9. 数据流与关键业务流程

### 9.1 AI 写作 + 定时发帖 完整链路

```
┌──────────────────────────────────────────────────────────────┐
│ 1. AI 写作（前端 → 后端 → LLM → SSE 流式返回）                 │
│                                                              │
│  用户输入 Prompt                                              │
│    → POST /api/content/generate (SSE)                       │
│    → LangChain Chat (DeepSeek)                              │
│    → 流式返回 title + body_blocks                           │
│    → 前端实时展示                                            │
│    → 用户确认 → status: "ready"                              │
│    → ContentDraft 写入数据库                                  │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. 设置定时任务                                               │
│                                                              │
│  用户选择账号 + 草稿 + cron 表达式                             │
│    → POST /api/routines (创建 AccountRoutine)                │
│    → routine_code: "daily_post", cron: "0 9 * * *"          │
│    → enabled: true                                           │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. Scheduler 触发（scheduler_loop，每 15s 扫描）              │
│                                                              │
│  _should_fire: cron 时间到 → 触发                             │
│    → 更新 last_run_at / next_run_at                          │
│    → asyncio.create_task(_safe_invoke(handle_daily_post))   │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. Chrome 自动发布（handle_daily_post）                        │
│                                                              │
│  a. 加载账号 → 检查 active + last_login_at                   │
│  b. 查今日配额 → 已发布数 vs daily_post_quota                 │
│  c. 选草稿 → status='ready' 且未被该账号发布过                 │
│  d. XHSAdapter.publish_note(draft, images)                  │
│     → account_lock(account_id) 获取互斥锁                    │
│     → launch_chrome(profile_dir, port) 启动/复用 Chrome       │
│     → browser-use Agent 自主执行：                            │
│        1. 打开发布页                                          │
│        2. 填充标题（input_text）                              │
│        3. 粘贴正文（paste_note_body / CDP Input.insertText）  │
│        4. 上传图片（如有）                                     │
│        5. 点击发布按钮                                        │
│        6. 验证发布结果                                        │
│     → graceful_close_chrome() 优雅关闭 Chrome                 │
│  e. 写 Post 行 + 标记草稿 status='used'                       │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ 5. 评论轮询 + 自动回复                                        │
│                                                              │
│  poll_inbox handler:                                         │
│    → 查 7 日内 Post                                          │
│    → XHSAdapter.poll_inbox_comments()                        │
│    → 新评论去重（comments_seen ON CONFLICT DO NOTHING）       │
│    → 写入 inbox_items                                        │
│    → 如启用 auto_reply: generate_reply(comment) → 标记已回复   │
└──────────────────────────────────────────────────────────────┘
```

### 9.2 知识库 RAG 流程

```
知识上传：
  PDF/MD/TXT → 读取内容 → 文本切片 (RecursiveCharacterTextSplitter)
  → 每片计算 Embedding (DashScope text-embedding-v3, 1024d)
  → 写入 knowledge_chunks (HNSW 索引, cosine 距离)

RAG 检索：
  用户提问 → 计算 query embedding
  → SELECT * FROM knowledge_chunks
    ORDER BY embedding <=> query_vector  -- cosine distance
    LIMIT top_k
  → 拼接 retrieved chunks → LLM 生成答案
```

---

## 10. 配置文件说明

### 10.1 `config.yaml` 完整字段

```yaml
postgresql:
  host: "localhost"        # 数据库地址
  port: 5432
  user: "postgres"
  password: "test123"      # ⚠️ 生产环境改为环境变量
  database: "matrix-ops"
  schema: "public"
  pool_size: 20            # asyncpg 连接池大小
  max_overflow: 10         # 溢出连接数
  pool_recycle: 3600       # 连接回收时间（秒）
  echo: false              # SQL 日志

llm:
  base_url: "https://api.deepseek.com/v1"   # LLM API 地址
  api_key: "sk-..."                          # ⚠️ 明文 API Key
  model: "deepseek-chat"
  temperature: 0.3
  max_tokens: 4096
  timeout: 120
  stream: true

embedding:
  base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  api_key: "sk-..."                          # ⚠️ 明文 API Key
  model: "text-embedding-v3"
  raw_dimension: 1024   # 模型原生维度
  dimension: 1024        # 实际存储维度（可截断降维）

redis:
  host: "localhost"
  port: 6379
  db: 0
  password: ""
  max_connections: 50
  key_prefix: "matrix:"  # 所有 Redis key 的前缀

app:
  host: "localhost"
  port: 8000
  profiles_dir: "./profiles"    # Chrome user-data-dir 根目录
  cors_origins:                  # 允许的前端来源
    - "http://localhost:5173"

guards:
  daily_reply_quota_default: 30  # 每日回复配额
  daily_post_quota_default: 5    # 每日发帖配额
  reply_interval_seconds: 90     # 回复最小间隔
  similarity_threshold: 0.90     # 相似度拦截阈值
  sensitive_words:               # 敏感词列表
    - "微信"
    - "加我"
    - "私聊"
```

### 10.2 环境变量覆盖（建议改造）

```
POSTGRES_USER=matrix_ops
POSTGRES_PASSWORD=<strong-password>
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=deepseek-chat
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-v3
REDIS_PASSWORD=<strong-password>
FRONTEND_URL=https://your-domain.com
CHROME_HEADLESS=1    # 生产：1 / 调试：0
DISPLAY=:99          # Linux Xvfb display
AIMARKETING_CHROME_PATH=/usr/bin/google-chrome-stable  # 自定义 Chrome 路径
```

---

## 11. 安全注意事项

| 风险 | 严重度 | 状态 | 整改方案 |
|------|:---:|:---:|------|
| `config.yaml` 硬编码 API Key | 🔴 严重 | 当前存在 | `${ENV_VAR}` 占位符 + 环境变量替换 |
| 数据库密码明文 | 🔴 严重 | 当前存在 | 环境变量 |
| 无请求认证 | 🟡 中等 | 未实现 | 按需添加 OAuth/JWT |
| 无请求限流 | 🟡 中等 | 未实现 | Nginx `limit_req` + `limit_conn` |
| CORS 全开 | 🟡 中等 | 生产锁定 | 仅允许 `FRONTEND_URL` |
| API Key 为生产密钥 | 🟡 中等 | 当前是 | 使用独立的开发/生产 API Key |
| Redis 无密码 | 🟡 中等 | 开发环境 | 生产强制 `requirepass` |
| Chrome 进程未隔离 | 🟢 低 | 可接受 | systemd `PrivateTmp` + `ProtectSystem` |

---

## 12. 运维与监控

### 12.1 健康检查

```bash
# 基础
curl http://localhost:8000/api/health
# → {"status": "ok"}

# 详细
curl http://localhost:8000/api/dashboard/stats
# → {"accounts": {...}, "tasks": {...}, "inbox": {"pending": N, ...}}
```

### 12.2 关键监控指标

| 指标 | 检查方式 | 告警阈值 |
|------|----------|----------|
| API 可达性 | `GET /api/health` | 连续 2 次失败 |
| Inbox 堆积 | `GET /api/dashboard/stats` → `inbox.pending` | > 50 |
| 任务失败率 | Dashboard stats → tasks fail 占比 | > 20% |
| Chrome 进程数 | `pgrep -c chrome` | > 5 |
| PG 连接数 | `SELECT count(*) FROM pg_stat_activity` | > 80% pool_size |
| 磁盘 | `df -h` | > 80% |
| 内存 | `free -m` | > 85% |

### 12.3 日志查看

```bash
# 后端日志（Linux systemd）
journalctl -u ai-marketing-api -f

# 后端日志（Windows）
Get-Content .\logs\backend.log -Tail 80 -Wait

# Nginx 日志
tail -f /var/log/nginx/ai-marketing-access.log
tail -f /var/log/nginx/ai-marketing-error.log
```

### 12.4 备份要点

- **数据库**：`pg_dump --format=custom --compress=9`，每日备份，保留 30 天
- **Chrome Profiles**：`tar -czf` 打包，每周备份，含登录态（避免重新扫码）
- **恢复**：`pg_restore --clean --if-exists --no-owner`

### 12.5 常见故障排查

| 问题 | 原因 | 排查步骤 |
|------|------|----------|
| Chrome 启动失败 "cannot open display" | Xvfb 未运行 | `ps aux \| grep Xvfb` → 启动 Xvfb |
| SSE 连接断开 | Nginx buffering | 确认 `proxy_buffering off` |
| XHS 登录态丢失 | Profile Cookies 过期/损坏 | 重新扫码登录 |
| 向量搜索慢 | 缺少 HNSW 索引 | 检查 `pg_indexes` → 重建 HNSW 索引 |
| 端口占用 | 僵尸 Chrome 进程 | `pkill -f "chrome.*--remote-debugging-port"` |
| Alembic 迁移失败 | 表已存在/版本冲突 | `alembic current` → `alembic stamp head` |

---

## 附录：扩展方案

### A. Scheduler 拆分（支持多 API 实例）

当前 scheduler 与 API 同进程 → 只能单实例。拆分为独立进程后：

```
scheduler_worker.py: 独立调度进程
  → Redis SETNX 做 Leader 选举
  → 只有获得锁的实例运行 scheduler_loop
  → API 实例可以任意水平扩展
```

### B. Chrome 远程执行（Chrome 宿主机分离）

```
当前: API 服务器 = Chrome 宿主机（必须在同一台机器）
中期: Windows Chrome 宿主机 + HTTP/gRPC 远程驱动
      API 跑在轻量容器，Chrome 跑在有 GUI 的 Windows 机器
```

---

> **相关文档**：详细的裸机/Docker 部署步骤、Nginx 完整配置、安全加固清单等，请参阅 [`DEPLOYMENT.md`](./DEPLOYMENT.md)。

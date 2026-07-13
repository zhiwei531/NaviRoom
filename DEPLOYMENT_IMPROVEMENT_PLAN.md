# NaviRoom 部署改进方案

> **参考项目**：AI Marketing Matrix（`DEPLOYMENT_ARCHITECTURE.md`）
> **目标**：对当前 Ansible → Docker 迁移进行系统性规划，并借鉴成熟项目的部署模式进行全面优化
> **日期**：2026-07-13

---

## 目录

1. [当前部署现状与问题诊断](#一当前部署现状与问题诊断)
2. [参考项目的可迁移模式](#二参考项目的可迁移模式)
3. [Docker 迁移方案](#三docker-迁移方案)
4. [配置系统改造](#四配置系统改造)
5. [日志系统升级](#五日志系统升级)
6. [健康检查与监控增强](#六健康检查与监控增强)
7. [systemd 安全加固](#七systemd-安全加固)
8. [Nginx 反向代理增强](#八nginx-反向代理增强)
9. [备份与灾备方案](#九备份与灾备方案)
10. [实施路线图](#十实施路线图)
11. [验收清单](#十一验收清单)

---

## 一、当前部署现状与问题诊断

### 1.1 现有部署架构回顾

```
当前 Ansible 部署流程：
  playbook.yml
    ├── common    → apt install python3/venv/pip/git
    ├── mysql     → 安装 MySQL 8.0，建库建用户
    ├── app       → 上传 Data_processing + recommendation，创建 venv，启动 systemd
    ├── frontend  → Node.js 构建 + rsync 发布到 /var/www/naviroom
    └── nginx     → HTTPS 站点配置 + 反向代理
```

### 1.2 对标 AI Marketing Matrix 后发现的问题

对照参考项目的部署架构，NaviRoom 当前存在以下差距：

| 问题领域 | NaviRoom 现状 | AI Marketing Matrix 的做法 | 严重度 |
|---------|-------------|--------------------------|:---:|
| **配置管理** | 散落的 `os.getenv()` + 硬编码默认值 | YAML + Pydantic Settings + `${ENV_VAR}` 占位符 + 环境变量覆盖 | 🔴 高 |
| **密码管理** | `pipeline.py` 硬编码 `"Weeder123456"`；`all.yml` 明文密码 | `config.yaml` 中敏感字段通过环境变量注入 | 🔴 高 |
| **日志系统** | 全部使用 `print()`，不可追踪、不可分级 | loguru：分级、轮转、结构化、链路追踪 | 🟡 中 |
| **健康检查** | `/healthz` 仅返回 `{"status":"ok"}` | 分段健康检查（DB/外部API/关键组件状态） | 🟡 中 |
| **systemd** | `User=root`，无安全限制 | `NoNewPrivileges`、`ProtectSystem=strict`、`ReadWritePaths` 限制 | 🟡 中 |
| **Nginx** | 基本反向代理，缺少超时/Buffering 控制 | SSE 适配（`proxy_buffering off`）、`limit_req` 限流、长超时 | 🟡 中 |
| **备份策略** | 无自动备份 | `pg_dump` 每日备份 + Profile 每周打包 | 🟡 中 |
| **监控** | 无应用级监控 | 健康检查端点 + Dashboard stats + 多维度指标 | 🟢 低 |
| **调度器** | 无定时任务 | croniter asyncio 调度器（每 15s 扫描） | 🟢 低 |
| **依赖锁定** | `requirements.txt`（无版本锁定） | `uv.lock` + `pyproject.toml` | 🟢 低 |

### 1.3 最紧急的三件事

1. **配置去硬编码** — 所有密码/密钥从代码中移除，统一走环境变量 + Pydantic Settings
2. **日志系统** — `print()` 全部替换为 loguru，增加轮转和分级
3. **容器化** — Ansible → Docker Compose，降低部署门槛，保证环境一致

---

## 二、参考项目的可迁移模式

AI Marketing Matrix 的 `DEPLOYMENT_ARCHITECTURE.md` 中有以下可直接借鉴的架构模式：

### 2.1 配置管理链

```
config.yaml  →  yaml.safe_load()  →  Pydantic Settings.model_validate()  →  全局 settings 单例
     ↑                                                    ↓
  明文默认值                                   环境变量 ${ENV_VAR} 递归覆盖
```

**对 NaviRoom 的映射**：创建 `recommendation/config.py`，将所有 `os.getenv()` 收敛到一个 `Settings` 类中，各模块统一 `from recommendation.config import settings`。

### 2.2 应用生命周期管理

```
FastAPI lifespan:
  startup  → 创建目录 → 初始化种子数据 → 启动后台任务
  shutdown → 取消后台任务 → 优雅退出
```

**对 NaviRoom 的映射**：在 `server.py` 的 lifespan 中集中处理：
- spaCy 模型预加载验证
- 默认数据集存在性检查
- 安全配置警告输出（如 SECRET_KEY 为默认值）

### 2.3 部署模式分层

该参考项目定义了 4 种部署模式，NaviRoom 可以套用：

| 模式 | 适用场景 | NaviRoom 实现方式 |
|------|---------|-----------------|
| 本地开发 | Windows/Mac 单机 | `uvicorn --reload` + `vite dev` |
| Docker Compose | 单机生产 | `docker compose up -d`（本方案重点） |
| 裸机 systemd | 传统 Linux 部署 | 保留当前 Ansible 模板，但增强安全配置 |
| 水平扩容 | 高并发 | 多 API 实例 + Nginx upstream + 数据库独立 |

### 2.4 systemd 安全加固模板

参考项目的 systemd service 配置值得直接借鉴：

```ini
# AI Marketing Matrix 的 systemd 安全配置
[Service]
User=matrix-ops                  # 专用用户（非 root）
NoNewPrivileges=yes              # 禁止权限提升
ProtectSystem=strict             # 系统目录只读
ReadWritePaths=/opt/app/output   # 只开放必要的写入路径
ProtectHome=yes                  # 隔离用户 home 目录
PrivateTmp=yes                   # 独立 tmp 目录
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX  # 限制网络协议族
```

**对 NaviRoom 的映射**：更新 `naviroom-api.service.j2` 模板，应用以上安全选项。

### 2.5 Nginx SSE / API 代理最佳实践

```nginx
# 关键配置项（参考项目直接可用）
location /api/ {
    proxy_http_version 1.1;       # HTTP/1.1 长连接
    proxy_buffering off;           # SSE 必须关闭缓冲
    proxy_cache off;               # 禁止缓存
    proxy_read_timeout 3600s;      # 长超时
    client_max_body_size 20m;      # 上传限制
}

# SPA fallback
location / {
    try_files $uri $uri/ /index.html;
}

# 静态资源缓存（Vite 输出带 content hash）
location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

**对 NaviRoom 的映射**：更新 `deploy/nginx/naviroom.conf` 和 `naviroom.conf.j2`，增加上述配置项。

### 2.6 健康检查分层

```python
# 参考项目的思路：不只是 "ok"，而是分段检查
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "database": check_db(),      # 数据库连通性
        "redis": check_redis(),      # 缓存服务（NaviRoom 暂无）
        "spacy": check_spacy(),      # NLP 模型可用性
        "rooms_count": get_rooms(),  # 数据就绪状态
    }
```

---

## 三、Docker 迁移方案

> 详细实现见 `DOCKER_DEPLOY.md`，此处聚焦于**从 Ansible 到 Docker 的迁移策略和决策依据**。

### 3.1 迁移策略：渐进式，非一次性切换

```
Phase 1: Docker 开发环境          Phase 2: Docker 生产并行        Phase 3: 完全切换
─────────────────────────────────────────────────────────────────────────────
  docker compose up -d            Ansible + Docker 共存          废弃 Ansible playbook
  仅用于本地开发测试              生产逐步切流量到 Docker         全部走 Docker Compose
```

### 3.2 Ansible Role → Docker Service 映射

| Ansible Role | Docker 等价物 | 关键差异 |
|---|---|---|
| `common`（系统依赖） | Dockerfile `RUN apt-get` 层 | 不污染宿主机，重复构建可缓存 |
| `mysql`（安装 MySQL） | `mysql:8.0` 官方镜像 | 版本锁定，初始化脚本自动执行 |
| `app`（Python venv + 代码） | 自定义 Dockerfile + `pip install` | 每次构建确定性的依赖树 |
| `frontend`（Node.js 构建） | 多阶段构建（`node:20` → `nginx:alpine`） | 构建产物内置于镜像，无需 rsync |
| `nginx`（反向代理） | `nginx:alpine` + 配置文件挂载 | 无系统级安装 |
| `seed_data.yml` | `data-pipeline` profile 容器（一次性） | 通过环境变量参数化数据源 |

### 3.3 Docker 相较于 Ansible 的关键优势

| 维度 | Ansible 痛点 | Docker 解决方案 |
|------|-------------|----------------|
| 首次部署时间 | SSH 传输 + apt install + pip install，10-30 分钟 | `docker compose up`，首次构建 3-5 分钟，后续秒级 |
| 环境差异 | Ubuntu 22.04 绑定 | 任何支持 Docker 的系统 |
| 依赖冲突 | 系统 Python 版本 vs 项目需要 3.11 | 容器内完全隔离 |
| 开发/生产差异 | 两套配置，容易遗漏 | 同一个 docker-compose.yml + override |
| 回滚 | 手动 git revert + 重新部署 | `docker tag` 切旧镜像，秒级回滚 |

### 3.4 数据持久化策略

```yaml
# Docker 数据卷设计
volumes:
  mysql_data:          # MySQL 数据文件（named volume，Docker 管理）
    driver: local

# Bind mount（宿主机路径直接映射）
  - ./Data_processing/output:/app/Data_processing/output  # JSON 输出共享
  - ./Data_processing/data:/app/Data_processing/data:ro   # 源数据只读
```

**迁移注意事项**：
- 从 Ansible 迁移时，先 `mysqldump` 导出数据，再在 Docker 中导入
- `Data_processing/output/*.json` 直接用 bind mount 指向现有文件
- Chrome profiles（NaviRoom 目前不涉及，但未来可能用于自动化预约）

### 3.5 CI/CD 集成展望

```yaml
# GitHub Actions 示例（参考项目模式）
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build and deploy
        run: |
          docker compose -f docker-compose.yml -f docker-compose.prod.yml build
          docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 四、配置系统改造

### 4.1 当前问题

```python
# engine.py — 散落的 os.getenv，无类型校验，无默认值集中管理
mode = os.getenv("RECO_SEMANTIC_MODE", "hybrid").strip().lower()
llm_top_k = int(os.getenv("RECO_LLM_TOP_K", "8"))

# pipeline.py:289 — 硬编码密码
parser.add_argument("--db-password", default="Weeder123456")

# group_vars/all.yml — 明文存储
naviroom_db_password: "endjb&14h678"
mysql_root_password: "45#3280ghwy!13497"
```

### 4.2 改进方案：Pydantic Settings

创建 `recommendation/config.py`，统一所有配置：

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 数据库 ----
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "navi_room_db"
    db_user: str = "root"
    db_password: str = ""  # 必填，不设默认值以强制配置

    # ---- LLM ----
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout_s: float = 15.0

    # ---- 推荐引擎 ----
    reco_semantic_mode: str = "hybrid"       # lexical | llm | hybrid | zero_shot
    reco_requirements_mode: str = "merge"     # manual | llm | merge
    reco_llm_top_k: int = 8
    reco_recency_half_life_days: float = 30.0

    # ---- JWT ----
    secret_key: str = "change_me_in_production"  # 生产环境必须更换
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # ---- 安全自检 ----
    def validate_security(self) -> list[str]:
        """返回不安全的配置项列表，在启动时打印警告"""
        warnings = []
        if self.secret_key == "change_me_in_production":
            warnings.append("SECRET_KEY 为默认值")
        if not self.db_password:
            warnings.append("DB_PASSWORD 未设置")
        if not self.llm_api_key and self.reco_semantic_mode in ("llm", "hybrid"):
            warnings.append("LLM_API_KEY 缺失，LLM 功能将降级")
        return warnings
```

### 4.3 各文件改造清单

| 文件 | 当前写法 | 改为 |
|------|---------|------|
| `engine.py` L320 | `os.getenv("RECO_SEMANTIC_MODE", "hybrid")` | `settings.reco_semantic_mode` |
| `engine.py` L366 | `os.getenv("RECO_RECENCY_HALF_LIFE_DAYS", "30")` | `settings.reco_recency_half_life_days` |
| `engine.py` L485-487 | `os.getenv("RECO_SEMANTIC_MODE")` + `os.getenv("RECO_LLM_TOP_K")` | `settings.reco_semantic_mode` + `settings.reco_llm_top_k` |
| `api.py` L14 | `os.getenv("RECO_REQUIREMENTS_MODE", "manual")` | `settings.reco_requirements_mode` |
| `llm.py` L22 | `os.getenv("LLM_API_KEY")` | `settings.llm_api_key` |
| `llm.py` L68-91 | 硬编码 `base_url`、`model`、`timeout` | `settings.llm_base_url`、`settings.llm_model`、`settings.llm_timeout_s` |
| `auth_store.py` L67-72 | 硬编码 `build_db_url()` 中的默认值 | `settings.db_url` |
| `server.py` L107 | `os.getenv("RECO_DATASET_PATH", ...)` | `settings.reco_dataset_path` |
| `pipeline.py` L289 | `default="Weeder123456"` | 移除默认值，改从环境变量读取 |

### 4.4 .env 文件模板

```bash
# NaviRoom 环境变量
# 生产环境通过 systemd EnvironmentFile 或 Docker Compose environment 注入

# 数据库
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=navi_room_db
DB_USER=navi_user
DB_PASSWORD=<生成强密码>

# LLM（DeepSeek）
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 推荐引擎
RECO_SEMANTIC_MODE=hybrid
RECO_REQUIREMENTS_MODE=merge
RECO_LLM_TOP_K=8
RECO_RECENCY_HALF_LIFE_DAYS=30

# JWT
SECRET_KEY=<openssl rand -hex 32 生成>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 数据集路径
RECO_DATASET_PATH=Data_processing/output/dku_dataset.json
```

---

## 五、日志系统升级

### 5.1 当前问题

```python
# 全项目使用 print()，无法：
#   - 分级（INFO/WARNING/ERROR）
#   - 记录时间戳和模块名
#   - 写文件 + 轮转
#   - 生产环境排查问题

print(f"Pipeline completed → {output}")          # pipeline.py
print(f"成功连接到 MySQL 数据库")                 # db_manager.py
print(f"Skip Error: Could not parse dates...")   # csv_processing.py
```

### 5.2 改进方案：loguru

创建 `recommendation/logging_config.py`：

```python
"""NaviRoom 日志配置"""
import sys
from pathlib import Path
from loguru import logger

def setup_logging(
    log_dir: str = "logs",
    level: str = "INFO",
    rotation: str = "50 MB",
    retention: str = "30 days",
):
    """初始化全局日志配置"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # 移除默认 handler
    logger.remove()

    # 控制台输出：彩色格式
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level=level,
        colorize=True,
    )

    # 全量日志文件：结构化格式
    logger.add(
        log_path / "api_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )

    # 错误日志单独文件
    logger.add(
        log_path / "error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
        level="ERROR",
        rotation=rotation,
        retention="90 days",
        encoding="utf-8",
    )

    return logger
```

### 5.3 替换清单

| 原写法 | 替换为 |
|-------|--------|
| `print(f"Pipeline completed → {output}")` | `logger.info(f"Pipeline completed → {output}")` |
| `print(f"成功连接到 MySQL 数据库")` | `logger.info("成功连接到 MySQL 数据库")` |
| `print(f"Error: {e}")` | `logger.error(f"数据库操作失败: {e}")` |
| `print(f"Skip Error: Could not parse...")` | `logger.warning(f"跳过无法解析的行: {row}")` |
| 无日志（异常被静默吞掉） | `logger.exception("LLM API 调用异常")` |

---

## 六、健康检查与监控增强

### 6.1 当前状态

```python
# server.py:51-53 — 信息量太少
@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

### 6.2 改进方案

```python
# server.py — 增强后的健康检查
from recommendation.config import settings

@app.get("/healthz")
def healthz():
    """轻量存活检查（Liveness Probe）"""
    return {"status": "ok", "version": "3.1.0"}


@app.get("/health/ready")
def health_ready():
    """就绪检查（Readiness Probe），包含依赖服务状态"""
    checks = {}

    # 1. 数据库连通性
    try:
        # 使用 auth_store 的连接测试
        from recommendation.auth_store import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # 2. spaCy 模型可用性
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
        checks["spacy_model"] = "loaded"
    except Exception as e:
        checks["spacy_model"] = f"error: {e}"

    # 3. 数据集状态
    from pathlib import Path
    dataset_file = settings.dataset_path
    if dataset_file.exists():
        checks["dataset"] = f"present ({dataset_file.stat().st_size} bytes)"
    else:
        checks["dataset"] = "missing"

    # 4. LLM API 状态（可选，仅在启用时检查）
    if settings.llm_api_key and settings.reco_semantic_mode != "lexical":
        checks["llm_api"] = "configured"
    else:
        checks["llm_api"] = "disabled"

    # 汇总状态
    critical_checks = {k: v for k, v in checks.items() if k != "llm_api"}
    all_ok = all(not str(v).startswith("error") for v in critical_checks.values())

    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }
```

### 6.3 Kubernetes 风格探针设计

```
Liveness Probe:  GET /healthz     → 进程是否存活
Readiness Probe: GET /health/ready → 进程是否可以接受流量
Startup Probe:   GET /health/ready → 初始启动是否完成（可设置更长 initialDelaySeconds）
```

---

## 七、systemd 安全加固

### 7.1 当前配置（问题）

```ini
# naviroom-api.service.j2 — 当前版本
[Service]
Type=simple
User=root                           # ❌ 以 root 运行
WorkingDirectory={{ naviroom_api_workdir }}
EnvironmentFile={{ naviroom_app_dir }}/.env
ExecStart={{ naviroom_venv }}/bin/uvicorn {{ naviroom_api_module }} ...
Restart=always
RestartSec=5
# ❌ 缺少任何安全限制
```

### 7.2 改进方案

```ini
# naviroom-api.service.j2 — 安全加固版（参考 AI Marketing Matrix）
[Unit]
Description=NaviRoom FastAPI service
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
# 使用专用用户（非 root）
User=naviroom
Group=naviroom

WorkingDirectory={{ naviroom_api_workdir }}
EnvironmentFile={{ naviroom_app_dir }}/.env
ExecStart={{ naviroom_venv }}/bin/uvicorn {{ naviroom_api_module }} \
    --host {{ naviroom_api_host }} --port {{ naviroom_api_port }} \
    --workers 1
Restart=always
RestartSec=5

# ---- 安全加固（参考 DEPLOYMENT_ARCHITECTURE.md 第 7.4 节） ----
NoNewPrivileges=yes                  # 禁止 setuid 等提权操作
ProtectSystem=strict                 # /usr、/boot、/etc 只读
# 只开放应用需要写入的路径
ReadWritePaths={{ naviroom_api_workdir }}/Data_processing/output
ReadWritePaths={{ naviroom_api_workdir }}/logs
ReadWritePaths=/tmp
ProtectHome=yes                      # 隔离 /home、/root、/run/user
PrivateTmp=yes                       # 独立 /tmp 和 /var/tmp
PrivateDevices=yes                   # 隔离设备节点
ProtectKernelTunables=yes            # 禁止修改内核参数
ProtectKernelModules=yes             # 禁止加载内核模块
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX  # 限制网络协议族
SystemCallFilter=@system-service     # 系统调用白名单
RestrictRealtime=yes                 # 禁止实时调度
MemoryDenyWriteExecute=yes           # 禁止可写内存页执行

# 资源限制
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

### 7.3 配套：Ansible 创建专用用户

在 `roles/app/tasks/main.yml` 中增加：

```yaml
- name: Create naviroom service user
  ansible.builtin.user:
    name: naviroom
    system: true
    shell: /usr/sbin/nologin
    create_home: false
    home: "{{ naviroom_app_dir }}"

- name: Ensure app directory ownership
  ansible.builtin.file:
    path: "{{ naviroom_app_dir }}"
    owner: naviroom
    group: naviroom
    recurse: true
```

---

## 八、Nginx 反向代理增强

### 8.1 当前配置（问题）

当前 `deploy/nginx/naviroom.conf` 和 `naviroom.conf.j2` 只有基本的反向代理：

```nginx
# 缺失：
#   - proxy_read_timeout（推荐接口可能耗时较长）
#   - proxy_buffering off（如果未来加 SSE）
#   - client_max_body_size（当前只在 /recommend/ 有）
#   - Gzip 压缩
#   - 限流
#   - 安全头（HSTS、X-Frame-Options 等）
```

### 8.2 改进方案

```nginx
# naviroom.conf.j2 — 增强版（参考 DEPLOYMENT_ARCHITECTURE.md 第 7.5 节）

# ---- upstream 定义 ----
upstream api_backend {
    server 127.0.0.1:{{ naviroom_api_port }};
    keepalive 32;          # 连接池
}

# ---- HTTP → HTTPS 重定向 ----
server {
    listen 80;
    server_name {{ naviroom_domain }} {{ naviroom_domain_www }};
    return 301 https://$host$request_uri;
}

# ---- HTTPS 主站点 ----
server {
    listen 443 ssl http2;
    server_name {{ naviroom_domain }} {{ naviroom_domain_www }};

    # TLS 证书
    ssl_certificate     {{ naviroom_tls_cert_path }};
    ssl_certificate_key {{ naviroom_tls_key_path }};

    # TLS 安全配置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # 安全头
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # 前端静态文件
    root {{ naviroom_frontend_web_root }};
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml text/javascript image/svg+xml;
    gzip_min_length 1000;
    gzip_vary on;

    # 上传大小限制（全局）
    client_max_body_size 20M;

    # ---- SPA fallback ----
    location / {
        try_files $uri $uri/ /index.html;
    }

    # ---- 静态资源长期缓存 ----
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # ---- API 代理 ----
    location /api/ {
        proxy_pass http://api_backend/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;          # 普通 API 60s 超时
        proxy_connect_timeout 10s;
    }

    # ---- 推荐接口代理（更长超时：LLM rerank 可能耗时） ----
    location /recommend/ {
        proxy_pass http://api_backend/recommend/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90s;          # LLM 调用需要更长时间
        proxy_buffering off;             # 如果未来加 SSE 流式输出
        client_max_body_size 20M;
    }

    # ---- 认证与数据接口 ----
    location /auth/ {
        proxy_pass http://api_backend/auth/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    location /data/ {
        proxy_pass http://api_backend/data/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # ---- 健康检查 ----
    location /healthz {
        proxy_pass http://api_backend/healthz;
        proxy_http_version 1.1;
        access_log off;                  # 不记录健康检查日志
    }

    # ---- 限流（防滥用） ----
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        # ... 其余 proxy 配置 ...
    }
}
```

---

## 九、备份与灾备方案

### 9.1 自动化备份脚本

参考 AI Marketing Matrix 的备份策略（`DEPLOYMENT_ARCHITECTURE.md` 第 12.4 节），创建 `scripts/backup.sh`：

```bash
#!/bin/bash
# NaviRoom 自动备份脚本
# 用法: ./scripts/backup.sh [daily|weekly]
# 建议 crontab:
#   0 2 * * * /opt/naviroom/scripts/backup.sh daily
#   0 3 * * 0 /opt/naviroom/scripts/backup.sh weekly

set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/opt/naviroom/backups}"
DB_NAME="${DB_NAME:-navi_room_db}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-}"
MODE="${1:-daily}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/${MODE}_${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

echo "=== NaviRoom Backup (${MODE}) ==="
echo "Backup dir: ${BACKUP_DIR}"

# ---- 1. MySQL 数据库备份 ----
echo "[1/3] Backing up database..."
if [ -n "${DB_PASSWORD}" ]; then
    MYSQL_PWD="${DB_PASSWORD}" mysqldump \
        -u "${DB_USER}" \
        --single-transaction \
        --routines \
        --triggers \
        "${DB_NAME}" | gzip > "${BACKUP_DIR}/database.sql.gz"
else
    # Docker 环境（通过 docker compose exec）
    docker compose exec -T mysql mysqldump \
        -u root -p"${MYSQL_ROOT_PASSWORD}" \
        --single-transaction \
        "${DB_NAME}" | gzip > "${BACKUP_DIR}/database.sql.gz"
fi
echo "  → database.sql.gz ($(du -h ${BACKUP_DIR}/database.sql.gz | cut -f1))"

# ---- 2. 数据集 JSON 备份 ----
echo "[2/3] Backing up dataset files..."
DATASET_DIR="Data_processing/output"
if [ -d "${DATASET_DIR}" ]; then
    tar czf "${BACKUP_DIR}/datasets.tar.gz" -C "$(dirname ${DATASET_DIR})" "$(basename ${DATASET_DIR})"
    echo "  → datasets.tar.gz ($(du -h ${BACKUP_DIR}/datasets.tar.gz | cut -f1))"
fi

# ---- 3. 环境变量备份（不含敏感值信息） ----
echo "[3/3] Backing up deployment metadata..."
{
    echo "Backup timestamp: $(date -Iseconds)"
    echo "Host: $(hostname)"
    echo "Git commit: $(git rev-parse HEAD 2>/dev/null || echo 'N/A')"
    docker compose version 2>/dev/null || echo "Docker Compose: N/A"
} > "${BACKUP_DIR}/metadata.txt"

# ---- 清理旧备份 ----
echo "Cleaning old backups..."
# daily 保留 30 天
find "${BACKUP_ROOT}" -name "daily_*" -type d -mtime +30 -exec rm -rf {} \; 2>/dev/null || true
# weekly 保留 90 天
find "${BACKUP_ROOT}" -name "weekly_*" -type d -mtime +90 -exec rm -rf {} \; 2>/dev/null || true

echo "=== Backup complete ==="
echo "Restore command:"
echo "  gunzip -c ${BACKUP_DIR}/database.sql.gz | docker compose exec -T mysql mysql -u root -p navi_room_db"
```

### 9.2 恢复流程

```bash
# 1. 列出可用备份
ls -lt /opt/naviroom/backups/

# 2. 恢复数据库
RESTORE_DIR="/opt/naviroom/backups/daily_20260713_020000"
gunzip -c "${RESTORE_DIR}/database.sql.gz" | \
    docker compose exec -T mysql mysql -u root -p navi_room_db

# 3. 恢复数据集
tar xzf "${RESTORE_DIR}/datasets.tar.gz" -C /

# 4. 验证
docker compose exec api python -c "
from recommendation.api import recommend_from_dataset_json
import json
dataset = json.load(open('Data_processing/output/dku_dataset.json'))
print(f'Rooms: {len(dataset[\"rooms\"])}, Reservations: {len(dataset[\"reservations\"])}')
"
```

---

## 十、实施路线图

```
Week 1: 基础改造                    Week 2: 容器化                    Week 3: 加固与监控
─────────────────────────────────────────────────────────────────────────────────────
□ 创建 config.py                    □ 编写 Dockerfile (4个)           □ systemd 安全加固
□ 创建 logging_config.py            □ 编写 docker-compose.yml         □ Nginx 配置增强
□ 改造 engine.py (os.getenv → settings) □ 编写 .env.docker 模板      □ backup.sh 脚本
□ 改造 api.py                       □ MySQL 初始化脚本                □ verify.yml 增强
□ 改造 llm.py                       □ 在本地环境启动验证              □ 健康检查增强
□ 改造 auth_store.py                □ 编写 DOCKER_DEPLOY.md           □ 文档整理
□ 改造 server.py                    □ first-deploy.sh 一键脚本        □ 生产环境试运行
```

### 各文件改造工作量评估

| 文件 | 改造内容 | 风险 | 预估时间 |
|------|---------|:--:|:------:|
| `recommendation/config.py` | **新建**，Pydantic Settings 定义 | 低 | 30 min |
| `recommendation/logging_config.py` | **新建**，loguru 配置 | 低 | 15 min |
| `recommendation/engine.py` | `os.getenv()` → `settings.*`（4 处） | 低 | 10 min |
| `recommendation/api.py` | `os.getenv()` → `settings.*`（1 处） | 低 | 5 min |
| `recommendation/llm.py` | 硬编码值 → `settings.*`（5 处） | 低 | 10 min |
| `recommendation/auth_store.py` | `build_db_url()` 改用 settings | 低 | 10 min |
| `recommendation/server.py` | 增强 `/health/ready`、lifespan、loguru | 中 | 30 min |
| `Data_processing/scripts/pipeline.py` | 移除默认密码 + loguru | 中 | 15 min |
| `naviroom-api.service.j2` | 安全加固 | 低 | 15 min |
| `naviroom.conf.j2` / `naviroom.conf` | Nginx 增强配置 | 中 | 20 min |
| `deploy/roles/app/tasks/main.yml` | 添加 naviroom 用户创建 | 低 | 10 min |
| `docker/*` (4 个 Dockerfile) | **新建**，多阶段构建 | 中 | 1.5 h |
| `docker-compose.yml` + `.prod.yml` | **新建**，服务编排 | 中 | 1 h |
| `scripts/backup.sh` | **新建**，备份脚本 | 低 | 20 min |
| `DOCKER_DEPLOY.md` | **新建**，部署文档 | — | 已完成 |

---

## 十一、验收清单

部署改进完成后，按此清单逐项验收：

### 配置系统

- [ ] `config.py` 存在且被 `engine.py`、`api.py`、`llm.py`、`auth_store.py`、`server.py` 引用
- [ ] 项目中无残留 `os.getenv()` 调用（用于推荐配置的部分）
- [ ] `pipeline.py` 中无硬编码密码
- [ ] `.env` 文件被 `.gitignore` 排除
- [ ] 启动时 `settings.validate_security()` 输出安全警告

### 日志系统

- [ ] 项目中无残留 `print()` 调用（核心逻辑部分）
- [ ] 日志输出到 `logs/` 目录，按日期轮转
- [ ] 错误日志单独文件，保留 90 天
- [ ] 日志包含时间戳、级别、模块、行号

### 健康检查

- [ ] `GET /healthz` 返回 `{"status": "ok", "version": "..."}`
- [ ] `GET /health/ready` 返回数据库、spaCy 模型、数据集状态
- [ ] 数据库不可达时 `/health/ready` 返回 503

### Docker

- [ ] `docker compose up -d` 一次启动全部服务
- [ ] `docker compose ps` 所有服务状态为 healthy
- [ ] `curl localhost:8000/healthz` 返回正常
- [ ] `curl localhost:3000/` 返回前端首页
- [ ] MySQL 数据在 `docker compose down && up` 后仍存在

### systemd（如果保留 Ansible）

- [ ] `naviroom-api` 以 `naviroom` 用户运行（非 root）
- [ ] `NoNewPrivileges=yes` 生效
- [ ] `ProtectSystem=strict` 生效

### Nginx

- [ ] HTTP → HTTPS 301 重定向
- [ ] SPA 路由刷新不 404
- [ ] `/assets/` 带 `Cache-Control: public, immutable`
- [ ] `/api/` 代理超时 ≥ 60s
- [ ] `/recommend/` 代理超时 ≥ 90s，buffering 关闭

### 备份

- [ ] `scripts/backup.sh daily` 执行成功
- [ ] 备份文件包含 database.sql.gz + datasets.tar.gz + metadata.txt
- [ ] 旧备份自动清理（daily 30 天，weekly 90 天）

---

> **相关文档**：
> - `DOCKER_DEPLOY.md` — Docker 化部署详细步骤（所有 Dockerfile、compose 文件、Nginx 配置的完整代码）
> - `DEPLOYMENT_ARCHITECTURE.md` — 参考项目的部署架构文档（AI Marketing Matrix）
> - `architecture_deployment_midterm_section.txt` — 当前项目的架构说明（待补充）

# NaviRoom 对外服务部署指南

> **目标场景**：外部用户通过网页上传 Excel/文字信息 → 与 AI 对话 → 获取预约推荐结果
> **当前状态**：核心 API 已就绪，前端需对接，需补充"对话式推荐"端点
> **预计部署时间**：2-4 小时

---

## 目录

1. [场景分析：现有能力 vs 需要补充的](#一场景分析现有能力-vs-需要补充的)
2. [整体架构](#二整体架构)
3. [需要补充的代码](#三需要补充的代码)
4. [前端改造：从静态页面到对话推荐](#四前端改造从静态页面到对话推荐)
5. [Docker 部署步骤](#五docker-部署步骤)
6. [域名与外部访问配置](#六域名与外部访问配置)
7. [验证流程](#七验证流程)

---

## 一、场景分析：现有能力 vs 需要补充的

### 1.1 用户的目标交互流程

```
用户打开网页
  │
  ▼
① 上传 Excel/CSV 或粘贴文字（描述自己的房间数据）
  │  例如：上传一个包含 50 间会议室的 Excel 表格
  │
  ▼
② 输入自然语言问题
  │  "我需要一个能容纳 4 人的安静房间，要有投影仪和白板"
  │
  ▼
③ AI 返回推荐结果（带解释）
  │  "为您推荐以下房间：R1124（2楼，4人，评分0.85）..."
  │
  ▼
④ 用户可以继续追问、细化条件
  │  "有没有下午 3 点以后可用的？"
  │  "换成带电视的也可以"
  │
  ▼
⑤ AI 更新推荐结果
```

### 1.2 现有代码能力盘点

| 步骤 | 需要的功能 | 现有代码 | 状态 |
|:---:|------|------|:---:|
| ① | 解析 Excel/CSV/文字 → 结构化房间数据 | `RoomParser` (`nlp_2_json_spacy.py`) 支持 CSV、Excel、纯文本 | ✅ 已有 |
| ① | 接收文件上传的 API | `POST /recommend/upload` 已支持 CSV 文件 + 文字描述 | ✅ 已有 |
| ② | 接收自然语言查询 | 同一个接口的 `user_query` 参数 | ✅ 已有 |
| ③ | 返回推荐结果 + 解释 | `recommend_top5()` 返回 `ScoredRoom`（含 `reasons`） | ✅ 已有 |
| ③ | LLM 理解用户意图 | `llm_extract_requirements()` 从自然语言提取结构化需求 | ✅ 已有 |
| ③ | LLM 重排序推荐 | `llm_score_relevance()` 语义相关性评分 | ✅ 已有 |
| ④ | 多轮对话（上下文保持） | ❌ 无——每次请求是独立的 | 🔴 需新增 |
| ④ | 前端对话界面 | ❌ 当前 UploadPage 只是静态表单+图片上传 | 🔴 需改造 |
| ⑤ | 根据对话历史更新推荐 | ❌ 需要 session 管理 | 🔴 需新增 |

### 1.3 结论：三件事需要做

```
需要补充的：
  🔴 1. 后端：增加一个"对话式推荐"端点（保持会话上下文）
  🔴 2. 前端：改造 UploadPage 为对话界面（上传数据 → 发消息 → 显示结果）
  🟡 3. 前端：支持 Excel 文件上传（当前只支持图片）
```

---

## 二、整体架构

### 2.1 部署拓扑

```
外部用户浏览器
  │
  │  https://naviroom.cn
  ▼
┌─────────────────────────────────────┐
│           云主机 (Ubuntu 22.04)       │
│                                     │
│  ┌──────────────────────────────┐  │
│  │  Nginx (:443)                │  │
│  │  TLS 终结 + 反向代理          │  │
│  │  /api/*    → API:8000        │  │
│  │  /*        → Frontend:3000   │  │
│  └──────────┬──────────┬────────┘  │
│             │          │           │
│  ┌──────────▼─┐  ┌────▼─────────┐  │
│  │  Frontend   │  │  FastAPI      │  │
│  │  (React)    │  │  :8000        │  │
│  │  :3000      │  │               │  │
│  │             │  │  POST /recommend/chat    │  │
│  │  ①上传数据  │  │  POST /recommend/upload  │  │
│  │  ②对话界面  │  │  GET  /healthz           │  │
│  │  ③结果展示  │  │               │  │
│  └────────────┘  └──────┬────────┘  │
│                         │           │
│                ┌────────▼────────┐  │
│                │     MySQL       │  │
│                │     :3306       │  │
│                └─────────────────┘  │
│                         │           │
│                ┌────────▼────────┐  │
│                │  DeepSeek API   │  │
│                │  (外部 LLM)      │  │
│                └─────────────────┘  │
└─────────────────────────────────────┘
```

### 2.2 用户请求的完整链路

```
[浏览器]                                [后端]
   │                                       │
   │──① POST /api/recommend/upload──────→ │
   │   multipart/form-data:                │  RoomParser 解析 Excel/CSV/文本
   │   - file: rooms.xlsx                 │  → 生成 rooms 列表
   │   - room_text: "..."                 │  → 存入 session (内存)
   │                                      │  → 返回 session_id + 解析结果
   │←── { session_id, rooms_count: 50 } ──│
   │                                       │
   │──② POST /api/recommend/chat────────→ │
   │   - session_id: "abc123"             │  LLM 提取需求:
   │   - message: "4个人安静房间带投影仪"   │     capacity=4, equipment=["projector"]
   │                                      │  推荐引擎:
   │                                      │     过滤 → 语义匹配 → 行为评分
   │                                      │  → 返回 Top-5 + reasons
   │←── { recommendations: [...], ────────│
   │      ai_response: "为您找到..." }     │
   │                                       │
   │──③ POST /api/recommend/chat────────→ │
   │   - session_id: "abc123"             │  追加到对话历史
   │   - message: "下午3点以后可用的"        │  更新 requirements (time_slot=afternoon)
   │                                      │  重新推荐
   │←── { recommendations: [...], ────────│
   │      ai_response: "筛选后..." }       │
```

---

## 三、需要补充的代码

### 3.1 新增对话推荐端点

在 `server.py` 中新增以下内容：

```python
# server.py — 新增部分

import uuid
from datetime import datetime, timedelta

# ---- 会话存储（生产环境应换 Redis） ----
# key: session_id, value: {rooms, reservations, history, created_at}
_sessions: dict[str, dict] = {}

SESSION_TTL = timedelta(hours=2)  # 会话 2 小时后过期


def _cleanup_expired_sessions():
    """清理过期会话"""
    now = datetime.now()
    expired = [
        sid for sid, s in _sessions.items()
        if now - s["created_at"] > SESSION_TTL
    ]
    for sid in expired:
        del _sessions[sid]


# ---- 新增：对话式推荐端点 ----
@app.post("/recommend/chat")
async def recommend_chat(
    user_query: str = Form(..., description="用户本次输入的问题"),
    session_id: str = Form(default="", description="会话 ID，首次为空则自动创建"),
    requirements: str = Form(default="{}", description="JSON 字符串的结构化约束"),
    file: UploadFile = File(default=None, description="Excel/CSV 文件（首次上传时提供）"),
    room_text: str = Form(default="", description="文字描述的房间信息（首次上传时提供）"),
):
    """
    对话式房间推荐。

    首次调用：
        - 上传 CSV/Excel 文件 或 粘贴文字描述 → 解析房间数据 → 创建会话
        - 同时可以带 user_query 立即获取第一个推荐结果

    后续调用：
        - 只需传 session_id + user_query
        - 系统会根据对话历史 + 已有房间数据进行推荐
    """
    _cleanup_expired_sessions()

    # ---- 1. 获取或创建会话 ----
    session: dict | None = None
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
    elif session_id and session_id not in _sessions:
        raise HTTPException(status_code=404, detail="会话已过期，请重新上传数据")

    # ---- 2. 解析房间数据（首次上传） ----
    rooms: list[dict[str, Any]] = []
    if session is None:
        # 新会话：必须提供数据源
        if file is not None and file.filename:
            ext = Path(file.filename).suffix.lower()
            if ext not in (".csv", ".xlsx", ".xls"):
                raise HTTPException(status_code=400, detail="仅支持 CSV 和 Excel 格式")
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="文件过大（最大 10 MB）")
            parser = RoomParser()
            rooms = parser.parse(content.decode("utf-8-sig") if ext == ".csv"
                                 else content)
        elif room_text.strip():
            parser = RoomParser()
            rooms = parser.parse(room_text.strip())
        else:
            raise HTTPException(
                status_code=400,
                detail="首次使用请上传 Excel/CSV 文件，或在文本框中描述房间信息",
            )

        # 创建会话
        session_id = uuid.uuid4().hex[:12]
        session = {
            "rooms": rooms,
            "reservations": [],  # 随对话逐步补充
            "history": [],       # 对话历史
            "created_at": datetime.now(),
        }
        _sessions[session_id] = session
    else:
        rooms = session["rooms"]

    # ---- 3. 处理结构化需求 ----
    try:
        req_dict: dict[str, Any] = json.loads(requirements) if requirements.strip() else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="requirements 必须是合法 JSON")

    # ---- 4. 构建对话上下文 ----
    # 将最近的对话历史拼接，帮助 LLM 理解上下文
    context_requirements = {}
    if session["history"]:
        recent_history = "\n".join(
            f"用户: {h['user']}\n助手: {h['assistant'][:200]}"
            for h in session["history"][-3:]  # 最近 3 轮
        )
        # 让 LLM 从对话历史中提取累积的需求
        try:
            from recommendation.llm import llm_extract_requirements
            context_requirements = llm_extract_requirements(
                user_query=f"{recent_history}\n用户最新问题: {user_query}"
            )
        except Exception:
            pass

    # 合并：对话上下文需求 + 显式传入需求
    merged_requirements = {**context_requirements, **req_dict}

    # ---- 5. 运行推荐 ----
    payload = {
        "user_query": user_query,
        "requirements": merged_requirements,
        "rooms": rooms,
        "reservations": session["reservations"],
    }
    results = recommend_rooms_payload(payload)

    # ---- 6. 生成 AI 自然语言回复 ----
    ai_response = _generate_chat_reply(
        user_query=user_query,
        results=results,
        rooms=rooms,
    )

    # ---- 7. 更新会话历史 ----
    session["history"].append({
        "user": user_query,
        "assistant": ai_response,
        "results": results,
        "timestamp": datetime.now().isoformat(),
    })
    # 只保留最近 20 轮
    if len(session["history"]) > 20:
        session["history"] = session["history"][-20:]

    return {
        "session_id": session_id,
        "ai_response": ai_response,
        "recommendations": results,
        "rooms_count": len(rooms),
        "history_count": len(session["history"]),
    }


def _generate_chat_reply(
    user_query: str,
    results: list[dict[str, Any]],
    rooms: list[dict[str, Any]],
) -> str:
    """生成 AI 自然语言回复（LLM 可用时）"""
    # 有 LLM 时生成自然语言回复
    try:
        from recommendation.llm import _client, LLMConfig, _extract_json_payload
        import json as _json

        cfg = LLMConfig()
        client = _client(cfg)

        prompt = (
            "你是一个房间预约助手的 AI 回复生成器。根据推荐结果，用中文给用户一个友好、有帮助的回复。\n"
            f"用户问题：{user_query}\n"
            f"推荐结果（JSON）：{_json.dumps(results, ensure_ascii=False)}\n\n"
            "回复要求：\n"
            "- 用自然的口吻告诉用户找到了哪些合适的房间\n"
            "- 简要说明每个房间为什么推荐（引用 reasons 字段）\n"
            "- 如果结果不够理想，礼貌地建议用户调整条件\n"
            "- 限制在 200 字以内"
        )
        resp = client.chat.completions.create(
            model=cfg.chat_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or _build_fallback_reply(results)
    except Exception:
        return _build_fallback_reply(results)


def _build_fallback_reply(results: list[dict[str, Any]]) -> str:
    """无 LLM 时的备选回复"""
    if not results:
        return "抱歉，没有找到完全匹配的房间。您可以尝试调整条件，例如放宽容量要求或去掉某些设备限制。"

    lines = [f"为您找到 {len(results)} 个推荐房间："]
    for i, r in enumerate(results, 1):
        reasons = ", ".join(r.get("reasons", [])[:2])
        lines.append(
            f"{i}. 房间 {r['room_id']}（匹配度 {r['final_score']:.0%}）"
            f"{' — ' + reasons if reasons else ''}"
        )
    return "\n".join(lines)
```

### 3.2 Excel 文件上传支持

当前 `/recommend/upload` 和 RoomParser 已经支持 Excel（`openpyxl`），无需额外改动核心解析器。但上传端点需要扩展：

```python
# server.py — 修改 recommend_upload 中的文件类型检查
# 原代码：
if not file.filename.lower().endswith(".csv"):
    raise HTTPException(status_code=400, detail="仅支持 CSV 格式文件")

# 改为：
ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
if ext not in ("csv", "xlsx", "xls"):
    raise HTTPException(status_code=400, detail="仅支持 CSV 和 Excel 格式")
```

### 3.3 依赖确认

```bash
# Data_processing/requirements.txt 已包含:
# pandas          # 数据处理
# openpyxl        # Excel 支持
# spacy           # NLP 解析
# fastapi         # Web 框架
# uvicorn         # ASGI 服务器
# openai          # LLM API 客户端
# python-dotenv   # 环境变量
# python-multipart # 文件上传
```

---

## 四、前端改造：从静态页面到对话推荐

### 4.1 改造要点

当前 `UploadPage.tsx` 的问题：
- 只接受图片上传（`accept="image/*"`）→ 需要改为 Excel/CSV
- `handleSubmit` 是假动作（3 秒后自动清空）→ 需要真实调用 API
- 没有推荐结果的展示区域
- 没有对话交互能力

### 4.2 改造后的页面结构

```tsx
// RecommendPage.tsx — 新的推荐对话页面（核心逻辑）
import { useState, useRef } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  recommendations?: RecommendationResult[];
}

export function RecommendPage() {
  const [sessionId, setSessionId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [dataReady, setDataReady] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ① 上传数据（Excel/CSV/文字）
  const handleDataUpload = async (file?: File, text?: string) => {
    setLoading(true);
    const formData = new FormData();
    if (file) formData.append('file', file);
    if (text) formData.append('room_text', text);
    formData.append('user_query', '数据分析');  // 初始请求

    const res = await fetch('/api/recommend/chat', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    setSessionId(data.session_id);
    setDataReady(true);
    setMessages([{
      role: 'assistant',
      content: `已解析 ${data.rooms_count} 个房间数据。您现在可以向我描述您的需求，我会为您推荐最合适的房间。`,
    }]);
    setLoading(false);
  };

  // ② 发送对话消息
  const handleSendMessage = async () => {
    if (!input.trim() || !sessionId) return;

    const userMsg = input;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setLoading(true);

    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('user_query', userMsg);

    const res = await fetch('/api/recommend/chat', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    setMessages(prev => [...prev, {
      role: 'assistant',
      content: data.ai_response,
      recommendations: data.recommendations,
    }]);
    setLoading(false);
  };

  // ③ 渲染
  return (
    <div className="max-w-3xl mx-auto p-8">
      {/* 未上传数据：显示上传区 */}
      {!dataReady && (
        <div className="space-y-8">
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={(e) => e.target.files?.[0] && handleDataUpload(e.target.files[0])}
          />
          {/* 或粘贴文字 */}
          <textarea placeholder="或者在这里粘贴房间描述..." />
        </div>
      )}

      {/* 已上传：显示对话区 */}
      {dataReady && (
        <>
          {/* 消息列表 */}
          <div className="space-y-6 mb-8">
            {messages.map((msg, i) => (
              <div key={i} className={msg.role === 'user' ? 'text-right' : ''}>
                <div className="inline-block max-w-[80%] p-4 rounded-2xl bg-gray-100">
                  <p>{msg.content}</p>
                  {/* 推荐结果卡片 */}
                  {msg.recommendations && (
                    <div className="mt-4 space-y-3">
                      {msg.recommendations.map((r) => (
                        <div key={r.room_id}
                             className="bg-white p-4 rounded-xl shadow-sm">
                          <div className="flex justify-between items-center">
                            <span className="font-bold text-lg">房间 {r.room_id}</span>
                            <span className="text-blue-600 font-bold">
                              {Math.round(r.final_score * 100)}%
                            </span>
                          </div>
                          <div className="text-sm text-gray-500 mt-1">
                            {r.reasons?.join(' · ')}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && <div>思考中…</div>}
          </div>

          {/* 输入框 */}
          <div className="flex gap-4">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="描述您的需求，例如：我需要一个4人的安静房间，有投影仪…"
              className="flex-1 p-4 border rounded-xl"
            />
            <button onClick={handleSendMessage} disabled={loading}>
              发送
            </button>
          </div>
        </>
      )}
    </div>
  );
}
```

实际实现时，前端改造可以一步到位直接修改 `UploadPage.tsx`，或者新增一个 `RecommendPage.tsx` 并在 `routes.tsx` 中注册路由。

---

## 五、Docker 部署步骤

### 5.1 前提条件

- ✅ 一台云主机（Ubuntu 22.04，4 核 8 GB 推荐）
- ✅ 已安装 Docker + Docker Compose
- ✅ 域名已购买（如 `naviroom.cn`），DNS A 记录指向云主机 IP
- ✅ DeepSeek API Key（或其它兼容 OpenAI 的 LLM API）

### 5.2 部署步骤（按顺序执行）

```bash
# ==================== Step 0: SSH 登录云主机 ====================
ssh root@<your-server-ip>

# ==================== Step 1: 安装 Docker ====================
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker $USER
newgrp docker

# ==================== Step 2: 克隆项目 ====================
cd /opt
git clone <your-git-repo-url> naviroom
cd naviroom

# ==================== Step 3: 创建 Docker 相关文件 ====================
# 根据 DOCKER_DEPLOY.md 创建所有 Dockerfile 和配置
# （或者如果这些文件已在仓库中，跳过此步骤）

mkdir -p docker/{api,frontend,nginx,data-pipeline,mysql/init}

# ... 创建各 Dockerfile 和配置文件（详见 DOCKER_DEPLOY.md）...

# ==================== Step 4: 配置环境变量 ====================
cp .env.docker .env
vim .env
# 必填项：
#   MYSQL_ROOT_PASSWORD=<强密码>
#   DB_PASSWORD=<强密码>
#   SECRET_KEY=$(openssl rand -hex 32)
#   LLM_API_KEY=sk-xxxxxxxx    ← DeepSeek API Key
# 可选：
#   RECO_SEMANTIC_MODE=hybrid   ← 推荐模式

# ==================== Step 5: 启动服务 ====================
# 启动 MySQL + API
docker compose up -d mysql
# 等待 MySQL healthy（约 30 秒）
docker compose ps

# 构建并启动 API
docker compose up -d --build api
docker compose logs -f api  # 等待启动完成，Ctrl+C 退出

# 验证 API
curl http://localhost:8000/healthz
# → {"status":"ok"}

# 初始化数据（可选——也可以让用户自己上传）
docker compose --profile init run --rm data-pipeline

# 构建并启动前端
docker compose up -d --build frontend

# 验证全栈
curl http://localhost:3000/   # 前端页面
curl http://localhost:8000/healthz  # API 健康

# ==================== Step 6: 测试推荐接口 ====================
# 测试上传 + 推荐
curl -X POST http://localhost:8000/recommend/upload \
  -F "user_query=需要一个4人安静房间带投影仪" \
  -F "room_text=R1124, floor 1, capacity 4, has_screen=Y, has_whiteboard=Y; R2201, floor 2, capacity 30, has_projector=Y" \
  -F 'requirements={"capacity":4}'

# 测试对话推荐
curl -X POST http://localhost:8000/recommend/chat \
  -F "user_query=我需要一个安静的房间" \
  -F "room_text=R1124, capacity 4, has_screen=Y, has_whiteboard=Y; R2201, capacity 30, has_projector=Y"
# → 返回 session_id、ai_response、recommendations

# 测试多轮对话
curl -X POST http://localhost:8000/recommend/chat \
  -F "session_id=<上一步返回的 session_id>" \
  -F 'user_query=最好是2楼的'
# → 基于已有房间的更新推荐
```

---

## 六、域名与外部访问配置

### 6.1 DNS 设置

在域名 DNS 管理面板中添加：

| 类型 | 主机记录 | 记录值 | TTL |
|:---:|------|------|:---:|
| A | `@` | 云主机公网 IP | 600 |
| A | `www` | 云主机公网 IP | 600 |

### 6.2 防火墙开放端口

```bash
# 云主机安全组/防火墙规则
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 6.3 生产模式启动（含 Nginx + TLS）

```bash
# 1. 获取 TLS 证书（使用 Let's Encrypt）
sudo apt install -y certbot
sudo certbot certonly --standalone -d naviroom.cn -d www.naviroom.cn
# 证书路径：/etc/letsencrypt/live/naviroom.cn/fullchain.pem
#   密钥路径：/etc/letsencrypt/live/naviroom.cn/privkey.pem

# 2. 更新 .env 中的 TLS 路径
echo "TLS_CERT_DIR=/etc/letsencrypt/live/naviroom.cn" >> .env

# 3. 启动 Nginx + 生产配置
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build nginx

# 4. 验证外部访问
curl -I https://naviroom.cn/
# → HTTP/2 200

# 5. 设置自动续期
sudo crontab -e
# 添加：
# 0 3 * * * certbot renew --quiet && docker compose restart nginx
```

### 6.4 不使用域名的备选方案

如果没有域名，可以用云主机公网 IP 直接访问：

```bash
# 开发模式下，直接暴露端口
docker compose up -d --build api frontend

# 然后在安全组开放 3000 和 8000 端口
# 用户访问: http://<云主机IP>:3000
# API 地址: http://<云主机IP>:8000
```

> ⚠️ 不推荐生产环境这样做，因为没有 HTTPS 加密。

---

## 七、验证流程

### 7.1 端到端验证脚本

```bash
#!/bin/bash
# e2e_test.sh — 部署后完整验证
set -e
BASE_URL="${1:-http://localhost:8000}"

echo "=== NaviRoom 端到端验证 ==="
echo "目标: ${BASE_URL}"
echo ""

# 1. 健康检查
echo "[1/5] 健康检查..."
curl -fsS "${BASE_URL}/healthz" | grep -q "ok" && echo "  ✅ 通过" || echo "  ❌ 失败"

# 2. 文字描述 → 推荐
echo "[2/5] 文字描述 + 推荐..."
RESP=$(curl -fsS -X POST "${BASE_URL}/recommend/upload" \
  -F 'user_query=需要一个4人安静房间带投影仪' \
  -F 'room_text=R1124, floor 1, capacity 4, has_screen=Y, has_whiteboard=Y; R2201, floor 2, capacity 30, has_projector=Y')
RECO_COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
if [ "$RECO_COUNT" -ge 1 ]; then
    echo "  ✅ 通过 (返回 ${RECO_COUNT} 个推荐)"
else
    echo "  ❌ 失败 (推荐为空)"
fi

# 3. 对话推荐（首次 + 创建会话）
echo "[3/5] 对话推荐..."
CHAT_RESP=$(curl -fsS -X POST "${BASE_URL}/recommend/chat" \
  -F 'user_query=需要一个安静的房间' \
  -F 'room_text=R1124, capacity 4, has_screen=Y, has_whiteboard=Y; R2201, capacity 30, has_projector=Y')
SESSION_ID=$(echo "$CHAT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
if [ -n "$SESSION_ID" ]; then
    echo "  ✅ 通过 (session_id: ${SESSION_ID})"
else
    echo "  ❌ 失败 (无 session_id)"
fi

# 4. 多轮对话
echo "[4/5] 多轮对话..."
CHAT_RESP2=$(curl -fsS -X POST "${BASE_URL}/recommend/chat" \
  -F "session_id=${SESSION_ID}" \
  -F 'user_query=最好是2楼的')
HISTORY_COUNT=$(echo "$CHAT_RESP2" | python3 -c "import sys,json; print(json.load(sys.stdin)['history_count'])")
if [ "$HISTORY_COUNT" -ge 2 ]; then
    echo "  ✅ 通过 (对话轮次: ${HISTORY_COUNT})"
else
    echo "  ❌ 失败 (对话历史未更新)"
fi

# 5. 前端可达性
echo "[5/5] 前端页面..."
curl -fsS -o /dev/null http://localhost:3000/ && echo "  ✅ 通过" || echo "  ❌ 失败"

echo ""
echo "=== 验证完成 ==="
```

### 7.2 完整的用户体验验证

```bash
# 模拟真实用户操作流程：

# Step A: 用户打开网页
# → 浏览器访问 https://naviroom.cn → 看到首页 → 点击"Get Started"

# Step B: 上传 Excel + 首次提问
curl -X POST https://naviroom.cn/api/recommend/chat \
  -F "file=@/path/to/my_rooms.xlsx" \
  -F "user_query=帮我看看有哪些适合小组讨论的房间？"

# 返回：
# {
#   "session_id": "a1b2c3d4e5f6",
#   "ai_response": "已解析 50 个房间数据。为您推荐以下适合小组讨论的房间：...",
#   "recommendations": [
#     {"room_id": "R2201", "final_score": 0.92, "reasons": ["匹配容量", "有投影仪"]},
#     ...
#   ],
#   "rooms_count": 50
# }

# Step C: 追问细化条件
curl -X POST https://naviroom.cn/api/recommend/chat \
  -F "session_id=a1b2c3d4e5f6" \
  -F "user_query=最好是下午有空的那种，我们3点要开会"

# 返回更新后的推荐（筛选了下午可用的房间）

# Step D: 继续调整
curl -X POST https://naviroom.cn/api/recommend/chat \
  -F "session_id=a1b2c3d4e5f6" \
  -F "user_query=有没有带电视的？没有投影仪也行"

# 返回基于新条件的推荐
```

### 7.3 检查清单

部署完成后逐项确认：

- [ ] `curl https://<域名>/healthz` 返回 `{"status":"ok"}`
- [ ] `curl https://<域名>/` 返回前端 HTML 页面（非 502/404）
- [ ] 浏览器访问域名，页面正常加载（CSS/JS 不 404）
- [ ] 上传 Excel 文件 + 文字查询，返回推荐结果
- [ ] 多轮对话：session_id 保持不变，历史正确累积
- [ ] LLM 模式正常：`RECO_SEMANTIC_MODE=hybrid` 时推荐理由包含 LLM 分析
- [ ] 无 LLM 时降级正常：不设置 API Key，推荐仍返回结果（走本地匹配）
- [ ] 前端静态资源带 hash + 长期缓存
- [ ] HTTPS 证书有效（浏览器地址栏无警告）

---

## 总结：最小可行部署的步骤清单

如果只做最核心的事情（让外部用户能访问网页、上传数据、对话推荐），按这个清单走：

```
□ 1. 准备云主机 + 域名 DNS 解析
□ 2. 安装 Docker
□ 3. 克隆项目，创建 Docker 文件
□ 4. 在 server.py 中添加 /recommend/chat 端点（约 100 行）
□ 5. 修改 UploadPage.tsx 为对话推荐界面（约 150 行）
□ 6. 配置 .env（重点是 LLM_API_KEY）
□ 7. docker compose up -d
□ 8. certbot 获取 TLS 证书
□ 9. docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
□ 10. 浏览器访问验证
```

预计总工时：**2-4 小时**（假设 Docker 文件已准备好，只需补充 chat 端点和前端改造）。

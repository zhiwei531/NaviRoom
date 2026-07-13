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
    pandas==2.2.3 \
    pydantic-settings==2.9.1

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

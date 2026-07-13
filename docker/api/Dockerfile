# ============================================================
# NaviRoom API 服务
# 基于 Python 3.11，运行 FastAPI 应用
# 国内构建：docker build --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple ...
# ============================================================
FROM python:3.11-slim-bookworm

# pip 镜像（默认清华源，海外部署可覆盖为 https://pypi.org/simple）
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

# 系统依赖（腾讯云 Ubuntu 默认走内网镜像，无需特殊配置）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------- 依赖安装 ----------
COPY data_processing/requirements.txt /app/requirements-data.txt

RUN pip install --no-cache-dir \
    -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED_HOST} \
    -r /app/requirements-data.txt && \
    pip install --no-cache-dir \
    -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED_HOST} \
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

# spaCy 英文模型（通过 pip 安装 wheel，走镜像；失败则回退到 spacy download）
RUN pip install --no-cache-dir \
    -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED_HOST} \
    "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl" 2>/dev/null || \
    python -m spacy download en_core_web_sm

# ---------- 应用代码 ----------
COPY data_processing/ /app/data_processing/
COPY recommendation/ /app/recommendation/

# ---------- 运行时配置 ----------
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

RUN useradd --create-home --shell /bin/bash naviroom && \
    chown -R naviroom:naviroom /app
USER naviroom

CMD ["uvicorn", "recommendation.server:app", "--host", "0.0.0.0", "--port", "8000"]

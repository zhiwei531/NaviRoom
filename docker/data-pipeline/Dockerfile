# ============================================================
# NaviRoom 数据管道 — 一次性运行容器
# 用于执行数据清洗流水线，生成结构化 JSON 数据集
# ============================================================
FROM python:3.11-slim-bookworm

ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Data_processing/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir \
    -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED_HOST} \
    -r /app/requirements.txt && \
    pip install --no-cache-dir \
    -i ${PIP_INDEX} --trusted-host ${PIP_TRUSTED_HOST} \
    "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl" 2>/dev/null || \
    python -m spacy download en_core_web_sm

COPY Data_processing/ /app/Data_processing/

VOLUME ["/app/Data_processing/output"]

COPY docker/data-pipeline/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

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

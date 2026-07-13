#!/bin/bash
# NaviRoom 数据管道入口
# 通过环境变量控制输入输出
set -e

echo "=========================================="
echo "  NaviRoom Data Pipeline"
echo "=========================================="

# 默认值
ROOMS_INPUT="${ROOMS_INPUT:-Data_processing/data/dku_room_data/rooms.csv}"
RESERVATIONS_INPUT="${RESERVATIONS_INPUT:-}"
OUTPUT_PATH="${OUTPUT_PATH:-Data_processing/output/dku_dataset.json}"

# 构建命令
CMD="python Data_processing/scripts/pipeline.py"
CMD="$CMD --rooms ${ROOMS_INPUT}"
CMD="$CMD --output ${OUTPUT_PATH}"

if [ -n "$RESERVATIONS_INPUT" ]; then
    CMD="$CMD --reservations ${RESERVATIONS_INPUT}"
    echo "[INFO] 预订数据: ${RESERVATIONS_INPUT}"
fi

if [ "${SAVE_TO_DB:-false}" = "true" ]; then
    CMD="$CMD --save-to-db --db-password ${DB_PASSWORD}"
    echo "[INFO] 将写入 MySQL 数据库"
fi

echo "[INFO] 房间数据: ${ROOMS_INPUT}"
echo "[INFO] 输出路径: ${OUTPUT_PATH}"
echo "[RUN]  $CMD"
echo ""

exec $CMD

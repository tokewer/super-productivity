#!/usr/bin/env bash
# ==============================================================================
# SuperSync 数据库灾难恢复脚本
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
DB_CONTAINER="supersync-postgres"
POSTGRES_USER="${POSTGRES_USER:-supersync}"
POSTGRES_DB="${POSTGRES_DB:-supersync}"

if [ $# -lt 1 ]; then
    echo "使用方法: $0 <备份文件路径.sql.gz>"
    echo "可用备份列表:"
    ls -lh "${BACKUP_DIR}"/supersync_*.sql.gz 2>/dev/null || echo "（暂无备份）"
    exit 1
fi

RESTORE_FILE="$1"

if [ ! -f "${RESTORE_FILE}" ]; then
    echo "[ERROR] 指定的备份文件不存在: ${RESTORE_FILE}" >&2
    exit 1
fi

echo "================================================================="
echo " 警告: 恢复操作将覆盖当前数据库中的所有同步记录！"
echo " 目标备份: ${RESTORE_FILE}"
echo "================================================================="
read -p "确认继续恢复? (输入 yes 确认): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    echo "操作已取消。"
    exit 0
fi

echo "[INFO] 停止应用容器以防并发写入..."
docker compose stop supersync || true

echo "[INFO] 导入数据库备份..."
gunzip -c "${RESTORE_FILE}" | docker exec -i "${DB_CONTAINER}" psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "[INFO] 重启 SuperSync 应用服务..."
docker compose start supersync

echo "[OK] 数据库恢复完成！"

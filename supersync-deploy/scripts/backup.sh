#!/usr/bin/env bash
# ==============================================================================
# SuperSync PostgreSQL 数据库自动备份脚本
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
DB_CONTAINER="supersync-postgres"
POSTGRES_USER="${POSTGRES_USER:-supersync}"
POSTGRES_DB="${POSTGRES_DB:-supersync}"

mkdir -p "${BACKUP_DIR}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/supersync_${TIMESTAMP}.sql.gz"
TEMP_FILE="${BACKUP_DIR}/.tmp_supersync_${TIMESTAMP}.sql.gz"

echo "[INFO] 开始备份 SuperSync 数据库..."
if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    echo "[ERROR] 容器 ${DB_CONTAINER} 未运行！" >&2
    exit 1
fi

docker exec -t "${DB_CONTAINER}" pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip -c > "${TEMP_FILE}"

# 验证备份非空
if [ ! -s "${TEMP_FILE}" ]; then
    echo "[ERROR] 备份文件为空，生成失败！" >&2
    rm -f "${TEMP_FILE}"
    exit 1
fi

mv "${TEMP_FILE}" "${BACKUP_FILE}"
SHA256=$(sha256sum "${BACKUP_FILE}" | awk '{print $1}')
echo "[OK] 备份成功: ${BACKUP_FILE}"
echo "[OK] 文件哈希 (SHA-256): ${SHA256}"
echo "[OK] 文件大小: $(du -h "${BACKUP_FILE}" | cut -f1)"

# 清理超过保留期的旧备份（确保至少保留最近 3 份）
TOTAL_BACKUPS=$(ls -1 "${BACKUP_DIR}"/supersync_*.sql.gz 2>/dev/null | wc -l)
if [ "${TOTAL_BACKUPS}" -gt 3 ]; then
    echo "[INFO] 清理 ${RETENTION_DAYS} 天前的旧备份..."
    find "${BACKUP_DIR}" -name "supersync_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} +
fi

echo "[DONE] 备份流程结束。"

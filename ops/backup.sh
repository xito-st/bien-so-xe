#!/bin/bash
# ==============================================================================
# Script tự động sao lưu CSDL PostgreSQL định kỳ (Runbook NFR-005, NFR-006)
# Chạy trên máy chủ VPS Linux qua cron job hằng ngày (ví dụ 01:00 AM)
# ==============================================================================

set -euo pipefail

# Thư mục lưu trữ bản sao lưu
BACKUP_DIR="$(dirname "$0")/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/biensoxe_backup_${TIMESTAMP}.dump"
DB_CONTAINER="biensoxe-db"
DB_NAME="biensoxe_prod"
DB_USER="postgres"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Bắt đầu sao lưu CSDL '${DB_NAME}' từ container '${DB_CONTAINER}'..."

# Thực hiện pg_dump định dạng custom (-Fc) nén tối ưu
docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_FILE"

# Kiểm tra tính toàn vẹn của tệp sao lưu
if docker exec -i "$DB_CONTAINER" pg_restore --list < "$BACKUP_FILE" > /dev/null 2>&1; then
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sao lưu THÀNH CÔNG: ${BACKUP_FILE} (Dung lượng: ${FILE_SIZE})"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] CẢNH BÁO: Tệp sao lưu không hợp lệ!" >&2
    exit 1
fi

# Dọn dẹp các bản sao lưu cũ hơn 30 ngày (đảm bảo NFR-006)
find "$BACKUP_DIR" -type f -name "biensoxe_backup_*.dump" -mtime +30 -exec rm -f {} \;
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Đã dọn dẹp các bản sao lưu quá 30 ngày."


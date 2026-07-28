#!/usr/bin/env bash
# Restore from a backup directory produced by backup.sh
# Usage: ./deploy/restore.sh /var/backups/vapt/20250115-020000
set -euo pipefail
DEST="${1:?usage: $0 <backup-dir>}"
source "$(dirname "$0")/../.env" 2>/dev/null || true

if [[ ! -d "$DEST" ]]; then
    echo "No such backup: $DEST" >&2
    exit 1
fi
echo "[restore] from $DEST"
echo "[restore] this will OVERWRITE the live database. Type 'yes' to continue."
read -r ans
[[ "$ans" == "yes" ]] || { echo "aborted"; exit 1; }

echo "[restore] dropping & recreating database…"
docker exec vapt-postgres psql -U "${POSTGRES_USER:-vapt}" -d postgres \
    -c "DROP DATABASE ${POSTGRES_DB:-vapt};" \
    -c "CREATE DATABASE ${POSTGRES_DB:-vapt} OWNER ${POSTGRES_USER:-vapt};"

echo "[restore] loading db dump…"
gunzip -c "$DEST/db.sql.gz" | docker exec -i vapt-postgres psql \
    -U "${POSTGRES_USER:-vapt}" -d "${POSTGRES_DB:-vapt}" -v ON_ERROR_STOP=1

echo "[restore] minio bucket mirror…"
docker run --rm --network vapt-platform_default \
    -v "$DEST/minio:/in" \
    minio/mc:latest \
    sh -c "
        mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-vapt} ${MINIO_ROOT_PASSWORD:-changeme};
        mc mirror --overwrite --remove /in local/${MINIO_BUCKET:-vapt-evidence};
    "

echo "[restore] done — restart backend to re-establish connections"
docker compose restart backend worker mcp

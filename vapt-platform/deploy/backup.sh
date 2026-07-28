#!/usr/bin/env bash
# Nightly backup: pg_dump + MinIO bucket mirror.
# Add to cron:  0 2 * * *  /opt/vapt/deploy/backup.sh
set -euo pipefail

source "$(dirname "$0")/../.env" 2>/dev/null || true

BACKUP_PATH="${BACKUP_PATH:-/var/backups/vapt}"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"
TS="$(date -u +%Y%m%d-%H%M%S)"
DEST="${BACKUP_PATH}/${TS}"
mkdir -p "$DEST"

echo "[backup] destination: $DEST"

# 1) Postgres
echo "[backup] pg_dump…"
docker exec vapt-postgres pg_dump -U "${POSTGRES_USER:-vapt}" "${POSTGRES_DB:-vapt}" \
    | gzip > "${DEST}/db.sql.gz"

# 2) MinIO bucket mirror
echo "[backup] minio mirror…"
docker run --rm --network vapt-platform_default \
    -v "${DEST}:/out" \
    minio/mc:latest \
    sh -c "
        mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-vapt} ${MINIO_ROOT_PASSWORD:-changeme};
        mc mirror --remove --overwrite local/${MINIO_BUCKET:-vapt-evidence} /out/minio;
    "

# 3) Manifest
cat > "${DEST}/manifest.json" <<EOF
{
  "created_at": "$(date -u --iso-8601=seconds)",
  "db_dump": "db.sql.gz",
  "minio_bucket": "${MINIO_BUCKET:-vapt-evidence}",
  "retention_days": ${RETENTION}
}
EOF

# 4) Prune old backups
echo "[backup] pruning…"
find "$BACKUP_PATH" -maxdepth 1 -mindepth 1 -type d -mtime "+${RETENTION}" -exec rm -rf {} +

echo "[backup] done"

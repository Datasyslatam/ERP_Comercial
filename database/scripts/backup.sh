#!/usr/bin/env sh
# Copia de seguridad lógica de PostgreSQL (formato custom, comprimido) con suma SHA-256 y retención.
# Uso: DATABASE_URL=postgresql://user:pass@host:5432/erp BACKUP_DIR=/backups RETENTION_DAYS=30 ./backup.sh
set -eu
: "${DATABASE_URL:?Defina DATABASE_URL}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
URL=$(printf '%s' "$DATABASE_URL" | sed 's#postgresql+psycopg://#postgresql://#')
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE="$BACKUP_DIR/erp_$STAMP.dump"
mkdir -p "$BACKUP_DIR"
pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$FILE" "$URL"
sha256sum "$FILE" > "$FILE.sha256"
pg_restore --list "$FILE" > /dev/null   # verificación de legibilidad del archivo
find "$BACKUP_DIR" -name 'erp_*.dump*' -mtime +"$RETENTION_DAYS" -delete
echo "Respaldo OK: $FILE ($(du -h "$FILE" | cut -f1))"

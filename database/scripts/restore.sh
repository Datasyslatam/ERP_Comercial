#!/usr/bin/env sh
# Restaura un respaldo en una base de datos DESTINO (nunca sobre producción sin ventana aprobada).
# Uso: TARGET_DATABASE_URL=postgresql://user:pass@host:5432/erp_restore ./restore.sh /backups/erp_XXXX.dump
set -eu
FILE="${1:?Indique el archivo .dump}"
: "${TARGET_DATABASE_URL:?Defina TARGET_DATABASE_URL}"
URL=$(printf '%s' "$TARGET_DATABASE_URL" | sed 's#postgresql+psycopg://#postgresql://#')
if [ -f "$FILE.sha256" ]; then sha256sum -c "$FILE.sha256"; fi
pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error --dbname="$URL" "$FILE"
echo "Restauración completada en destino"

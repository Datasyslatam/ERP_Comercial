#!/usr/bin/env sh
# Restaura un respaldo en una base de datos DESTINO (nunca sobre producción sin ventana aprobada).
# Uso: TARGET_DATABASE_URL=postgresql://user:pass@host:5432/erp_restore ./restore.sh /backups/erp_XXXX.dump
#
# Se detiene en el primer error. El cliente (pg_dump/pg_restore) puede ser más nuevo que el servidor destino: desde
# la v17 el respaldo fija transaction_timeout, parámetro que un servidor anterior rechaza, por lo que esa línea se
# omite solo en esos servidores. No se admite restaurar en un servidor más antiguo que el de origen del respaldo.
set -eu
FILE="${1:?Indique el archivo .dump}"
: "${TARGET_DATABASE_URL:?Defina TARGET_DATABASE_URL}"
URL=$(printf '%s' "$TARGET_DATABASE_URL" | sed 's#postgresql+psycopg://#postgresql://#')
if [ -f "$FILE.sha256" ]; then sha256sum -c "$FILE.sha256"; fi

TOC=$(pg_restore --list "$FILE")
SRC_MAJOR=$(printf '%s\n' "$TOC" | sed -n 's/^;[[:space:]]*Dumped from database version: \([0-9]*\).*/\1/p' | head -n 1)
DST_NUM=$(psql --no-psqlrc -At -d "$URL" -c "show server_version_num")
DST_MAJOR=$((DST_NUM / 10000))
echo "Respaldo de PostgreSQL ${SRC_MAJOR:-?} hacia servidor PostgreSQL $DST_MAJOR con $(pg_restore --version)"
if [ -n "$SRC_MAJOR" ] && [ "$DST_MAJOR" -lt "$SRC_MAJOR" ]; then
  echo "ERROR: el destino (PostgreSQL $DST_MAJOR) es más antiguo que el origen del respaldo (PostgreSQL $SRC_MAJOR)" >&2
  exit 1
fi

# Archivo temporal privado: contiene todos los datos del respaldo sin comprimir y se borra al terminar.
SQL=$(mktemp)
trap 'rm -f "$SQL"' EXIT
pg_restore --clean --if-exists --no-owner --no-privileges --file="$SQL" "$FILE"
if [ "$DST_MAJOR" -lt 17 ]; then
  # Solo en el encabezado: nunca debe tocar los datos de las tablas.
  sed -i '1,100{/^SET transaction_timeout = 0;$/d;}' "$SQL"
fi
psql --no-psqlrc -q -v ON_ERROR_STOP=1 -d "$URL" -f "$SQL"
echo "Restauración completada en destino"

#!/usr/bin/env sh
# Prueba periódica de restauración: restaura el último respaldo en una base temporal y compara conteos
# de tablas críticas y el balance contable. Programar al menos mensualmente (ver docs/administracion.md).
set -eu
: "${DATABASE_URL:?}"; : "${RESTORE_TEST_URL:?}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
LAST=$(ls -1t "$BACKUP_DIR"/erp_*.dump | head -n1)
SRC=$(printf '%s' "$DATABASE_URL" | sed 's#postgresql+psycopg://#postgresql://#')
DST=$(printf '%s' "$RESTORE_TEST_URL" | sed 's#postgresql+psycopg://#postgresql://#')
TARGET_DATABASE_URL="$DST" "$(dirname "$0")/restore.sh" "$LAST"
Q="select (select count(*) from journal_entries)||'/'||(select count(*) from stock_moves)||'/'||
   (select coalesce(sum(debit-credit),0) from journal_lines)"
echo "Origen:  $(psql -At "$SRC" -c "$Q")  (puede diferir si hubo transacciones después del respaldo)"
echo "Destino: $(psql -At "$DST" -c "$Q")"
psql -At "$DST" -c "select 'balance_ok' where (select coalesce(sum(debit-credit),0) from journal_lines) = 0" | grep -q balance_ok
echo "Prueba de restauración OK ($LAST)"

#!/usr/bin/env sh
# api    → aplica migraciones (si RUN_MIGRATIONS=1) y arranca uvicorn
# worker → procesa bandeja de salida (facturación electrónica) y alertas
# otro   → se ejecuta tal cual (p. ej. "python -m app.cli init")
set -eu
case "${1:-api}" in
  api)
    if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then alembic upgrade head; fi
    exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" \
      --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" --no-server-header
    ;;
  worker)
    exec python -m app.worker
    ;;
  *)
    exec "$@"
    ;;
esac

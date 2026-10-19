#!/usr/bin/env sh
# api    → aplica migraciones (si RUN_MIGRATIONS=1) y arranca uvicorn; con RUN_WORKER=1 corre además el
#          worker en el mismo contenedor (PaaS donde un volumen no se comparte entre servicios, p. ej. Railway:
#          el worker guarda el XML de facturación y la API lo sirve, ambos deben ver el mismo /data/storage)
# worker → procesa bandeja de salida (facturación electrónica) y alertas
# otro   → se ejecuta tal cual (p. ej. "python -m app.cli init")
set -eu
case "${1:-api}" in
  api)
    if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then alembic upgrade head; fi
    if [ "${RUN_WORKER:-0}" = "1" ]; then
      # Se relanza si termina por un error; muere con el contenedor cuando uvicorn (PID 1) se detiene.
      ( while true; do python -m app.worker || true; sleep 5; done ) &
    fi
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

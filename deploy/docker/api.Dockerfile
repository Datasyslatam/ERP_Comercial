# Imagen del backend (API y worker). Contexto de construcción: raíz del repositorio.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/srv
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 erp
WORKDIR /srv
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY backend/app ./app
COPY integrations ./integrations
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY database/scripts ./scripts
COPY deploy/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/prepend_sys_path = backend ./prepend_sys_path = ./' alembic.ini \
    && chmod +x /usr/local/bin/entrypoint.sh ./scripts/*.sh \
    && mkdir -p /data/storage && chown -R erp:erp /data
USER erp
ENV STORAGE_PATH=/data/storage PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:${PORT}/health/live || exit 1
ENTRYPOINT ["entrypoint.sh"]
CMD ["api"]

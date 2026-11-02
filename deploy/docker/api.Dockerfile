# Imagen del backend (API y worker). Contexto de construcción: raíz del repositorio.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/srv
# Cliente de PostgreSQL de la misma versión que el servidor de producción: pg_dump se niega a respaldar un servidor
# más nuevo que él. El de la distribución no sirve porque su versión cambia con la imagen base.
ARG PG_CLIENT_MAJOR=18
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && . /etc/os-release && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /etc/apt/keyrings/pgdg.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends "postgresql-client-${PG_CLIENT_MAJOR}" \
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

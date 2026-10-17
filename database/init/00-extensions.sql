-- Se ejecuta solo al crear el volumen de PostgreSQL por primera vez (docker-entrypoint-initdb.d).
-- El esquema lo crean las migraciones de Alembic; aquí solo ajustes de la base.
ALTER DATABASE erp SET timezone TO 'UTC';

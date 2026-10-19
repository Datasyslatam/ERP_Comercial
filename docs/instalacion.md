# Manual de instalación

## Requisitos mínimos

| Escenario | CPU | RAM | Disco | Notas |
|---|---|---|---|---|
| Pruebas / piloto (≤ 20 usuarios) | 2 vCPU | 4 GB | 40 GB SSD | Un solo servidor con Docker |
| Producción pequeña (≤ 80 usuarios, multisede) | 4 vCPU | 8 GB | 100 GB SSD + respaldo externo | `WEB_CONCURRENCY=4` |
| Producción mediana | 8 vCPU | 16 GB | BD gestionada (PostgreSQL 16) | API y worker en réplicas |

Software: Docker Engine 24+ con Compose v2 (o Docker Desktop). Para desarrollo sin Docker: Python 3.12+,
Node 20+, PostgreSQL 16.

Red: puertos **80 y 443** abiertos hacia el servidor (Caddy). La base de datos **no** se publica. Salida a
internet hacia Let's Encrypt y, cuando se contrate, hacia el proveedor tecnológico de facturación.

## A. Ejecución local (desarrollo)

```bash
python -m venv .venv
```
```bash
.venv/bin/pip install -r backend/requirements-dev.txt
```
Cree `.env` a partir de `.env.example` con `DATABASE_URL` y `TEST_DATABASE_URL` apuntando a un PostgreSQL 16
local (o `docker compose up -d db` publicando el puerto temporalmente). Luego:

```bash
alembic upgrade head
```
```bash
cd backend && python -m app.cli init && python -m app.cli create-company --code DLCO --name "Mi empresa" --tax-id 900123456 --dv 8 --country CO --withholding-agent
```
```bash
cd backend && python -m app.cli create-admin --email admin@miempresa.com --name "Administrador" --company DLCO --superadmin
```
```bash
cd backend && python -m app.cli seed-demo --company DLCO
```
(`seed-demo` es opcional y crea datos **sintéticos** con prefijo `DEMO-`; está bloqueado en producción.)

```bash
uvicorn app.main:app --app-dir backend --reload --port 8000
```
```bash
npm --prefix frontend install && npm --prefix frontend run dev
```
Abra http://localhost:5173 (Vite redirige `/api` al puerto 8000). Documentación de la API: http://localhost:8000/api/docs

Pruebas:
```bash
pytest -q
```
```bash
npm --prefix frontend test
```

## B. Servidor propio de la organización (Docker Compose)

1. Instale Docker y clone el repositorio en `/opt/datasys-erp`.
2. `cp .env.example .env` y defina: `POSTGRES_PASSWORD`, `JWT_SECRET` (48+ caracteres aleatorios),
   `SITE_ADDRESS` (dominio), `CORS_ORIGINS` (https://dominio). Permisos del archivo: `chmod 600 .env`.
3. Registre un DNS tipo A del dominio hacia la IP pública del servidor.
4. Construya y arranque:
```bash
docker compose --env-file .env up -d --build
```
5. Inicialice (solo la primera vez):
```bash
docker compose exec api python -m app.cli init
```
```bash
docker compose exec api python -m app.cli create-company --code DLCO --name "Razón social" --tax-id 900123456 --dv 8 --country CO --withholding-agent
```
```bash
docker compose exec -e ERP_ADMIN_PASSWORD api python -m app.cli create-admin --email admin@empresa.com --name "Administrador" --company DLCO
```
6. Verifique: `https://<dominio>/health/ready` debe devolver `schema_version`.

Caddy obtiene y renueva el certificado HTTPS automáticamente. Los datos persisten en los volúmenes
`pgdata` (BD), `storage` (adjuntos y XML fiscales) y `caddy_data` (certificados). Los respaldos diarios
quedan en `./backups` (cópielos fuera del servidor; ver manual de administración).

Monitoreo opcional: `docker compose --profile monitoring up -d prometheus` (Prometheus en 127.0.0.1:9090).

## C. Nube pública o privada (VM)

Mismo procedimiento que B sobre una VM (AWS EC2, Azure VM, GCP, OCI, OpenStack, VMware). Recomendado:
- Grupo de seguridad: entrada 80/443 desde internet; 22 solo desde IP administrativas.
- Disco con cifrado en reposo habilitado por el proveedor.
- Para mayor disponibilidad, sustituya el servicio `db` por PostgreSQL gestionado (RDS, Azure Database,
  Cloud SQL): elimine `db` del compose y defina `DATABASE_URL` con `sslmode=require`.
- Almacenamiento de respaldos en un bucket con versionado y retención (copie `./backups` con la CLI del proveedor).

## D. Railway (paso a paso)

1. Cree un proyecto en Railway y agregue **PostgreSQL** (plugin). Railway expone `DATABASE_URL`.
2. Conecte el repositorio y cree **dos servicios** desde el mismo repo (no hace falta un servicio Caddy aparte:
   la imagen de `web` ya es Caddy con el frontend compilado y el proxy hacia la API; el worker corre dentro de
   `api` con `RUN_WORKER=1`, porque un volumen de Railway no se comparte entre servicios y el worker guarda el
   XML de facturación que la API sirve):
   | Servicio | Dockerfile Path | Start Command | Healthcheck |
   |---|---|---|---|
   | `api` | `deploy/docker/api.Dockerfile` | `entrypoint.sh api` | `/health/ready` (timeout 120 s) |
   | `web` | `deploy/docker/web.Dockerfile` | — | `/` |

   Los mismos valores están en `deploy/railway/*.railway.json` como referencia; Railway ya no admite
   enlazar nuevos archivos *config-as-code*, así que se configuran en *Settings* de cada servicio.
   En ambos, **Root Directory vacío o `/`** (raíz del repositorio): los Dockerfile copian `backend/`,
   `frontend/` y `deploy/` desde la raíz. Con Root Directory `/frontend` el build falla con
   `"/frontend/package.json": not found`. Con *Dockerfile Path* definido Railway construye con Docker,
   no con Railpack, y la fuente debe ser el repositorio, no una imagen.
3. Variables de `api`:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}` (se normaliza al driver psycopg automáticamente)
   - `ENVIRONMENT=production`, `JWT_SECRET=<aleatorio 48+>`, `CORS_ORIGINS=https://<dominio-web>`
   - `HOST=::` (red privada de Railway), `PORT=8000`, `WEB_CONCURRENCY=2`, `TRUSTED_PROXY_COUNT=2`
     (borde de Railway + Caddy)
   - `RAILWAY_RUN_UID=0`: el volumen de Railway se monta como root y la imagen corre con un usuario sin
     privilegios; sin esta variable la API no puede escribir adjuntos en `/data/storage`.
   - `RUN_WORKER=1`: el worker (bandeja de salida de facturación y alertas) corre en el mismo contenedor y se
     relanza solo si falla. Mantenga **una** réplica de `api` mientras tenga volumen (Railway lo exige).
4. Variables de `web`: `SITE_ADDRESS=:8080`, `PORT=8080`, `API_UPSTREAM=api.railway.internal:8000`,
   `TRUSTED_PROXIES=0.0.0.0/0 ::/0` (el borde de Railway no usa IP privadas; sin esto todos los usuarios
   compartirían el límite de intentos de ingreso). `VITE_API_URL` no se usa: el navegador llama a `/api` en
   el mismo dominio y Caddy lo reenvía.
5. Genere un dominio público solo para `web` (Railway termina TLS). La API no necesita dominio público.
6. Volumen: adjunte un volumen a `api` montado en `/data/storage` (adjuntos y XML). Para escalar la API a
   varias réplicas habría que mover el almacenamiento a un bucket S3 compatible (pendiente listado en
   `pendientes-produccion.md`) y volver a separar el worker (`entrypoint.sh worker`, `RUN_MIGRATIONS=0`).
7. Inicialización: en `api` → *Shell* ejecute los comandos `python -m app.cli init`, `create-company` y
   `create-admin` del paso B.5.
8. Respaldos: habilite los backups del plugin PostgreSQL de Railway y, adicionalmente, programe un
   *cron service* con la imagen de `api` y el comando `scripts/backup.sh` hacia almacenamiento externo.

## E. Actualización de versiones sin pérdida de datos

1. Respaldo inmediato: `docker compose exec backup /scripts/backup.sh`.
2. `git pull` de la versión etiquetada; revise `migrations/versions` nuevas.
3. `docker compose --env-file .env up -d --build` — la API ejecuta `alembic upgrade head` al arrancar
   (`RUN_MIGRATIONS=1`). Las migraciones son transaccionales: si fallan, no se aplican parcialmente.
4. Verifique `/health/ready` (nueva `schema_version`) y revise logs: `docker compose logs -f api worker`.
5. Reversión: volver a la imagen anterior y, solo si la migración lo permite, `alembic downgrade -1`;
   en caso contrario restaurar el respaldo del paso 1.

## F. Recuperación ante fallos

| Falla | Acción |
|---|---|
| Caída de contenedor | `restart: unless-stopped` lo reinicia; revise `docker compose ps` y logs |
| Corrupción / borrado de datos | Restaurar último respaldo en base nueva (`restore.sh`), validar y conmutar `DATABASE_URL` |
| Pérdida del servidor | Nuevo servidor → pasos B.1–B.4 → restaurar respaldo externo → copiar volumen `storage` |
| Proveedor de facturación caído | El outbox reintenta; documentos quedan `pending/error` con alerta; reenvío manual |
| Certificado HTTPS | Caddy renueva solo; verifique puertos 80/443 y DNS |

Objetivos sugeridos: RPO ≤ 24 h con respaldos diarios (≤ 15 min con WAL/PITR de una BD gestionada);
RTO ≤ 4 h siguiendo este procedimiento.

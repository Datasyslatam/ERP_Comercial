# Novix ERP

**Novix ERP** (antes DATASYS ERP): ERP modular de **DATASYS LATAM GROUP**: compras, inventario, calidad, ventas, logística, operaciones,
contabilidad, facturación electrónica (Colombia / Venezuela), indicadores e importación de datos reales.

> **Estado**: listo para un entorno controlado de pruebas. La facturación electrónica opera con
> adaptadores **SANDBOX sin validez fiscal** hasta contratar el proveedor tecnológico DIAN y la imprenta
> digital SENIAT. Ver [pendientes para producción](docs/pendientes-produccion.md).

## Pila
FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · React 18 + TypeScript + Vite · Caddy (HTTPS) · Docker Compose.
Monolito modular con API REST documentada (OpenAPI), worker de integraciones y CI en GitHub Actions.

## Estructura
```
backend/        API FastAPI (app/core, app/modules/<dominio>, worker, CLI)
frontend/       SPA React + TypeScript
integrations/   adaptadores de facturación electrónica (contrato + DIAN + SENIAT + sandbox)
migrations/     migraciones Alembic (esquema + reglas de integridad en BD)
database/       inicialización y scripts de respaldo / restauración / prueba de restauración
tests/          pruebas de integración y unitarias contra PostgreSQL real
deploy/         Dockerfiles, Caddyfile, Railway, monitoreo
docs/           arquitectura, modelo ER, diccionario, API, manuales, pruebas, pendientes
```

## Inicio rápido (desarrollo)
```bash
pip install -r backend/requirements-dev.txt
```
```bash
alembic upgrade head
```
```bash
uvicorn app.main:app --app-dir backend --reload
```
```bash
npm --prefix frontend install && npm --prefix frontend run dev
```
Configuración, alta de empresa y administrador: [docs/instalacion.md](docs/instalacion.md).

## Desarrollo local en Windows (sin Docker)
Si Docker Desktop no está disponible, PostgreSQL 16 corre embebido (binarios de
[pgserver](https://pypi.org/project/pgserver/)) desde una carpeta persistente **fuera del repositorio y de Temp**:

```
%LOCALAPPDATA%\DatasysERP\
  pg\pginstall\bin\   pg_ctl, postgres, psql, pg_dump ...
  pg\data\            clúster: puerto 5433, usuario erp, bases erp y erp_test
  pg\pg.log           log de PostgreSQL
  logs\               salida de la API (api.out.log / api.err.log)
```

Cada día, o tras reiniciar el PC, ejecute desde la raíz del repositorio:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
```
El script arranca PostgreSQL (y elimina un `postmaster.pid` huérfano si el equipo se apagó sin detenerlo),
aplica `alembic upgrade head`, levanta uvicorn en segundo plano y espera a que
http://localhost:8000/health/ready responda `"status": "ok"`. Luego, en otra terminal:
```powershell
npm --prefix frontend run dev
```
y abra http://localhost:5173. Para detener la API y la base de datos con un apagado limpio:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-down.ps1
```
Opciones: `-DbOnly` (solo PostgreSQL), `-Reload` (uvicorn con recarga), `-NoMigrate`, `-ApiPort`, `-PgPort`,
`-PgHome` (o la variable de entorno `ERP_PG_HOME`) para otra carpeta del clúster.
Las credenciales viven solo en `.env` (no versionado): `DATABASE_URL` y `TEST_DATABASE_URL` apuntan a `127.0.0.1:5433`.
Por seguridad, `dev-up` se niega a migrar o arrancar la API si `ENVIRONMENT` no es `development`/`test` o si
`DATABASE_URL` no apunta a esta máquina (se revisan `.env` y las variables de entorno del sistema, que prevalecen).
PostgreSQL y la API escuchan solo en `127.0.0.1`, y el clúster exige contraseña (`scram-sha-256`).
Para la prueba de respaldo/restauración, `$env:PG_BIN = "$env:LOCALAPPDATA\DatasysERP\pg\pginstall\bin"`.

**Primera instalación en un equipo nuevo** (cuando `%LOCALAPPDATA%\DatasysERP\pg` no existe):
```powershell
py -3.11 -m venv "$env:LOCALAPPDATA\DatasysERP\pgserver-venv"
```
```powershell
& "$env:LOCALAPPDATA\DatasysERP\pgserver-venv\Scripts\pip" install pgserver==0.1.4
```
```powershell
Copy-Item -Recurse "$env:LOCALAPPDATA\DatasysERP\pgserver-venv\Lib\site-packages\pgserver\pginstall" "$env:LOCALAPPDATA\DatasysERP\pg\pginstall"
```
```powershell
& "$env:LOCALAPPDATA\DatasysERP\pg\pginstall\bin\initdb" -D "$env:LOCALAPPDATA\DatasysERP\pg\data" -U erp -W -A scram-sha-256 -E UTF8 --locale=C
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1 -DbOnly
```
```powershell
& "$env:LOCALAPPDATA\DatasysERP\pg\pginstall\bin\createdb" -h 127.0.0.1 -p 5433 -U erp erp
```
```powershell
& "$env:LOCALAPPDATA\DatasysERP\pg\pginstall\bin\createdb" -h 127.0.0.1 -p 5433 -U erp erp_test
```
Después copie `.env.example` a `.env` con `ENVIRONMENT=development` y la contraseña elegida en
`DATABASE_URL`/`TEST_DATABASE_URL` (puerto 5433), cree el entorno de la API
(`py -3.13 -m venv .venv` y `.venv\Scripts\pip install -r backend\requirements-dev.txt`) y siga con la configuración de empresa y administrador de [docs/instalacion.md](docs/instalacion.md).

## Pruebas
```bash
pytest -q
```
Resultados de la última ejecución: **64 backend + 9 frontend aprobadas, 0 fallidas**, cobertura 84 % —
detalle y pruebas no ejecutadas en [docs/pruebas.md](docs/pruebas.md).

## Documentación
| Documento | Contenido |
|---|---|
| [arquitectura.md](docs/arquitectura.md) | Decisiones, módulos y dependencias, procesos intermodulares, seguridad, topología híbrida |
| [modelo-er.md](docs/modelo-er.md) / [diccionario-datos.md](docs/diccionario-datos.md) | Generados desde el código (`python -m app.tools.gen_docs`) |
| [api.md](docs/api.md) / [openapi.json](docs/openapi.json) | Convenciones y mapa de la API |
| [instalacion.md](docs/instalacion.md) | Local, servidor propio, nube, Railway, actualizaciones, recuperación |
| [manual-usuario.md](docs/manual-usuario.md) | Operación por módulo |
| [administracion.md](docs/administracion.md) | Roles, políticas, parametrización fiscal, respaldos, monitoreo, retención |
| [fases.md](docs/fases.md) | Entregables por fase |
| [pendientes-produccion.md](docs/pendientes-produccion.md) | Lo que falta antes de producción |

# DATASYS ERP

ERP modular para **DATASYS LATAM GROUP**: compras, inventario, calidad, ventas, logística, operaciones,
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

## Pruebas
```bash
pytest -q
```
Resultados de la última ejecución: **63 backend + 5 frontend aprobadas, 0 fallidas**, cobertura 84 % —
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

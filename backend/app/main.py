"""Punto de entrada de la API del ERP (monolito modular)."""
from decimal import Decimal

from fastapi import APIRouter, FastAPI
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.middleware.cors import CORSMiddleware

from app.core.audit import register_audit_listener
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.http import install_middleware, setup_logging
from app.modules.accounting.fiscal_router import router as fiscal
from app.modules.accounting.router import router as accounting
from app.modules.documents.router import router as documents
from app.modules.einvoicing.router import router as einvoicing
from app.modules.iam.router import router as iam
from app.modules.imports.router import router as imports
from app.modules.inventory.router import router as inventory
from app.modules.kpi.router import router as kpi
from app.modules.logistics.router import router as logistics
from app.modules.masters.router import router as masters
from app.modules.operations.router import router as operations
from app.modules.org.router import health_router
from app.modules.org.router import router as org
from app.modules.purchasing.router import router as purchasing
from app.modules.quality.router import router as quality
from app.modules.sales.pricing_router import router as sales_pricing
from app.modules.sales.router import router as sales
from app.modules.trace.router import router as trace

# Los importes se serializan como texto para no perder precisión (FastAPI usa float por defecto).
ENCODERS_BY_TYPE[Decimal] = str

API_DESCRIPTION = """
Novix ERP: ERP modular de DATASYS LATAM GROUP.

* Autenticación: `POST /api/v1/auth/login` → `Authorization: Bearer <token>`.
* Contexto multiempresa: toda operación de negocio exige la cabecera `X-Company-Id`.
* Facturación electrónica: los adaptadores configurados por defecto son **SANDBOX** (sin validez fiscal).
"""


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_runtime()
    setup_logging()
    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, traces_sample_rate=0.05)
        except ImportError:  # pragma: no cover
            pass
    register_audit_listener()
    docs = settings.environment != "production"
    app = FastAPI(title=settings.app_name, version="1.0.0", description=API_DESCRIPTION,
                  docs_url="/api/docs" if docs else None, redoc_url="/api/redoc" if docs else None,
                  openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-Company-Id", "X-Request-Id",
                                      "Idempotency-Key"])
    install_middleware(app)
    register_error_handlers(app)
    api = APIRouter(prefix="/api/v1")
    for r in (iam, masters, org, purchasing, inventory, quality, sales, logistics, operations, accounting, einvoicing,
              kpi, imports, trace, documents, sales_pricing, fiscal):
        api.include_router(r)
    app.include_router(api)
    app.include_router(health_router)
    return app


app = create_app()

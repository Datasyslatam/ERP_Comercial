"""Errores de dominio y su traducción a respuestas HTTP seguras (sin filtrar trazas internas)."""
import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("erp.errors")

# Restricción de la base → mensaje para el usuario. Lo no listado usa el texto genérico por tipo.
CONSTRAINT_MESSAGES = {
    "uq_parties_company_id_code": "Ya existe un tercero con ese código",
    "uq_parties_company_id_id_type_tax_id": "Ya existe un tercero con ese tipo y número de identificación",
    "ck_parties_has_role": "Marque el tercero como cliente, proveedor o transportista",
    "uq_items_company_id_sku": "Ya existe un artículo con ese SKU",
    "ck_items_minmax_nonneg": "Las existencias mínima y máxima no pueden ser negativas",
    "ck_items_service_not_stocked": "Un servicio no puede ser inventariable",
    "uq_taxes_company_id_code": "Ya existe un impuesto con ese código",
    "ck_taxes_rate_range": "La tarifa debe estar entre 0 y 100",
    "uq_accounts_company_id_code": "Ya existe una cuenta con ese código",
    "uq_warehouses_company_id_code": "Ya existe una bodega con ese código",
    "uq_locations_warehouse_id_code": "Ya existe una ubicación con ese código en la bodega",
    "uq_payment_terms_company_id_code": "Ya existe una condición de pago con ese código",
    "ck_payment_terms_days_nonneg": "Los días de la condición de pago no pueden ser negativos",
    "uq_item_categories_company_id_code": "Ya existe una categoría con ese código",
    "uq_sites_company_id_code": "Ya existe una sede con ese código",
    "uq_business_units_company_id_code": "Ya existe una unidad de negocio con ese código",
    "uq_cost_centers_company_id_code": "Ya existe un centro de costo con ese código",
    "uq_bank_accounts_company_id_name": "Ya existe una cuenta bancaria con ese nombre",
    "uq_document_sequences_company_id_doc_type": "Ya existe una secuencia para ese tipo de documento",
    "uq_uoms_code": "Ya existe una unidad de medida con ese código",
    "uq_exchange_rates_from_currency_to_currency_rate_date_source": "Ya existe esa tasa para la fecha y la fuente",
    "ck_exchange_rates_rate_positive": "La tasa debe ser mayor que cero",
    "uq_delivery_routes_company_id_code": "Ya existe una ruta con ese código",
    "uq_inspection_plans_company_id_code": "Ya existe un plan de inspección con ese código",
    "uq_boms_company_id_code": "Ya existe una lista de materiales con ese código",
    "uq_numbering_ranges_company_id_doc_type_prefix_range_from": "Ya existe ese rango de numeración",
    "ck_numbering_ranges_range_valid": "Revise el rango: «Hasta» y «Siguiente» deben ser coherentes con «Desde»",
}


def integrity_message(constraint: str | None) -> str:
    if constraint in CONSTRAINT_MESSAGES:
        return CONSTRAINT_MESSAGES[constraint]
    if constraint and constraint.startswith("uq_"):
        return "Ya existe un registro con esos datos"
    if constraint and constraint.startswith("ck_"):
        return "Un dato no cumple las reglas del formulario; revise los valores"
    if constraint and constraint.startswith("fk_"):
        return "El registro está relacionado con otro que no existe o que aún lo usa"
    return "La operación viola una restricción de integridad"


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFound(DomainError):
    status_code = 404
    code = "not_found"


class Conflict(DomainError):
    status_code = 409
    code = "conflict"


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"


class Unauthorized(DomainError):
    status_code = 401
    code = "unauthorized"


class BusinessRuleViolation(DomainError):
    status_code = 422
    code = "business_rule"


def _body(code: str, message: str, request: Request, details: dict | None = None) -> dict:
    return jsonable_encoder({
        "error": {"code": code, "message": message, "details": details or {}},
        "request_id": getattr(request.state, "request_id", None),
    })


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError):
        return JSONResponse(_body(exc.code, exc.message, request, exc.details), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            _body("validation_error", "Datos de entrada inválidos", request, {"errors": errors}), status_code=422
        )

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError):
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        log.warning("integrity_error", extra={"constraint": constraint})
        return JSONResponse(
            _body("integrity_error", integrity_message(constraint), request,
                  {"constraint": constraint}),
            status_code=409,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_error")
        return JSONResponse(_body("internal_error", "Error interno", request), status_code=500)

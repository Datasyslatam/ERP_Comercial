"""Errores de dominio y su traducción a respuestas HTTP seguras (sin filtrar trazas internas)."""
import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("erp.errors")


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
            _body("integrity_error", "La operación viola una restricción de integridad", request,
                  {"constraint": constraint}),
            status_code=409,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled_error")
        return JSONResponse(_body("internal_error", "Error interno", request), status_code=500)

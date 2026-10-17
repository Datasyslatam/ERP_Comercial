"""Contexto de la petición en curso (usuario, IP, request id) accesible desde servicios y auditoría.

El middleware crea un objeto por petición y las dependencias lo MUTAN en sitio: FastAPI ejecuta las
dependencias síncronas en otro hilo con una copia del contexto, por lo que `ContextVar.set` allí no se
propagaría al endpoint, pero la mutación del mismo objeto sí.
"""
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class RequestContext:
    user_id: int | None = None
    company_id: int | None = None
    ip: str | None = None
    request_id: str | None = None


_ctx: ContextVar[RequestContext | None] = ContextVar("erp_request_ctx", default=None)


def get_context() -> RequestContext:
    ctx = _ctx.get()
    if ctx is None:
        ctx = RequestContext()
        _ctx.set(ctx)
    return ctx


def set_context(ctx: RequestContext) -> None:
    _ctx.set(ctx)


def update_context(**kwargs) -> None:
    ctx = get_context()
    for k, v in kwargs.items():
        setattr(ctx, k, v)

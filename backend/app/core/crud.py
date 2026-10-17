"""Fábrica de esquemas y routers CRUD para datos maestros.

- Genera esquemas Pydantic desde las columnas del modelo (longitudes, nulabilidad, tipos).
- Aísla por empresa: company_id se toma del contexto autenticado, nunca del cliente.
- Verifica que toda clave foránea a una tabla multiempresa apunte a un registro de la misma empresa.
- No expone DELETE: los maestros se desactivan (is_active) para preservar la integridad histórica.
"""
import csv
import io
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import Base, get_db
from app.core.deps import Principal, require
from app.core.errors import BusinessRuleViolation, NotFound

_SERVER_FIELDS = {"id", "company_id", "created_at", "updated_at", "created_by_id"}


def _py_type(col) -> Any:
    try:
        t = col.type.python_type
    except NotImplementedError:
        t = Any
    if t is dict:
        return dict
    if t is list:
        return list
    return t


def schema_from_model(model: type[Base], *, name: str, exclude: set[str] = frozenset(), partial: bool = False,
                      output: bool = False) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for col in model.__table__.columns:
        if col.key in exclude or (not output and col.key in _SERVER_FIELDS):
            continue
        t = _py_type(col)
        constraints = {}
        if isinstance(col.type, String) and col.type.length and t is str:
            constraints["max_length"] = col.type.length
        has_default = col.default is not None or col.server_default is not None
        if output:
            fields[col.key] = (t | None, None)
        elif partial or col.nullable or has_default:
            fields[col.key] = (t | None, Field(default=None, **constraints))
        else:
            fields[col.key] = (t, Field(..., **constraints))
    cfg = ConfigDict(from_attributes=True, extra="forbid" if not output else "ignore")
    return create_model(name, __config__=cfg, **fields)


def check_company_refs(db: Session, model: type[Base], company_id: int, data: dict) -> None:
    for col in model.__table__.columns:
        if col.key not in data or data[col.key] is None:
            continue
        for fk in col.foreign_keys:
            target = fk.column.table
            if "company_id" in target.c and target.name != "companies":
                owner = db.execute(select(target.c.company_id).where(fk.column == data[col.key])).scalar()
                if owner is None:
                    raise BusinessRuleViolation(f"Referencia inválida en '{col.key}'")
                if owner != company_id:
                    raise BusinessRuleViolation(f"'{col.key}' pertenece a otra empresa")


def get_owned(db: Session, model: type[Base], obj_id: int, company_id: int, *, lock: bool = False):
    stmt = select(model).where(model.id == obj_id)
    if lock:
        stmt = stmt.with_for_update(of=model).execution_options(populate_existing=True)
    obj = db.scalar(stmt)
    if obj is None or getattr(obj, "company_id", company_id) != company_id:
        raise NotFound(f"{model.__tablename__}: registro {obj_id} no encontrado")
    return obj


def _csv_value(v):
    if isinstance(v, Decimal | date | datetime):
        return str(v)
    return v


def crud_router(
    model: type[Base],
    *,
    prefix: str,
    tag: str,
    read_perm: str,
    write_perm: str,
    export_perm: str | None = None,
    search_fields: tuple[str, ...] = ("code", "name"),
    exclude_in: set[str] = frozenset(),
    before_save: Callable[[Session, Principal, Any, dict], None] | None = None,
    order_by: str = "id",
    exclude_out: set[str] = frozenset(),
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    name = model.__name__
    In = schema_from_model(model, name=f"{name}Create", exclude=set(exclude_in))
    Patch = schema_from_model(model, name=f"{name}Update", exclude=set(exclude_in), partial=True)
    Out = schema_from_model(model, name=f"{name}Out", output=True, exclude=set(exclude_out))
    scoped = "company_id" in model.__table__.c

    class Page(BaseModel):
        items: list[Out]  # type: ignore[valid-type]
        total: int

    Page.__name__ = f"{name}Page"

    def _base_query(principal: Principal, q: str | None, active: bool | None):
        stmt = select(model)
        if scoped:
            stmt = stmt.where(model.company_id == principal.company_id)
        if q:
            conds = [getattr(model, f).ilike(f"%{q}%") for f in search_fields if hasattr(model, f)]
            if conds:
                stmt = stmt.where(or_(*conds))
        if active is not None and hasattr(model, "is_active"):
            stmt = stmt.where(model.is_active.is_(active))
        return stmt

    @router.get("", response_model=Page, summary=f"Listar {tag}")
    def list_(q: str | None = None, active: bool | None = None, limit: int = Query(50, le=500), offset: int = 0,
              principal: Principal = Depends(require(read_perm)), db: Session = Depends(get_db)):
        stmt = _base_query(principal, q, active)
        total = db.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = db.scalars(stmt.order_by(getattr(model, order_by)).limit(limit).offset(offset)).all()
        return {"items": rows, "total": total}

    if export_perm:
        @router.get("/export.csv", summary=f"Exportar {tag} a CSV")
        def export(q: str | None = None, active: bool | None = None,
                   principal: Principal = Depends(require(export_perm)), db: Session = Depends(get_db)):
            rows = db.scalars(_base_query(principal, q, active).order_by(model.id)).all()
            cols = [c.key for c in model.__table__.columns]
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(cols)
            for r in rows:
                w.writerow([_csv_value(getattr(r, c)) for c in cols])
            log_action(db, "export", model.__tablename__, None, f"Exportación CSV de {len(rows)} registros")
            db.commit()
            return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                     headers={"Content-Disposition": f'attachment; filename="{prefix.strip("/")}.csv"'})

    @router.get("/{obj_id}", response_model=Out, summary=f"Consultar {tag}")
    def get_(obj_id: int, principal: Principal = Depends(require(read_perm)), db: Session = Depends(get_db)):
        return get_owned(db, model, obj_id, principal.company_id)

    @router.post("", response_model=Out, status_code=201, summary=f"Crear {tag}")
    def create(payload: In, principal: Principal = Depends(require(write_perm)),  # type: ignore[valid-type]
               db: Session = Depends(get_db)):
        data = {k: v for k, v in payload.model_dump().items() if v is not None}
        if scoped:
            data["company_id"] = principal.company_id
            check_company_refs(db, model, principal.company_id, data)
        obj = model(**data)
        if hasattr(obj, "created_by_id"):
            obj.created_by_id = principal.user_id
        if before_save:
            before_save(db, principal, obj, data)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.patch("/{obj_id}", response_model=Out, summary=f"Actualizar {tag}")
    def update(obj_id: int, payload: Patch, principal: Principal = Depends(require(write_perm)),  # type: ignore
               db: Session = Depends(get_db)):
        obj = get_owned(db, model, obj_id, principal.company_id, lock=True)
        data = payload.model_dump(exclude_unset=True)
        if scoped:
            check_company_refs(db, model, principal.company_id, data)
        for k, v in data.items():
            setattr(obj, k, v)
        if before_save:
            before_save(db, principal, obj, data)
        db.commit()
        db.refresh(obj)
        return obj

    return router

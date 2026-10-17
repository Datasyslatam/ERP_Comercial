"""Serialización de entidades y paginación para respuestas de la API."""
from typing import Any

from sqlalchemy import Select, func, inspect, select
from sqlalchemy.orm import Session

_HIDDEN = {"password_hash", "technical_key", "token_hash", "idempotency_key"}


def to_dict(obj, *relations: str) -> dict[str, Any]:
    if obj is None:
        return None
    mapper = inspect(obj).mapper
    out = {a.key: getattr(obj, a.key) for a in mapper.column_attrs if a.key not in _HIDDEN}
    for rel in relations:
        name, _, sub = rel.partition(".")
        val = getattr(obj, name)
        if isinstance(val, list):
            out[name] = [to_dict(v, *([sub] if sub else [])) for v in val]
        else:
            out[name] = to_dict(val, *([sub] if sub else [])) if val is not None else None
    for attr in ("line_subtotal", "difference"):
        if hasattr(type(obj), attr) and isinstance(getattr(type(obj), attr), property):
            out[attr] = getattr(obj, attr)
    return out


def paginate(db: Session, stmt: Select, limit: int, offset: int, *relations: str) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.limit(limit).offset(offset)).all()
    return {"total": total, "items": [to_dict(r, *relations) for r in rows]}

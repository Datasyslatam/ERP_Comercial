"""Auditoría automática de cambios del ORM y registro explícito de acciones sensibles."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.context import get_context

# Tablas de alto volumen o propias de la auditoría que no se registran campo a campo.
_SKIP_TABLES = {
    "audit_log", "login_attempts", "refresh_tokens", "kpi_snapshots", "import_rows", "idempotency_records",
    "stock_balances", "item_costs", "integration_events",
}
_REDACT = {"password_hash", "technical_key", "token_hash"}


def _jsonable(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, str | int | float | bool) or v is None:
        return v
    if isinstance(v, dict | list):
        return v
    return str(v)


def _changes(obj) -> dict:
    out = {}
    state = inspect(obj)
    for attr in state.mapper.column_attrs:
        key = attr.key
        hist = state.attrs[key].history
        if hist.has_changes():
            old = hist.deleted[0] if hist.deleted else None
            new = hist.added[0] if hist.added else None
            if key in _REDACT:
                old, new = ("***" if old else None), "***"
            out[key] = [_jsonable(old), _jsonable(new)]
    return out


def _snapshot(obj) -> dict:
    state = inspect(obj)
    return {
        a.key: ("***" if a.key in _REDACT else _jsonable(getattr(obj, a.key)))
        for a in state.mapper.column_attrs
    }


def log_action(db: Session, action: str, entity_type: str, entity_id, summary: str | None = None,
               changes: dict | None = None) -> None:
    """Registra una acción de negocio (aprobación, contabilización, anulación, exportación, login...)."""
    from app.modules.iam.models import AuditLog

    ctx = get_context()
    db.add(AuditLog(
        user_id=ctx.user_id, company_id=ctx.company_id, ip=ctx.ip, request_id=ctx.request_id, action=action,
        entity_type=entity_type, entity_id=str(entity_id) if entity_id is not None else None, summary=summary,
        changes=changes,
    ))


_registered = False


def register_audit_listener() -> None:
    global _registered
    if _registered:
        return
    _registered = True
    from app.modules.iam.models import AuditLog

    @event.listens_for(Session, "after_flush")
    def _after_flush(session: Session, flush_context):  # pragma: no cover - ejercitado por pruebas de integración
        ctx = get_context()
        entries = []
        for kind, objs in (("create", session.new), ("update", session.dirty), ("delete", session.deleted)):
            for obj in objs:
                table = getattr(obj, "__tablename__", None)
                if table is None or table in _SKIP_TABLES or isinstance(obj, AuditLog):
                    continue
                if kind == "update":
                    if not session.is_modified(obj, include_collections=False):
                        continue
                    changes = _changes(obj)
                    if not changes or set(changes) <= {"updated_at"}:
                        continue
                else:
                    changes = _snapshot(obj)
                ident = inspect(obj).mapper.primary_key_from_instance(obj)
                entries.append({
                    "user_id": ctx.user_id, "company_id": getattr(obj, "company_id", None) or ctx.company_id,
                    "ip": ctx.ip, "request_id": ctx.request_id, "action": kind, "entity_type": table,
                    "entity_id": ",".join(str(i) for i in ident) if any(i is not None for i in ident) else None,
                    "changes": changes,
                })
        if entries:
            session.execute(AuditLog.__table__.insert(), entries)

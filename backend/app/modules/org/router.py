"""Adjuntos (evidencias, soportes de entrega, facturas de proveedor) y estado del sistema."""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, get_principal
from app.core.errors import BusinessRuleViolation, Forbidden
from app.core.serialize import to_dict
from app.core.storage import read_attachment, save_attachment
from app.modules.org.models import Attachment

router = APIRouter(tags=["Adjuntos y sistema"])

# Tipo de entidad → permiso de lectura necesario para ver/adjuntar archivos
ENTITY_PERMS = {
    "inspections": "quality.inspection", "nonconformities": "quality.nonconformity",
    "dispatch_orders": "logistics.dispatch", "supplier_invoices": "purchasing.invoice",
    "goods_receipts": "purchasing.receipt", "purchase_orders": "purchasing.order", "sales_invoices": "einvoicing.invoice",
    "work_orders": "operations.work_order", "journal_entries": "accounting.journal", "bank_statements": "accounting.bank",
}


def _check(p: Principal, entity_type: str, action: str) -> None:
    base = ENTITY_PERMS.get(entity_type)
    if base is None:
        raise BusinessRuleViolation(f"No se admiten adjuntos para '{entity_type}'")
    needed = [f"{base}.read"] if action == "read" else [f"{base}.{a}" for a in ("create", "approve", "post")]
    if not any(p.has(x) for x in needed):
        raise Forbidden("Permiso insuficiente sobre la entidad")


@router.post("/attachments", status_code=201)
async def upload(entity_type: str = Form(...), entity_id: int = Form(...), description: str | None = Form(None),
                 file: UploadFile = File(...), p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    _check(p, entity_type, "create")
    from app.models import metadata

    table = metadata.tables[entity_type]
    owner = db.execute(select(table.c.company_id).where(table.c.id == entity_id)).scalar()
    if owner != p.company_id:
        raise BusinessRuleViolation("La entidad no existe en esta empresa")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    att = save_attachment(db, company_id=p.company_id, entity_type=entity_type, entity_id=entity_id,
                          filename=file.filename or "archivo", content_type=file.content_type or "", data=data,
                          user_id=p.user_id, description=description)
    db.commit()
    return to_dict(att)


@router.get("/attachments")
def list_attachments(entity_type: str, entity_id: int, p: Principal = Depends(get_principal),
                     db: Session = Depends(get_db)):
    _check(p, entity_type, "read")
    rows = db.scalars(select(Attachment).where(Attachment.company_id == p.company_id,
                                               Attachment.entity_type == entity_type,
                                               Attachment.entity_id == entity_id).order_by(Attachment.id))
    return [{k: v for k, v in to_dict(a).items() if k != "storage_key"} for a in rows]


@router.get("/attachments/{att_id}/content")
def download(att_id: int, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    att = get_owned(db, Attachment, att_id, p.company_id)
    _check(p, att.entity_type, "read")
    return Response(read_attachment(att), media_type=att.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{att.filename}"'})


health_router = APIRouter(tags=["Sistema"])


@health_router.get("/health/live")
def live():
    return {"status": "ok"}


@health_router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    version = db.execute(text("select version_num from alembic_version")).scalar()
    return {"status": "ok", "schema_version": version, "environment": get_settings().environment}

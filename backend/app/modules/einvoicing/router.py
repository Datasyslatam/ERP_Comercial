from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import crud_router, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.schemas import ReasonIn
from app.core.serialize import paginate, to_dict
from app.core.storage import read_attachment
from app.modules.einvoicing import service as svc
from app.modules.einvoicing.models import EInvoiceSubmission, NumberingRange, SalesInvoice
from app.modules.org.models import Attachment

router = APIRouter(prefix="/einvoicing", tags=["Facturación electrónica"],
                   dependencies=[Depends(require_module("einvoicing"))])
router.include_router(crud_router(NumberingRange, prefix="/numbering-ranges", tag="Numeración autorizada",
                                  read_perm="einvoicing.numbering.read", write_perm="einvoicing.numbering.admin",
                                  search_fields=("prefix", "authorization_number"), exclude_out={"technical_key"}))


class FromDispatchIn(BaseModel):
    dispatch_id: int
    issue_date: date | None = None


class NoteLineIn(BaseModel):
    invoice_line_id: int
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=255)


class NoteIn(BaseModel):
    doc_type: str = Field(pattern="^(credit_note|debit_note)$")
    correction_code: str = Field(max_length=4)
    reason: str = Field(min_length=5, max_length=255)
    issue_date: date | None = None
    lines: list[NoteLineIn] = Field(min_length=1)


def _out(inv: SalesInvoice) -> dict:
    out = to_dict(inv, "lines", "taxes")
    out["fiscal_notice"] = None if inv.legal_validity else (
        "Documento de PRUEBAS: sin validez fiscal" if inv.edoc_environment == "sandbox"
        else "Pendiente de validación por la autoridad tributaria")
    return out


@router.get("/invoices")
def list_invoices(doc_type: str | None = None, status: str | None = None, edoc_status: str | None = None,
                  customer_id: int | None = None, start: date | None = None, end: date | None = None,
                  limit: int = Query(50, le=500), offset: int = 0,
                  p: Principal = Depends(require("einvoicing.invoice.read")), db: Session = Depends(get_db)):
    stmt = select(SalesInvoice).where(SalesInvoice.company_id == p.company_id)
    for col, val in ((SalesInvoice.doc_type, doc_type), (SalesInvoice.status, status),
                     (SalesInvoice.edoc_status, edoc_status), (SalesInvoice.customer_id, customer_id)):
        if val is not None:
            stmt = stmt.where(col == val)
    if start:
        stmt = stmt.where(SalesInvoice.issue_date >= start)
    if end:
        stmt = stmt.where(SalesInvoice.issue_date <= end)
    return paginate(db, stmt.order_by(SalesInvoice.id.desc()), limit, offset, "lines", "taxes")


@router.get("/invoices/{inv_id}")
def get_invoice(inv_id: int, p: Principal = Depends(require("einvoicing.invoice.read")), db: Session = Depends(get_db)):
    inv = get_owned(db, SalesInvoice, inv_id, p.company_id)
    out = _out(inv)
    out["submissions"] = [to_dict(s) for s in db.scalars(select(EInvoiceSubmission).where(
        EInvoiceSubmission.invoice_id == inv.id).order_by(EInvoiceSubmission.attempt_no))]
    return out


@router.post("/invoices/from-dispatch", status_code=201)
def from_dispatch(body: FromDispatchIn, p: Principal = Depends(require("einvoicing.invoice.create")),
                  db: Session = Depends(get_db)):
    inv = svc.create_from_dispatch(db, p, body.dispatch_id, body.issue_date)
    db.commit()
    return _out(inv)


@router.post("/invoices/{inv_id}/notes", status_code=201)
def create_note(inv_id: int, body: NoteIn, p: Principal = Depends(require("einvoicing.invoice.create")),
                db: Session = Depends(get_db)):
    note = svc.create_note(db, p, inv_id, body.model_dump())
    db.commit()
    return _out(note)


@router.post("/invoices/{inv_id}/issue")
def issue(inv_id: int, p: Principal = Depends(require("einvoicing.invoice.post")), db: Session = Depends(get_db)):
    inv = svc.issue(db, p, inv_id)
    db.commit()
    return _out(inv)


@router.post("/invoices/{inv_id}/resend")
def resend(inv_id: int, p: Principal = Depends(require("einvoicing.invoice.post")), db: Session = Depends(get_db)):
    inv = svc.resend(db, p, inv_id)
    db.commit()
    return _out(inv)


@router.post("/invoices/{inv_id}/cancel")
def cancel(inv_id: int, body: ReasonIn, p: Principal = Depends(require("einvoicing.invoice.void")),
           db: Session = Depends(get_db)):
    inv = svc.cancel_draft(db, p, inv_id, body.reason)
    db.commit()
    return _out(inv)


@router.get("/invoices/{inv_id}/document")
def download_document(inv_id: int, p: Principal = Depends(require("einvoicing.invoice.export")),
                      db: Session = Depends(get_db)):
    """Documento electrónico conservado (XML DIAN o JSON imprenta), verificado contra su huella SHA-256."""
    inv = get_owned(db, SalesInvoice, inv_id, p.company_id)
    sub = db.scalar(select(EInvoiceSubmission).where(EInvoiceSubmission.invoice_id == inv.id,
                                                     EInvoiceSubmission.document_attachment_id.is_not(None))
                    .order_by(EInvoiceSubmission.attempt_no.desc()).limit(1))
    if sub is None:
        from app.core.errors import NotFound

        raise NotFound("El documento electrónico aún no se ha generado")
    att = db.get(Attachment, sub.document_attachment_id)
    return Response(read_attachment(att), media_type=att.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{att.filename}"'})


@router.get("/reconciliation")
def reconciliation(start: date, end: date, p: Principal = Depends(require("einvoicing.invoice.read")),
                   db: Session = Depends(get_db)):
    return svc.reconciliation(db, p.company_id, start, end)


@router.get("/correction-codes")
def correction_codes(_: Principal = Depends(require("einvoicing.invoice.read"))):
    return svc.CORRECTION_CODES_CO

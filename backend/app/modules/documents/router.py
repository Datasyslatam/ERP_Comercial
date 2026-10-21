from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import get_db
from app.core.deps import Principal, get_principal
from app.core.serialize import to_dict
from app.modules.documents import service

router = APIRouter(prefix="/documents", tags=["Documentos comerciales"])


class EmailIn(BaseModel):
    to: list[EmailStr] = Field(min_length=1, max_length=10)
    cc: list[EmailStr] = Field(default_factory=list, max_length=10)
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=5000)


@router.get("/{doc_type}/{doc_id}/pdf")
def pdf(doc_type: str, doc_id: int, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Representación gráfica en PDF (sales_quote, sales_order, purchase_order, sales_invoice)."""
    filename, data = service.pdf_for(db, p, doc_type, doc_id)
    log_action(db, "export", doc_type, doc_id, f"Descarga del PDF {filename}")
    db.commit()
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/{doc_type}/{doc_id}/email-defaults")
def email_defaults(doc_type: str, doc_id: int, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Destinatario (correo del tercero), asunto y mensaje sugeridos para el envío."""
    _, obj = service._get(db, p, doc_type, doc_id, perm="send")
    return service.default_message(db, doc_type, obj)


@router.post("/{doc_type}/{doc_id}/email", status_code=202)
def send_email(doc_type: str, doc_id: int, body: EmailIn, p: Principal = Depends(get_principal),
               db: Session = Depends(get_db)):
    """Encola el envío; el worker genera el PDF vigente, lo adjunta y reintenta ante fallas del servidor de correo."""
    em = service.queue_email(db, p, doc_type, doc_id, [str(x) for x in body.to], [str(x) for x in body.cc],
                             body.subject, body.body)
    db.commit()
    return to_dict(em)


@router.get("/{doc_type}/{doc_id}/emails")
def emails(doc_type: str, doc_id: int, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Historial de envíos del documento con su estado (en cola, enviado, fallido) y error si lo hubo."""
    return [to_dict(e) for e in service.history(db, p, doc_type, doc_id)]

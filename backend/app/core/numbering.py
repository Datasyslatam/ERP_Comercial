"""Asignación concurrente-segura de números de documento internos (sin duplicados)."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.org.models import DocumentSequence

DEFAULT_PREFIXES = {
    "purchase_requisition": "SC", "rfq": "SQ", "purchase_order": "OC", "goods_receipt": "RM",
    "supplier_invoice": "FP", "inventory_document": "MI", "physical_count": "CF", "sales_order": "PV",
    "dispatch": "DS", "customer_return": "DV", "work_order": "OT", "inspection": "IN", "nonconformity": "NC",
    "journal_entry": "CC", "payment_receipt": "RC", "payment_disbursement": "CE",
}


def next_number(db: Session, company_id: int, doc_type: str) -> str:
    # Creación idempotente de la secuencia (dos transacciones simultáneas no colisionan) y bloqueo de fila.
    db.execute(pg_insert(DocumentSequence).values(
        company_id=company_id, doc_type=doc_type, prefix=DEFAULT_PREFIXES.get(doc_type, doc_type[:3].upper()),
        next_number=1, padding=6).on_conflict_do_nothing())
    seq = db.scalar(
        select(DocumentSequence)
        .where(DocumentSequence.company_id == company_id, DocumentSequence.doc_type == doc_type)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    number = seq.next_number
    seq.next_number = number + 1
    db.flush()
    return f"{seq.prefix}-{str(number).zfill(seq.padding)}"

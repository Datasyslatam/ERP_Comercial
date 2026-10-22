from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.schemas import QtyField
from app.core.serialize import paginate, to_dict
from app.modules.purchasing import service as svc
from app.modules.purchasing.models import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseRequisition,
    RequestForQuotation,
    SupplierInvoice,
)

router = APIRouter(prefix="/purchasing", tags=["Compras"], dependencies=[Depends(require_module("purchasing"))])



class ReqLine(BaseModel):
    item_id: int
    quantity: Decimal = QtyField()
    description: str | None = Field(default=None, max_length=255)
    estimated_unit_price: Decimal = Field(default=Decimal("0"), ge=0)


class RequisitionIn(BaseModel):
    site_id: int
    cost_center_id: int | None = None
    needed_by: date | None = None
    justification: str | None = Field(default=None, max_length=2000)
    lines: list[ReqLine] = Field(min_length=1)


class DecisionIn(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=1000)


class RfqIn(BaseModel):
    requisition_id: int
    due_date: date | None = None


class QuoteLine(BaseModel):
    requisition_line_id: int
    quantity: Decimal = QtyField()
    unit_price: Decimal = Field(ge=0)
    tax_id: int | None = None


class QuoteIn(BaseModel):
    supplier_id: int
    quote_reference: str | None = Field(default=None, max_length=60)
    quote_date: date
    valid_until: date | None = None
    currency: str = Field(min_length=3, max_length=3)
    delivery_days: int = Field(default=0, ge=0)
    payment_term_id: int | None = None
    lines: list[QuoteLine] = Field(min_length=1)


class AwardIn(BaseModel):
    quote_id: int
    warehouse_id: int


class PoLine(BaseModel):
    item_id: int
    quantity: Decimal = QtyField()
    unit_price: Decimal = Field(ge=0)
    tax_id: int | None = None
    description: str | None = Field(default=None, max_length=255)
    requisition_line_id: int | None = None


class OrderIn(BaseModel):
    site_id: int
    supplier_id: int
    warehouse_id: int
    cost_center_id: int | None = None
    requisition_id: int | None = None
    order_date: date
    expected_date: date | None = None
    currency: str = Field(min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    payment_term_id: int | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[PoLine] = Field(min_length=1)


class ReceiptLine(BaseModel):
    po_line_id: int
    quantity: Decimal = QtyField()
    lot_number: str | None = Field(default=None, max_length=60)
    expiry_date: date | None = None


class ReceiptIn(BaseModel):
    receipt_date: date
    supplier_delivery_note: str | None = Field(default=None, max_length=60)
    location_id: int | None = None
    lines: list[ReceiptLine] = Field(min_length=1)


class InvoiceLine(BaseModel):
    receipt_line_id: int | None = None
    item_id: int | None = None
    expense_account_id: int | None = None
    cost_center_id: int | None = None
    description: str = Field(max_length=255)
    quantity: Decimal = QtyField()
    unit_price: Decimal = Field(ge=0)
    tax_id: int | None = None


class SupplierInvoiceIn(BaseModel):
    supplier_id: int
    supplier_invoice_number: str = Field(min_length=1, max_length=60)
    supplier_cufe: str | None = Field(default=None, max_length=120)
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(min_length=3, max_length=3)
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    lines: list[InvoiceLine] = Field(min_length=1)


class CancelIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


def _list(db, model, p, status, limit, offset, *rels, date_field=None, start=None, end=None, party=None,
          party_field="supplier_id"):
    stmt = select(model).where(model.company_id == p.company_id)
    if status:
        stmt = stmt.where(model.status == status)
    if party:
        stmt = stmt.where(getattr(model, party_field) == party)
    if date_field and start:
        stmt = stmt.where(getattr(model, date_field) >= start)
    if date_field and end:
        stmt = stmt.where(getattr(model, date_field) <= end)
    return paginate(db, stmt.order_by(model.id.desc()), limit, offset, *rels)


# ------------------------------------------------------------------ solicitudes
@router.get("/requisitions")
def list_requisitions(status: str | None = None, limit: int = Query(50, le=500), offset: int = 0,
                      p: Principal = Depends(require("purchasing.requisition.read")), db: Session = Depends(get_db)):
    return _list(db, PurchaseRequisition, p, status, limit, offset, "lines")


@router.post("/requisitions", status_code=201)
def create_requisition(body: RequisitionIn, p: Principal = Depends(require("purchasing.requisition.create")),
                       db: Session = Depends(get_db)):
    req = svc.create_requisition(db, p, body.model_dump())
    db.commit()
    return to_dict(req, "lines")


class ReplenishmentReqIn(BaseModel):
    site_id: int
    needed_by: date | None = None
    quantities: dict[int, Decimal] | None = Field(default=None, description="item_id → cantidad; omita para usar la sugerida")


@router.post("/requisitions/from-replenishment", status_code=201)
def requisition_from_replenishment(body: ReplenishmentReqIn,
                                   p: Principal = Depends(require("purchasing.requisition.create", "inventory.stock.read")),
                                   db: Session = Depends(get_db)):
    """Convierte las sugerencias de reabastecimiento (artículos bajo mínimo) en una solicitud de compra en borrador."""
    req = svc.requisition_from_replenishment(db, p, body.site_id, body.needed_by, body.quantities)
    db.commit()
    return to_dict(req, "lines")


@router.get("/requisitions/{req_id}")
def get_requisition(req_id: int, p: Principal = Depends(require("purchasing.requisition.read")),
                    db: Session = Depends(get_db)):
    return to_dict(get_owned(db, PurchaseRequisition, req_id, p.company_id), "lines")


@router.post("/requisitions/{req_id}/submit")
def submit_requisition(req_id: int, p: Principal = Depends(require("purchasing.requisition.create")),
                       db: Session = Depends(get_db)):
    req = svc.submit_requisition(db, p, req_id)
    db.commit()
    return to_dict(req, "lines")


@router.post("/requisitions/{req_id}/decision")
def decide_requisition(req_id: int, body: DecisionIn, p: Principal = Depends(require("purchasing.requisition.approve")),
                       db: Session = Depends(get_db)):
    req = svc.decide_requisition(db, p, req_id, body.approve, body.reason)
    db.commit()
    return to_dict(req, "lines")


# ------------------------------------------------------------------ cotizaciones
@router.get("/rfqs")
def list_rfqs(status: str | None = None, limit: int = Query(50, le=500), offset: int = 0,
              p: Principal = Depends(require("purchasing.rfq.read")), db: Session = Depends(get_db)):
    return _list(db, RequestForQuotation, p, status, limit, offset, "quotes.lines")


@router.post("/rfqs", status_code=201)
def create_rfq(body: RfqIn, p: Principal = Depends(require("purchasing.rfq.create")), db: Session = Depends(get_db)):
    rfq = svc.create_rfq(db, p, body.requisition_id, body.due_date)
    db.commit()
    return to_dict(rfq)


@router.post("/rfqs/{rfq_id}/quotes", status_code=201)
def add_quote(rfq_id: int, body: QuoteIn, p: Principal = Depends(require("purchasing.rfq.create")),
              db: Session = Depends(get_db)):
    q = svc.add_quote(db, p, rfq_id, body.model_dump())
    db.commit()
    return to_dict(q, "lines")


@router.get("/rfqs/{rfq_id}/comparison")
def compare(rfq_id: int, p: Principal = Depends(require("purchasing.rfq.read")), db: Session = Depends(get_db)):
    return svc.compare_quotes(db, p, rfq_id)


@router.post("/rfqs/{rfq_id}/award")
def award(rfq_id: int, body: AwardIn, p: Principal = Depends(require("purchasing.rfq.approve")),
          db: Session = Depends(get_db)):
    po = svc.award_quote(db, p, rfq_id, body.quote_id, body.warehouse_id)
    db.commit()
    return to_dict(po, "lines")


# ------------------------------------------------------------------ órdenes
@router.get("/orders")
def list_orders(status: str | None = None, supplier_id: int | None = None, start: date | None = None,
                end: date | None = None, overdue: bool = False, limit: int = Query(50, le=500), offset: int = 0,
                p: Principal = Depends(require("purchasing.order.read")), db: Session = Depends(get_db)):
    if overdue:
        stmt = select(PurchaseOrder).where(PurchaseOrder.company_id == p.company_id,
                                           PurchaseOrder.status.in_(("approved", "partially_received")),
                                           PurchaseOrder.expected_date < date.today())
        return paginate(db, stmt.order_by(PurchaseOrder.expected_date), limit, offset, "lines")
    return _list(db, PurchaseOrder, p, status, limit, offset, "lines", date_field="order_date", start=start, end=end,
                 party=supplier_id)


@router.post("/orders", status_code=201)
def create_order(body: OrderIn, p: Principal = Depends(require("purchasing.order.create")),
                 db: Session = Depends(get_db)):
    po = svc.create_order(db, p, body.model_dump())
    db.commit()
    return to_dict(po, "lines")


@router.put("/orders/{po_id}")
def update_order(po_id: int, body: OrderIn, p: Principal = Depends(require("purchasing.order.create")),
                 db: Session = Depends(get_db)):
    """Edita una orden en borrador: reemplaza encabezado y líneas y recalcula impuestos."""
    po = svc.update_order(db, p, po_id, body.model_dump(exclude_none=True))
    db.commit()
    return to_dict(po, "lines")


@router.get("/orders/{po_id}")
def get_order(po_id: int, p: Principal = Depends(require("purchasing.order.read")), db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, po_id, p.company_id)
    out = to_dict(po, "lines")
    out["receipts"] = [to_dict(r, "lines") for r in db.scalars(
        select(GoodsReceipt).where(GoodsReceipt.purchase_order_id == po.id))]
    out["invoices"] = [to_dict(i) for i in db.scalars(
        select(SupplierInvoice).where(SupplierInvoice.purchase_order_id == po.id))]
    return out


@router.post("/orders/{po_id}/submit")
def submit_order(po_id: int, p: Principal = Depends(require("purchasing.order.create")), db: Session = Depends(get_db)):
    po = svc.submit_order(db, p, po_id)
    db.commit()
    return to_dict(po, "lines")


@router.post("/orders/{po_id}/decision")
def decide_order(po_id: int, body: DecisionIn, p: Principal = Depends(require("purchasing.order.approve")),
                 db: Session = Depends(get_db)):
    po, budget = svc.decide_order(db, p, po_id, body.approve, body.reason)
    db.commit()
    return {**to_dict(po, "lines"), "budget_check": budget}


@router.post("/orders/{po_id}/cancel")
def cancel_order(po_id: int, body: CancelIn, p: Principal = Depends(require("purchasing.order.void")),
                 db: Session = Depends(get_db)):
    po = svc.cancel_order(db, p, po_id, body.reason)
    db.commit()
    return to_dict(po)


@router.post("/orders/{po_id}/receipts", status_code=201)
def receive(po_id: int, body: ReceiptIn, p: Principal = Depends(require("purchasing.receipt.post")),
            db: Session = Depends(get_db)):
    gr = svc.receive(db, p, po_id, body.model_dump())
    db.commit()
    return to_dict(gr, "lines")


@router.get("/receipts")
def list_receipts(supplier_id: int | None = None, start: date | None = None, end: date | None = None,
                  limit: int = Query(50, le=500), offset: int = 0,
                  p: Principal = Depends(require("purchasing.receipt.read")), db: Session = Depends(get_db)):
    return _list(db, GoodsReceipt, p, None, limit, offset, "lines", date_field="receipt_date", start=start, end=end,
                 party=supplier_id)


# ------------------------------------------------------------------ facturas de proveedor
@router.get("/invoices")
def list_invoices(status: str | None = None, supplier_id: int | None = None, limit: int = Query(50, le=500),
                  offset: int = 0, p: Principal = Depends(require("purchasing.invoice.read")),
                  db: Session = Depends(get_db)):
    return _list(db, SupplierInvoice, p, status, limit, offset, "lines", "taxes", party=supplier_id)


@router.post("/invoices", status_code=201)
def create_invoice(body: SupplierInvoiceIn, p: Principal = Depends(require("purchasing.invoice.create")),
                   db: Session = Depends(get_db)):
    inv = svc.create_supplier_invoice(db, p, body.model_dump())
    db.commit()
    return to_dict(inv, "lines", "taxes")


@router.post("/invoices/{inv_id}/post")
def post_invoice(inv_id: int, p: Principal = Depends(require("purchasing.invoice.post")),
                 db: Session = Depends(get_db)):
    inv = svc.post_supplier_invoice_doc(db, p, inv_id)
    db.commit()
    return to_dict(inv, "lines", "taxes")


# ------------------------------------------------------------------ análisis
@router.get("/price-history/{item_id}")
def price_history(item_id: int, p: Principal = Depends(require("purchasing.order.read")),
                  db: Session = Depends(get_db)):
    return svc.price_history(db, p.company_id, item_id)


@router.get("/suppliers/evaluation")
def evaluation_ranking(start: date, end: date, p: Principal = Depends(require("purchasing.supplier_eval.read")),
                       db: Session = Depends(get_db)):
    """Evaluación de todos los proveedores con recepciones en el periodo, de mejor a peor puntaje."""
    return svc.supplier_ranking(db, p.company_id, start, end)


@router.get("/suppliers/{supplier_id}/evaluation")
def evaluation(supplier_id: int, start: date, end: date,
               p: Principal = Depends(require("purchasing.supplier_eval.read")), db: Session = Depends(get_db)):
    return svc.supplier_evaluation(db, p.company_id, supplier_id, start, end)


@router.get("/budget-status")
def budget_status(on: date, cost_center_id: int | None = None,
                  p: Principal = Depends(require("purchasing.order.read")), db: Session = Depends(get_db)):
    return svc.budget_status(db, p.company_id, cost_center_id, on)

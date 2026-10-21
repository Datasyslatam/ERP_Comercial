from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.schemas import CurrencyField, QtyField, ReasonIn
from app.core.serialize import paginate, to_dict
from app.modules.sales import service as svc
from app.modules.sales.models import SalesOrder, SalesQuote

router = APIRouter(prefix="/sales", tags=["Ventas"], dependencies=[Depends(require_module("sales"))])


class SoLine(BaseModel):
    item_id: int
    quantity: Decimal = QtyField()
    unit_price: Decimal | None = Field(default=None, ge=0)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_id: int | None = None
    description: str | None = Field(default=None, max_length=255)


class SalesOrderIn(BaseModel):
    site_id: int
    customer_id: int
    warehouse_id: int
    order_date: date
    promised_date: date | None = None
    currency: str = CurrencyField()
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    payment_term_id: int | None = None
    delivery_address: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[SoLine] = Field(min_length=1)


@router.get("/orders")
def list_orders(status: str | None = None, customer_id: int | None = None, start: date | None = None,
                end: date | None = None, limit: int = Query(50, le=500), offset: int = 0,
                p: Principal = Depends(require("sales.order.read")), db: Session = Depends(get_db)):
    stmt = select(SalesOrder).where(SalesOrder.company_id == p.company_id)
    if status:
        stmt = stmt.where(SalesOrder.status == status)
    if customer_id:
        stmt = stmt.where(SalesOrder.customer_id == customer_id)
    if start:
        stmt = stmt.where(SalesOrder.order_date >= start)
    if end:
        stmt = stmt.where(SalesOrder.order_date <= end)
    if p.site_ids is not None:
        stmt = stmt.where(SalesOrder.site_id.in_(p.site_ids))
    return paginate(db, stmt.order_by(SalesOrder.id.desc()), limit, offset, "lines")


@router.post("/orders", status_code=201)
def create_order(body: SalesOrderIn, p: Principal = Depends(require("sales.order.create")),
                 db: Session = Depends(get_db)):
    so = svc.create_order(db, p, body.model_dump(exclude_none=True))
    db.commit()
    return to_dict(so, "lines")


@router.get("/orders/{so_id}")
def get_order(so_id: int, p: Principal = Depends(require("sales.order.read")), db: Session = Depends(get_db)):
    from app.modules.einvoicing.models import SalesInvoice
    from app.modules.logistics.models import DispatchOrder

    so = get_owned(db, SalesOrder, so_id, p.company_id)
    out = to_dict(so, "lines")
    out["dispatches"] = [to_dict(d, "lines") for d in db.scalars(
        select(DispatchOrder).where(DispatchOrder.sales_order_id == so.id))]
    out["invoices"] = [to_dict(i) for i in db.scalars(select(SalesInvoice).where(SalesInvoice.sales_order_id == so.id))]
    return out


@router.post("/orders/{so_id}/confirm")
def confirm(so_id: int, p: Principal = Depends(require("sales.order.approve")), db: Session = Depends(get_db)):
    so = svc.confirm_order(db, p, so_id)
    db.commit()
    return to_dict(so, "lines")


@router.post("/orders/{so_id}/cancel")
def cancel(so_id: int, body: ReasonIn, p: Principal = Depends(require("sales.order.void")),
           db: Session = Depends(get_db)):
    so = svc.cancel_order(db, p, so_id, body.reason)
    db.commit()
    return to_dict(so, "lines")


@router.get("/customers/{customer_id}/credit")
def credit(customer_id: int, p: Principal = Depends(require("sales.order.read")), db: Session = Depends(get_db)):
    from app.modules.masters.models import Party

    party = get_owned(db, Party, customer_id, p.company_id)
    exposure = svc.credit_exposure(db, p.company_id, party.id)
    return {"customer_id": party.id, "credit_limit": party.credit_limit, "exposure": exposure,
            "available": (party.credit_limit - exposure) if party.credit_limit else None}


@router.post("/orders/{so_id}/close")
def close(so_id: int, body: ReasonIn, p: Principal = Depends(require("sales.order.approve")),
          db: Session = Depends(get_db)):
    """Cierra el pedido con saldo pendiente (el cliente ya no lo requiere) y libera sus reservas."""
    so = svc.close_order(db, p, so_id, body.reason)
    db.commit()
    return to_dict(so, "lines")


# ---------------------------------------------------------------- cotizaciones
class QuoteIn(BaseModel):
    site_id: int
    customer_id: int
    quote_date: date
    valid_until: date
    currency: str = CurrencyField()
    payment_term_id: int | None = None
    contact_name: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[SoLine] = Field(min_length=1)


class ConvertIn(BaseModel):
    warehouse_id: int
    order_date: date | None = None
    promised_date: date | None = None
    delivery_address: str | None = Field(default=None, max_length=255)


def _quote_out(q: SalesQuote) -> dict:
    out = to_dict(q, "lines")
    out["status"] = svc.quote_status(q)
    return out


@router.get("/quotes")
def list_quotes(status: str | None = None, customer_id: int | None = None, limit: int = Query(50, le=500),
                offset: int = 0, p: Principal = Depends(require("sales.quote.read")), db: Session = Depends(get_db)):
    stmt = select(SalesQuote).where(SalesQuote.company_id == p.company_id)
    if status == "expired":
        stmt = stmt.where(SalesQuote.status.in_(("draft", "sent")), SalesQuote.valid_until < date.today())
    elif status in ("draft", "sent"):
        stmt = stmt.where(SalesQuote.status == status, SalesQuote.valid_until >= date.today())
    elif status:
        stmt = stmt.where(SalesQuote.status == status)
    if customer_id:
        stmt = stmt.where(SalesQuote.customer_id == customer_id)
    if p.site_ids is not None:
        stmt = stmt.where(SalesQuote.site_id.in_(p.site_ids))
    page = paginate(db, stmt.order_by(SalesQuote.id.desc()), limit, offset, "lines")
    for row in page["items"]:
        if row["status"] in ("draft", "sent") and date.fromisoformat(str(row["valid_until"])) < date.today():
            row["status"] = "expired"
    return page


@router.post("/quotes", status_code=201)
def create_quote(body: QuoteIn, p: Principal = Depends(require("sales.quote.create")), db: Session = Depends(get_db)):
    q = svc.create_quote(db, p, body.model_dump(exclude_none=True))
    db.commit()
    return _quote_out(q)


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: int, p: Principal = Depends(require("sales.quote.read")), db: Session = Depends(get_db)):
    return _quote_out(get_owned(db, SalesQuote, quote_id, p.company_id))


@router.post("/quotes/{quote_id}/send")
def send_quote(quote_id: int, p: Principal = Depends(require("sales.quote.create")), db: Session = Depends(get_db)):
    q = svc.send_quote(db, p, quote_id)
    db.commit()
    return _quote_out(q)


@router.post("/quotes/{quote_id}/reject")
def reject_quote(quote_id: int, body: ReasonIn, p: Principal = Depends(require("sales.quote.create")),
                 db: Session = Depends(get_db)):
    q = svc.reject_quote(db, p, quote_id, body.reason)
    db.commit()
    return _quote_out(q)


@router.post("/quotes/{quote_id}/convert", status_code=201)
def convert_quote(quote_id: int, body: ConvertIn,
                  p: Principal = Depends(require("sales.quote.create", "sales.order.create")),
                  db: Session = Depends(get_db)):
    """Convierte la cotización vigente en un pedido de venta en borrador con las mismas condiciones."""
    so = svc.convert_quote(db, p, quote_id, body.model_dump(exclude_none=True))
    db.commit()
    return to_dict(so, "lines")

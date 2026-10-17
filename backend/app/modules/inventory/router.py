from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.serialize import paginate, to_dict
from app.modules.inventory import service as svc
from app.modules.inventory import stock
from app.modules.inventory.models import InventoryDocument, Lot, PhysicalCount, StockReservation

router = APIRouter(prefix="/inventory", tags=["Inventario"], dependencies=[Depends(require_module("inventory"))])


class DocLine(BaseModel):
    item_id: int
    lot_id: int | None = None
    from_location_id: int | None = None
    to_location_id: int | None = None
    quantity: Decimal = Field(max_digits=18, decimal_places=6)
    unit_cost: Decimal | None = Field(default=None, ge=0)


class DocumentIn(BaseModel):
    doc_type: str = Field(pattern="^(transfer|adjustment|consumption|scrap)$")
    doc_date: date
    reason: str = Field(min_length=5, max_length=255)
    cost_center_id: int | None = None
    lines: list[DocLine] = Field(min_length=1)


class CountOpenIn(BaseModel):
    warehouse_id: int
    count_date: date
    notes: str | None = Field(default=None, max_length=1000)


class CountEntry(BaseModel):
    item_id: int
    location_id: int
    lot_id: int | None = None
    counted_qty: Decimal = Field(ge=0)


class CountRecordIn(BaseModel):
    entries: list[CountEntry] = Field(min_length=1)


@router.get("/stock")
def stock_on_hand(warehouse_id: int | None = None, item_id: int | None = None, below_min: bool = False,
                  p: Principal = Depends(require("inventory.stock.read")), db: Session = Depends(get_db)):
    return svc.stock_on_hand(db, p.company_id, warehouse_id, item_id, below_min)


@router.get("/kardex/{item_id}")
def kardex(item_id: int, start: date, end: date, location_id: int | None = None,
           p: Principal = Depends(require("inventory.stock.read")), db: Session = Depends(get_db)):
    stock.get_item(db, p.company_id, item_id)
    return svc.kardex(db, p.company_id, item_id, start, end, location_id)


@router.get("/availability/{item_id}")
def availability(item_id: int, warehouse_id: int | None = None,
                 p: Principal = Depends(require("inventory.stock.read")), db: Session = Depends(get_db)):
    stock.get_item(db, p.company_id, item_id)
    return {"item_id": item_id, "available": stock.available_qty(db, p.company_id, item_id, warehouse_id),
            "avg_cost": stock.current_cost(db, p.company_id, item_id)}


@router.get("/replenishment")
def replenishment(p: Principal = Depends(require("inventory.stock.read")), db: Session = Depends(get_db)):
    return svc.replenishment_alerts(db, p.company_id)


@router.get("/expiring")
def expiring(days: int = Query(30, ge=0, le=365), p: Principal = Depends(require("inventory.stock.read")),
             db: Session = Depends(get_db)):
    return svc.expiring_lots(db, p.company_id, days)


@router.get("/lots")
def lots(item_id: int | None = None, status: str | None = None, limit: int = Query(100, le=500), offset: int = 0,
         p: Principal = Depends(require("inventory.stock.read")), db: Session = Depends(get_db)):
    stmt = select(Lot).where(Lot.company_id == p.company_id)
    if item_id:
        stmt = stmt.where(Lot.item_id == item_id)
    if status:
        stmt = stmt.where(Lot.status == status)
    return paginate(db, stmt.order_by(Lot.expiry_date.nulls_last(), Lot.id), limit, offset)


@router.get("/reservations")
def reservations(item_id: int | None = None, status: str = "active", limit: int = Query(100, le=500),
                 offset: int = 0, p: Principal = Depends(require("inventory.stock.read")),
                 db: Session = Depends(get_db)):
    stmt = select(StockReservation).where(StockReservation.company_id == p.company_id,
                                          StockReservation.status == status)
    if item_id:
        stmt = stmt.where(StockReservation.item_id == item_id)
    return paginate(db, stmt.order_by(StockReservation.id.desc()), limit, offset)


@router.get("/consistency")
def consistency(p: Principal = Depends(require("inventory.stock.read")), db: Session = Depends(get_db)):
    """Verifica que los saldos coincidan con el libro de movimientos (lista vacía = consistente)."""
    diffs = stock.consistency_report(db, p.company_id)
    return {"consistent": not diffs, "differences": diffs}


# ------------------------------------------------------------------ documentos
@router.get("/documents")
def list_documents(doc_type: str | None = None, status: str | None = None, limit: int = Query(50, le=500),
                   offset: int = 0, p: Principal = Depends(require("inventory.document.read")),
                   db: Session = Depends(get_db)):
    stmt = select(InventoryDocument).where(InventoryDocument.company_id == p.company_id)
    if doc_type:
        stmt = stmt.where(InventoryDocument.doc_type == doc_type)
    if status:
        stmt = stmt.where(InventoryDocument.status == status)
    return paginate(db, stmt.order_by(InventoryDocument.id.desc()), limit, offset, "lines")


@router.post("/documents", status_code=201)
def create_document(body: DocumentIn, p: Principal = Depends(require("inventory.document.create")),
                    db: Session = Depends(get_db)):
    doc = svc.create_document(db, p, body.model_dump())
    db.commit()
    return to_dict(doc, "lines")


@router.post("/documents/{doc_id}/approve")
def approve_document(doc_id: int, p: Principal = Depends(require("inventory.document.approve")),
                     db: Session = Depends(get_db)):
    doc = svc.approve_document(db, p, doc_id)
    db.commit()
    return to_dict(doc, "lines")


@router.post("/documents/{doc_id}/post")
def post_document(doc_id: int, p: Principal = Depends(require("inventory.document.post")),
                  db: Session = Depends(get_db)):
    doc = svc.post_document(db, p, doc_id)
    db.commit()
    return to_dict(doc, "lines")


# ------------------------------------------------------------------ conteos
@router.get("/counts")
def list_counts(limit: int = Query(50, le=500), offset: int = 0,
                p: Principal = Depends(require("inventory.count.read")), db: Session = Depends(get_db)):
    stmt = select(PhysicalCount).where(PhysicalCount.company_id == p.company_id).order_by(PhysicalCount.id.desc())
    return paginate(db, stmt, limit, offset)


@router.get("/counts/{count_id}")
def get_count(count_id: int, blind: bool = True, p: Principal = Depends(require("inventory.count.read")),
              db: Session = Depends(get_db)):
    """Conteo ciego: oculta la existencia del sistema mientras está abierto (blind=false solo para aprobadores)."""
    cnt = get_owned(db, PhysicalCount, count_id, p.company_id)
    out = to_dict(cnt, "lines")
    if cnt.status == "open" and (blind or not p.has("inventory.count.approve")):
        for ln in out["lines"]:
            ln.pop("system_qty", None)
            ln.pop("difference", None)
    return out


@router.post("/counts", status_code=201)
def open_count(body: CountOpenIn, p: Principal = Depends(require("inventory.count.create")),
               db: Session = Depends(get_db)):
    cnt = svc.open_count(db, p, body.warehouse_id, body.count_date, body.notes)
    db.commit()
    return {"id": cnt.id, "number": cnt.number, "lines": len(cnt.lines)}


@router.post("/counts/{count_id}/entries")
def record_count(count_id: int, body: CountRecordIn, p: Principal = Depends(require("inventory.count.create")),
                 db: Session = Depends(get_db)):
    cnt = svc.record_count(db, p, count_id, [e.model_dump() for e in body.entries])
    db.commit()
    return {"id": cnt.id, "pending": sum(1 for ln in cnt.lines if ln.counted_qty is None)}


@router.post("/counts/{count_id}/close")
def close_count(count_id: int, p: Principal = Depends(require("inventory.count.approve")),
                db: Session = Depends(get_db)):
    cnt = svc.close_count(db, p, count_id)
    db.commit()
    return to_dict(cnt, "lines")

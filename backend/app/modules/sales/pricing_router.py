"""Listas de precios, promociones y consulta de precios de venta."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import check_company_refs, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.errors import BusinessRuleViolation, Conflict
from app.core.schemas import CurrencyField, QtyField
from app.core.serialize import to_dict
from app.modules.masters.models import Item, Party
from app.modules.sales import pricing
from app.modules.sales.models import PriceList, PriceListItem, Promotion

router = APIRouter(prefix="/sales", tags=["Ventas: precios y promociones"],
                   dependencies=[Depends(require_module("sales"))])


# ---------------------------------------------------------------- listas de precios
class PriceListIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    currency: str = CurrencyField()
    valid_from: date
    valid_to: date | None = None
    is_default: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class PriceListPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    valid_to: date | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PriceItemIn(BaseModel):
    item_id: int
    min_qty: Decimal = QtyField()
    unit_price: Decimal = Field(ge=0)


class PriceItemsIn(BaseModel):
    items: list[PriceItemIn] = Field(max_length=5000)


class CustomersIn(BaseModel):
    customer_ids: list[int] = Field(max_length=5000)


def _clear_default(db: Session, company_id: int, currency: str, keep_id: int | None = None) -> None:
    """Una sola lista predeterminada por moneda: se desmarca la anterior ANTES de marcar la nueva (índice único)."""
    stmt = update(PriceList).where(PriceList.company_id == company_id, PriceList.currency == currency,
                                   PriceList.is_default.is_(True))
    if keep_id is not None:
        stmt = stmt.where(PriceList.id != keep_id)
    db.execute(stmt.values(is_default=False))


def _list_out(db: Session, pl: PriceList, detail: bool = False) -> dict:
    out = to_dict(pl, "items") if detail else to_dict(pl)
    customers = db.execute(select(Party.id, Party.legal_name).where(Party.price_list_id == pl.id)
                           .order_by(Party.legal_name)).all()
    out["customers_count"] = len(customers)
    out["items_count"] = len(pl.items)
    if detail:
        out["customers"] = [{"id": c.id, "legal_name": c.legal_name} for c in customers]
    return out


@router.get("/price-lists")
def list_price_lists(p: Principal = Depends(require("sales.pricing.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(PriceList).where(PriceList.company_id == p.company_id)
                      .order_by(PriceList.is_default.desc(), PriceList.code)).all()
    return [_list_out(db, pl) for pl in rows]


@router.post("/price-lists", status_code=201)
def create_price_list(body: PriceListIn, p: Principal = Depends(require("sales.pricing.admin")),
                      db: Session = Depends(get_db)):
    if body.valid_to and body.valid_to < body.valid_from:
        raise BusinessRuleViolation("La vigencia final no puede ser anterior a la inicial")
    if db.scalar(select(PriceList.id).where(PriceList.company_id == p.company_id, PriceList.code == body.code)):
        raise Conflict("Ya existe una lista con ese código")
    if body.is_default:
        _clear_default(db, p.company_id, body.currency)
    pl = PriceList(company_id=p.company_id, **body.model_dump())
    db.add(pl)
    db.flush()
    log_action(db, "create", "price_lists", pl.id, f"Lista de precios {pl.code} ({pl.currency})")
    db.commit()
    return _list_out(db, pl, detail=True)


@router.get("/price-lists/{list_id}")
def get_price_list(list_id: int, p: Principal = Depends(require("sales.pricing.read")), db: Session = Depends(get_db)):
    return _list_out(db, get_owned(db, PriceList, list_id, p.company_id), detail=True)


@router.patch("/price-lists/{list_id}")
def update_price_list(list_id: int, body: PriceListPatch, p: Principal = Depends(require("sales.pricing.admin")),
                      db: Session = Depends(get_db)):
    pl = get_owned(db, PriceList, list_id, p.company_id, lock=True)
    data = body.model_dump(exclude_unset=True)
    if data.get("is_default"):
        _clear_default(db, p.company_id, pl.currency, keep_id=pl.id)
    for k, v in data.items():
        setattr(pl, k, v)
    if pl.valid_to and pl.valid_to < pl.valid_from:
        raise BusinessRuleViolation("La vigencia final no puede ser anterior a la inicial")
    db.commit()
    return _list_out(db, pl, detail=True)


@router.put("/price-lists/{list_id}/items")
def set_price_items(list_id: int, body: PriceItemsIn, p: Principal = Depends(require("sales.pricing.admin")),
                    db: Session = Depends(get_db)):
    """Reemplaza los precios de la lista. Varios tramos del mismo artículo = descuento por volumen."""
    pl = get_owned(db, PriceList, list_id, p.company_id, lock=True)
    seen = set()
    for it in body.items:
        get_owned(db, Item, it.item_id, p.company_id)
        key = (it.item_id, it.min_qty)
        if key in seen:
            raise BusinessRuleViolation("Hay tramos repetidos para el mismo artículo y cantidad mínima")
        seen.add(key)
    before = len(pl.items)
    pl.items.clear()
    db.flush()
    pl.items.extend(PriceListItem(**it.model_dump()) for it in body.items)
    log_action(db, "update", "price_lists", pl.id, f"Precios de la lista {pl.code}: {before} -> {len(body.items)} tramos")
    db.commit()
    db.refresh(pl)
    return _list_out(db, pl, detail=True)


@router.put("/price-lists/{list_id}/customers")
def set_price_customers(list_id: int, body: CustomersIn, p: Principal = Depends(require("sales.pricing.admin")),
                        db: Session = Depends(get_db)):
    """Define exactamente qué clientes usan la lista (los que salen quedan con la lista predeterminada)."""
    pl = get_owned(db, PriceList, list_id, p.company_id, lock=True)
    for cid in body.customer_ids:
        c = get_owned(db, Party, cid, p.company_id)
        if not c.is_customer:
            raise BusinessRuleViolation(f"{c.legal_name} no es cliente")
    db.execute(update(Party).where(Party.company_id == p.company_id, Party.price_list_id == pl.id,
                                   Party.id.notin_(body.customer_ids or [0])).values(price_list_id=None))
    if body.customer_ids:
        db.execute(update(Party).where(Party.company_id == p.company_id, Party.id.in_(body.customer_ids))
                   .values(price_list_id=pl.id))
    log_action(db, "update", "price_lists", pl.id, f"Clientes de la lista {pl.code}: {len(body.customer_ids)}")
    db.commit()
    return _list_out(db, pl, detail=True)


# ---------------------------------------------------------------- promociones
class PromotionIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    discount_pct: Decimal = Field(gt=0, le=100)
    valid_from: date
    valid_to: date
    item_id: int | None = None
    category_id: int | None = None
    customer_id: int | None = None
    min_qty: Decimal | None = Field(default=None, gt=0)


class PromotionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    valid_to: date | None = None
    is_active: bool | None = None


def _promo_out(db: Session, pr: Promotion) -> dict:
    out = to_dict(pr)
    today = date.today()
    out["state"] = ("inactive" if not pr.is_active else "scheduled" if pr.valid_from > today
                    else "expired" if pr.valid_to < today else "active")
    return out


@router.get("/promotions")
def list_promotions(p: Principal = Depends(require("sales.pricing.read")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Promotion).where(Promotion.company_id == p.company_id)
                      .order_by(Promotion.valid_to.desc(), Promotion.code)).all()
    return [_promo_out(db, pr) for pr in rows]


@router.post("/promotions", status_code=201)
def create_promotion(body: PromotionIn, p: Principal = Depends(require("sales.pricing.admin")),
                     db: Session = Depends(get_db)):
    data = body.model_dump()
    if data["valid_to"] < data["valid_from"]:
        raise BusinessRuleViolation("La vigencia final no puede ser anterior a la inicial")
    if data["item_id"] and data["category_id"]:
        raise BusinessRuleViolation("La promoción aplica a un artículo o a una categoría, no a ambos")
    if db.scalar(select(Promotion.id).where(Promotion.company_id == p.company_id, Promotion.code == data["code"])):
        raise Conflict("Ya existe una promoción con ese código")
    check_company_refs(db, Promotion, p.company_id, data)
    pr = Promotion(company_id=p.company_id, **data)
    db.add(pr)
    db.flush()
    log_action(db, "create", "promotions", pr.id, f"Promoción {pr.code}: {pr.discount_pct} %")
    db.commit()
    return _promo_out(db, pr)


@router.patch("/promotions/{promo_id}")
def update_promotion(promo_id: int, body: PromotionPatch, p: Principal = Depends(require("sales.pricing.admin")),
                     db: Session = Depends(get_db)):
    pr = get_owned(db, Promotion, promo_id, p.company_id, lock=True)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(pr, k, v)
    if pr.valid_to < pr.valid_from:
        raise BusinessRuleViolation("La vigencia final no puede ser anterior a la inicial")
    db.commit()
    return _promo_out(db, pr)


# ---------------------------------------------------------------- consulta de precios
class PricingLine(BaseModel):
    item_id: int
    quantity: Decimal = QtyField()


class PricingIn(BaseModel):
    customer_id: int | None = None
    currency: str = CurrencyField()
    on: date | None = None
    lines: list[PricingLine] = Field(min_length=1, max_length=200)


@router.post("/pricing")
def price_preview(body: PricingIn, p: Principal = Depends(require("sales.pricing.read")), db: Session = Depends(get_db)):
    """Precio y descuento que se aplicarían a cada línea (lista del cliente, predeterminada o precio de lista)."""
    on = body.on or date.today()
    customer = get_owned(db, Party, body.customer_id, p.company_id) if body.customer_id else None
    lists = pricing.applicable_lists(db, p.company_id, customer, body.currency, on)
    out = []
    for ln in body.lines:
        item = get_owned(db, Item, ln.item_id, p.company_id)
        lp = pricing.price_line(db, p.company_id, customer, item, ln.quantity, body.currency, on, lists=lists)
        out.append({"item_id": item.id, "quantity": ln.quantity, "unit_price": lp.unit_price, "source": lp.source,
                    "price_list_id": lp.price_list_id, "discount_pct": lp.discount_pct,
                    "promotion_id": lp.promotion_id, "promotion": lp.promotion_name})
    return {"lists": [{"id": pl.id, "code": pl.code, "name": pl.name} for pl in lists], "lines": out}

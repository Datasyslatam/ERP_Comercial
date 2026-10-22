"""Precios de venta: listas de precios con tramos por cantidad y promociones con vigencia.

Orden para el precio unitario de una línea sin precio manual:
  1. lista de precios asignada al cliente (activa, de la moneda del documento y vigente en la fecha);
  2. lista predeterminada de la empresa para esa moneda;
  3. precio de lista del artículo.
Dentro de una lista se toma el tramo de mayor cantidad mínima que la cantidad pedida alcanza.

Descuento de una línea sin descuento manual: la promoción vigente de mayor porcentaje que aplique al artículo
(por artículo, por categoría o general), a la cantidad mínima y, si la promoción es exclusiva, al cliente.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.modules.masters.models import Item, Party
from app.modules.sales.models import PriceList, PriceListItem, Promotion


@dataclass
class LinePrice:
    unit_price: Decimal
    source: str  # manual | price_list | list_price | quote
    price_list_id: int | None = None
    discount_pct: Decimal = Decimal("0")
    promotion_id: int | None = None
    promotion_name: str | None = None


def _valid(stmt, model, on: date):
    return stmt.where(model.is_active.is_(True), model.valid_from <= on,
                      or_(model.valid_to.is_(None), model.valid_to >= on) if model is PriceList else model.valid_to >= on)


def applicable_lists(db: Session, company_id: int, customer: Party | None, currency: str, on: date) -> list[PriceList]:
    """Listas a consultar en orden de prioridad: la del cliente y luego la predeterminada."""
    out: list[PriceList] = []
    if customer is not None and customer.price_list_id:
        pl = db.scalar(_valid(select(PriceList).where(PriceList.id == customer.price_list_id,
                                                      PriceList.company_id == company_id,
                                                      PriceList.currency == currency), PriceList, on))
        if pl is not None:
            out.append(pl)
    default = db.scalar(_valid(select(PriceList).where(PriceList.company_id == company_id, PriceList.currency == currency,
                                                       PriceList.is_default.is_(True)), PriceList, on))
    if default is not None and default not in out:
        out.append(default)
    return out


def list_price(db: Session, lists: list[PriceList], item_id: int, qty: Decimal) -> tuple[Decimal, int] | None:
    for pl in lists:
        tier = db.scalar(select(PriceListItem).where(PriceListItem.price_list_id == pl.id, PriceListItem.item_id == item_id,
                                                     PriceListItem.min_qty <= qty)
                         .order_by(PriceListItem.min_qty.desc()).limit(1))
        if tier is not None:
            return tier.unit_price, pl.id
    return None


def best_promotion(db: Session, company_id: int, customer_id: int | None, item: Item, qty: Decimal,
                   on: date) -> Promotion | None:
    stmt = _valid(select(Promotion).where(Promotion.company_id == company_id), Promotion, on).where(
        or_(Promotion.item_id == item.id,
            Promotion.category_id == item.category_id if item.category_id else false(),
            (Promotion.item_id.is_(None)) & (Promotion.category_id.is_(None))),
        or_(Promotion.customer_id.is_(None), Promotion.customer_id == customer_id),
        or_(Promotion.min_qty.is_(None), Promotion.min_qty <= qty))
    return db.scalar(stmt.order_by(Promotion.discount_pct.desc(), Promotion.id).limit(1))


def price_line(db: Session, company_id: int, customer: Party | None, item: Item, qty: Decimal, currency: str, on: date,
               unit_price: Decimal | None = None, discount_pct: Decimal | None = None,
               lists: list[PriceList] | None = None) -> LinePrice:
    qty = Decimal(qty)
    if unit_price is not None:
        res = LinePrice(unit_price=Decimal(unit_price), source="manual")
    else:
        found = list_price(db, lists if lists is not None else applicable_lists(db, company_id, customer, currency, on),
                           item.id, qty)
        res = LinePrice(unit_price=found[0], source="price_list", price_list_id=found[1]) if found \
            else LinePrice(unit_price=item.list_price, source="list_price")
    if discount_pct is not None:
        res.discount_pct = Decimal(discount_pct)
    else:
        promo = best_promotion(db, company_id, customer.id if customer else None, item, qty, on)
        if promo is not None:
            res.discount_pct, res.promotion_id, res.promotion_name = promo.discount_pct, promo.id, promo.name
    return res


def apply_to_lines(db: Session, company_id: int, customer: Party, currency: str, on: date, lines: list[dict],
                   items: dict[int, Item]) -> None:
    """Completa en sitio unit_price, discount_pct, price_source y promotion_id de cada línea (dict)."""
    lists = applicable_lists(db, company_id, customer, currency, on)
    for ln in lines:
        if ln.get("price_source") == "quote":  # condiciones ya pactadas en la cotización
            continue
        lp = price_line(db, company_id, customer, items[ln["item_id"]], ln["quantity"], currency, on,
                        ln.get("unit_price"), ln.get("discount_pct"), lists)
        ln["unit_price"], ln["discount_pct"] = lp.unit_price, lp.discount_pct
        ln["price_source"], ln["promotion_id"] = lp.source, lp.promotion_id

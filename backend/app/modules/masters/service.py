"""Servicios de maestros: conversión de unidades y motor de cálculo de impuestos y retenciones."""
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolation
from app.core.money import ZERO, money
from app.modules.masters.models import Party, Tax, UomConversion


def convert_qty(db: Session, item_id: int, qty: Decimal, from_uom_id: int, to_uom_id: int) -> Decimal:
    if from_uom_id == to_uom_id:
        return qty
    for a, b, inverse in ((from_uom_id, to_uom_id, False), (to_uom_id, from_uom_id, True)):
        for it in (item_id, None):
            conv = db.scalar(select(UomConversion).where(
                UomConversion.item_id.is_(None) if it is None else UomConversion.item_id == it,
                UomConversion.from_uom_id == a, UomConversion.to_uom_id == b))
            if conv:
                return (qty / conv.factor) if inverse else (qty * conv.factor)
    raise BusinessRuleViolation("No existe conversión entre las unidades indicadas")


@dataclass
class TaxLine:
    tax: Tax
    base: Decimal
    amount: Decimal

    @property
    def is_withholding(self) -> bool:
        return self.tax.is_withholding


@dataclass
class TaxResult:
    subtotal: Decimal = ZERO
    taxes: list[TaxLine] = field(default_factory=list)  # IVA, impoconsumo
    withholdings: list[TaxLine] = field(default_factory=list)
    line_taxes: list[Decimal] = field(default_factory=list)

    @property
    def tax_total(self) -> Decimal:
        return sum((t.amount for t in self.taxes), ZERO)

    @property
    def withholding_total(self) -> Decimal:
        return sum((w.amount for w in self.withholdings), ZERO)

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax_total


def compute_taxes(lines: list[tuple[Decimal, Tax | None]], withholdings: list[Tax], side: str) -> TaxResult:
    """lines: (subtotal neto de descuentos, impuesto de la línea). side: 'sales' o 'purchases'."""
    res = TaxResult()
    by_tax: dict[int, TaxLine] = {}
    for subtotal, tax in lines:
        subtotal = money(subtotal)
        res.subtotal += subtotal
        amount = ZERO
        if tax is not None:
            if tax.is_withholding:
                raise BusinessRuleViolation(f"{tax.code} es una retención y no puede asignarse a una línea")
            if tax.applies_to not in (side, "both"):
                raise BusinessRuleViolation(f"El impuesto {tax.code} no aplica a {side}")
            amount = money(subtotal * tax.rate / 100)
            tl = by_tax.setdefault(tax.id, TaxLine(tax=tax, base=ZERO, amount=ZERO))
            tl.base += subtotal
            tl.amount += amount
        res.line_taxes.append(amount)
    res.taxes = list(by_tax.values())
    vat_total = sum((t.amount for t in res.taxes if t.tax.kind == "vat"), ZERO)
    for w in withholdings:
        if not w.is_active or w.applies_to not in (side, "both") or not w.is_withholding:
            continue
        base = vat_total if w.base == "vat" else res.subtotal
        if base <= 0 or base < w.min_base_amount:
            continue
        res.withholdings.append(TaxLine(tax=w, base=base, amount=money(base * w.rate / 100)))
    return res


def party_withholdings(db: Session, party: Party, company_is_agent: bool, side: str) -> list[Tax]:
    """En compras retenemos si somos agentes de retención; en ventas nos retiene el cliente si él es agente."""
    if side == "purchases" and not company_is_agent:
        return []
    if side == "sales" and not party.is_withholding_agent:
        return []
    return [t for t in party.withholdings if t.applies_to in (side, "both")]

"""Reglas de contabilización automática de los documentos comerciales (moneda funcional).

Cada función usa una clave de idempotencia derivada del documento origen: invocarla dos veces no duplica
el asiento. La trazabilidad documento → asiento queda en journal_entries.source_type/source_id.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.money import ZERO, money
from app.modules.accounting.ledger import LineSpec, post_entry, posting_account
from app.modules.accounting.models import JournalEntry
from app.modules.masters.models import Item, ItemCategory, Tax


def _item_account(db: Session, company_id: int, item_id: int | None, attr: str, fallback_key: str) -> int:
    if item_id:
        item = db.get(Item, item_id)
        if item and item.category_id:
            cat = db.get(ItemCategory, item.category_id)
            acc = getattr(cat, attr, None)
            if acc:
                return acc
    return posting_account(db, company_id, fallback_key)


def _tax_account(tax: Tax, side: str) -> int:
    acc = tax.sales_account_id if side == "sales" else tax.purchase_account_id
    if acc is None:
        from app.core.errors import BusinessRuleViolation

        raise BusinessRuleViolation(f"El impuesto {tax.code} no tiene cuenta contable para {side}")
    return acc


def post_inventory_value(db: Session, *, company_id: int, entry_date: date, key: str, description: str,
                         source_type: str, source_id: int, by_item: dict[int, Decimal], counter_key: str,
                         inbound: bool, user_id: int | None, counter_account_id: int | None = None,
                         cost_center_id: int | None = None) -> JournalEntry | None:
    """Asiento genérico inventario ↔ contrapartida. inbound=True: débito a inventario."""
    total = money(sum(by_item.values(), ZERO))
    if total == 0:
        return None
    inv: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for item_id, value in by_item.items():
        inv[_item_account(db, company_id, item_id, "inventory_account_id", "inventory")] += money(value)
    counter = counter_account_id or posting_account(db, company_id, counter_key)
    lines = []
    for acc, value in inv.items():
        lines.append(LineSpec(account_id=acc, debit=value if inbound else ZERO, credit=ZERO if inbound else value))
    diff = sum(inv.values(), ZERO)
    lines.append(LineSpec(account_id=counter, debit=ZERO if inbound else diff, credit=diff if inbound else ZERO,
                          cost_center_id=cost_center_id))
    return post_entry(db, company_id=company_id, entry_date=entry_date, journal_type="inventory",
                      description=description, lines=lines, idempotency_key=key, source_type=source_type,
                      source_id=source_id, user_id=user_id)


def post_supplier_invoice(db: Session, inv, user_id: int | None) -> JournalEntry:
    from app.modules.purchasing.models import GoodsReceiptLine

    rate = inv.exchange_rate
    lines: list[LineSpec] = []
    ppv = posting_account(db, inv.company_id, "purchase_price_variance")
    grni = posting_account(db, inv.company_id, "grni")
    for ln in inv.lines:
        value = money(ln.line_subtotal * rate)
        if ln.receipt_line_id:
            rl = db.get(GoodsReceiptLine, ln.receipt_line_id)
            accrued = money(ln.quantity * rl.unit_cost)
            lines.append(LineSpec(account_id=grni, debit=accrued, description=f"Cruce recepción {ln.description}"))
            if value != accrued:
                lines.append(LineSpec(account_id=ppv, debit=value - accrued if value > accrued else ZERO,
                                      credit=accrued - value if accrued > value else ZERO,
                                      description="Variación de precio de compra"))
        else:
            acc = ln.expense_account_id or _item_account(db, inv.company_id, ln.item_id, "expense_account_id",
                                                         "inventory_adjustment_loss")
            lines.append(LineSpec(account_id=acc, debit=value, cost_center_id=ln.cost_center_id,
                                  description=ln.description))
    for t in inv.taxes:
        tax = db.get(Tax, t.tax_id)
        amount = money(t.amount * rate)
        if t.is_withholding:
            lines.append(LineSpec(account_id=_tax_account(tax, "purchases"), credit=amount, party_id=inv.supplier_id,
                                  description=tax.name))
        else:
            lines.append(LineSpec(account_id=_tax_account(tax, "purchases"), debit=amount, description=tax.name))
    payable = money(inv.payable_total * rate)
    lines.append(LineSpec(account_id=posting_account(db, inv.company_id, "accounts_payable"), credit=payable,
                          party_id=inv.supplier_id, currency=inv.currency, amount_currency=inv.payable_total,
                          exchange_rate=rate))
    _balance_rounding(lines, ppv)
    return post_entry(db, company_id=inv.company_id, entry_date=inv.invoice_date, journal_type="purchases",
                      description=f"Factura proveedor {inv.supplier_invoice_number} ({inv.number})", lines=lines,
                      idempotency_key=f"supplier_invoice:{inv.id}", source_type="supplier_invoice",
                      source_id=inv.id, user_id=user_id)


def post_sales_invoice(db: Session, inv, user_id: int | None) -> JournalEntry:
    rate = inv.exchange_rate
    is_credit = inv.doc_type == "credit_note"
    lines: list[LineSpec] = []
    revenue: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for ln in inv.lines:
        key = "sales_returns" if is_credit else "revenue"
        acc = posting_account(db, inv.company_id, key) if is_credit else _item_account(
            db, inv.company_id, ln.item_id, "revenue_account_id", "revenue")
        revenue[acc] += money(ln.line_subtotal * rate)
    for acc, value in revenue.items():
        lines.append(LineSpec(account_id=acc, debit=value if is_credit else ZERO, credit=ZERO if is_credit else value))
    for t in inv.taxes:
        tax = db.get(Tax, t.tax_id)
        amount = money(t.amount * rate)
        lines.append(LineSpec(account_id=_tax_account(tax, "sales"), debit=amount if is_credit else ZERO,
                              credit=ZERO if is_credit else amount, description=tax.name))
    total = sum((ln.credit - ln.debit for ln in lines), ZERO)
    ar = posting_account(db, inv.company_id, "accounts_receivable")
    lines.append(LineSpec(account_id=ar, debit=total if total > 0 else ZERO, credit=-total if total < 0 else ZERO,
                          party_id=inv.customer_id, currency=inv.currency,
                          amount_currency=-inv.total if is_credit else inv.total, exchange_rate=rate))
    label = {"invoice": "Factura", "credit_note": "Nota crédito", "debit_note": "Nota débito"}[inv.doc_type]
    return post_entry(db, company_id=inv.company_id, entry_date=inv.issue_date, journal_type="sales",
                      description=f"{label} de venta {inv.full_number}", lines=lines,
                      idempotency_key=f"sales_invoice:{inv.id}", source_type="sales_invoice", source_id=inv.id,
                      user_id=user_id)


def post_payment(db: Session, pay, allocations: list[tuple], user_id: int | None,
                 igtf_tax: Tax | None = None) -> JournalEntry:
    """allocations: [(open_item, amount)] en moneda del documento (= moneda del pago)."""
    from app.modules.accounting.models import BankAccount, PaymentWithholding  # noqa: F401

    bank = db.get(BankAccount, pay.bank_account_id)
    rate = pay.exchange_rate
    company_id = pay.company_id
    lines: list[LineSpec] = []
    receivable = pay.kind == "receipt"
    party_acc = posting_account(db, company_id, "accounts_receivable" if receivable else "accounts_payable")
    settled = ZERO
    for item, amount in allocations:
        value = money(amount * item.exchange_rate)
        settled += value
        lines.append(LineSpec(account_id=party_acc, debit=ZERO if receivable else value,
                              credit=value if receivable else ZERO, party_id=pay.party_id, currency=item.currency,
                              amount_currency=-amount if receivable else amount, exchange_rate=item.exchange_rate,
                              description=f"Aplicación a {item.document_number}"))
    cash = money(pay.amount * rate)
    igtf = money(pay.igtf_amount * rate)
    if receivable:
        lines.append(LineSpec(account_id=bank.gl_account_id, debit=cash + igtf, currency=pay.currency,
                              amount_currency=pay.amount + pay.igtf_amount, exchange_rate=rate))
        for w in pay.withholdings:
            tax = db.get(Tax, w.tax_id)
            lines.append(LineSpec(account_id=_tax_account(tax, "sales"), debit=money(w.amount * rate),
                                  party_id=pay.party_id, description=f"Retención practicada por cliente: {tax.name}"))
        if igtf:
            lines.append(LineSpec(account_id=_tax_account(igtf_tax, "sales"), credit=igtf, description="IGTF percibido"))
    else:
        lines.append(LineSpec(account_id=bank.gl_account_id, credit=cash + igtf, currency=pay.currency,
                              amount_currency=-(pay.amount + pay.igtf_amount), exchange_rate=rate))
        if igtf:
            lines.append(LineSpec(account_id=_tax_account(igtf_tax, "purchases"), debit=igtf, description="IGTF pagado"))
    diff = sum((ln.debit - ln.credit for ln in lines), ZERO)
    if diff != 0:
        fx = posting_account(db, company_id, "fx_difference")
        lines.append(LineSpec(account_id=fx, debit=-diff if diff < 0 else ZERO, credit=diff if diff > 0 else ZERO,
                              description="Diferencia en cambio realizada"))
    kind = "Recibo de caja" if receivable else "Comprobante de egreso"
    return post_entry(db, company_id=company_id, entry_date=pay.payment_date, journal_type="treasury",
                      description=f"{kind} {pay.number}", lines=lines, idempotency_key=f"payment:{pay.id}",
                      source_type="payment", source_id=pay.id, user_id=user_id)


def _balance_rounding(lines: list[LineSpec], account_id: int) -> None:
    """Absorbe diferencias de redondeo de céntimos (≤ 1 unidad monetaria) en la cuenta indicada."""
    diff = sum((money(ln.debit) - money(ln.credit) for ln in lines), ZERO)
    if diff != 0 and abs(diff) <= Decimal("1"):
        lines.append(LineSpec(account_id=account_id, debit=-diff if diff < 0 else ZERO,
                              credit=diff if diff > 0 else ZERO, description="Ajuste por redondeo"))

"""Contabilidad operativa: comprobantes manuales, periodos, cierres, tesorería, conciliación y reportes."""
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import get_owned
from app.core.deps import Principal
from app.core.errors import BusinessRuleViolation, Conflict, NotFound
from app.core.money import ZERO, money
from app.core.numbering import next_number
from app.core.policies import enforce_approval_limit, enforce_sod
from app.modules.accounting.ledger import LineSpec, get_open_period, post_entry, posting_account, reverse_entry
from app.modules.accounting.models import (
    ADVANCE_TYPES,
    Account,
    AdvanceApplication,
    BankAccount,
    BankStatement,
    BankStatementLine,
    FiscalPeriod,
    JournalEntry,
    JournalLine,
    OpenItem,
    Payment,
    PaymentAllocation,
    PaymentWithholding,
)
from app.modules.accounting.posting import post_advance_application, post_payment
from app.modules.masters.models import Party, Tax


# ---------------------------------------------------------------- comprobantes manuales
def create_manual_entry(db: Session, p: Principal, data: dict) -> JournalEntry:
    period = get_open_period(db, p.company_id, data["entry_date"])
    entry = JournalEntry(company_id=p.company_id, number=f"BR-{uuid.uuid4().hex[:10].upper()}",
                         entry_date=data["entry_date"], period_id=period.id, journal_type=data.get("journal_type", "general"),
                         description=data["description"], status="draft",
                         idempotency_key=f"manual:{uuid.uuid4().hex}", created_by_id=p.user_id)
    for i, ln in enumerate(data["lines"], start=1):
        get_owned(db, Account, ln["account_id"], p.company_id)
        entry.lines.append(JournalLine(company_id=p.company_id, line_no=i, account_id=ln["account_id"],
                                       debit=money(ln.get("debit") or 0), credit=money(ln.get("credit") or 0),
                                       description=ln.get("description"), party_id=ln.get("party_id"),
                                       cost_center_id=ln.get("cost_center_id")))
    db.add(entry)
    db.flush()
    return entry


def post_manual_entry(db: Session, p: Principal, entry_id: int) -> JournalEntry:
    draft = get_owned(db, JournalEntry, entry_id, p.company_id, lock=True)
    if draft.status != "draft":
        raise Conflict("El comprobante no está en borrador")
    enforce_sod(p, "sod_journal_self_post", draft.created_by_id, "contabilizar")
    lines = [LineSpec(account_id=ln.account_id, debit=ln.debit, credit=ln.credit, description=ln.description,
                      party_id=ln.party_id, cost_center_id=ln.cost_center_id) for ln in draft.lines]
    posted = post_entry(db, company_id=p.company_id, entry_date=draft.entry_date, journal_type=draft.journal_type,
                        description=draft.description, lines=lines, idempotency_key=draft.idempotency_key + ":posted",
                        source_type="manual", source_id=None, user_id=p.user_id, created_by_id=draft.created_by_id)
    db.delete(draft)  # el borrador se reemplaza por el comprobante numerado definitivo
    db.flush()
    return posted


def delete_draft(db: Session, p: Principal, entry_id: int) -> None:
    draft = get_owned(db, JournalEntry, entry_id, p.company_id, lock=True)
    if draft.status != "draft":
        raise BusinessRuleViolation("Solo se eliminan borradores; los contabilizados se reversan")
    db.delete(draft)


def reverse(db: Session, p: Principal, entry_id: int, reversal_date: date, reason: str) -> JournalEntry:
    entry = get_owned(db, JournalEntry, entry_id, p.company_id)
    if entry.source_type not in (None, "manual"):
        raise BusinessRuleViolation("Los asientos generados por documentos se corrigen desde el documento origen "
                                    f"({entry.source_type}); no se reversan manualmente")
    return reverse_entry(db, company_id=p.company_id, entry_id=entry.id, reversal_date=reversal_date, reason=reason,
                         user_id=p.user_id)


# ---------------------------------------------------------------- periodos
def close_period(db: Session, p: Principal, year: int, month: int) -> FiscalPeriod:
    period = db.scalar(select(FiscalPeriod).where(FiscalPeriod.company_id == p.company_id, FiscalPeriod.year == year,
                                                  FiscalPeriod.month == month).with_for_update())
    if period is None:
        raise BusinessRuleViolation("Periodo inexistente")
    if period.status == "closed":
        raise Conflict("El periodo ya está cerrado")
    drafts = db.scalar(select(func.count()).select_from(JournalEntry).where(
        JournalEntry.period_id == period.id, JournalEntry.status == "draft"))
    if drafts:
        raise BusinessRuleViolation(f"Hay {drafts} comprobantes en borrador en el periodo")
    pending_edocs = db.scalar(text("""select count(*) from sales_invoices where company_id = :c and status = 'issued'
        and edoc_status <> 'accepted' and issue_date between :s and :e"""),
        {"c": p.company_id, "s": period.start_date, "e": period.end_date})
    if pending_edocs:
        raise BusinessRuleViolation(f"Hay {pending_edocs} documentos electrónicos sin aceptar en el periodo")
    period.status, period.closed_by_id, period.closed_at = "closed", p.user_id, datetime.now(UTC)
    log_action(db, "close", "fiscal_periods", period.id, f"Cierre {year}-{month:02d}")
    return period


def reopen_period(db: Session, p: Principal, year: int, month: int, reason: str) -> FiscalPeriod:
    if not reason or len(reason) < 10:
        raise BusinessRuleViolation("La reapertura exige una justificación (mínimo 10 caracteres)")
    period = db.scalar(select(FiscalPeriod).where(FiscalPeriod.company_id == p.company_id, FiscalPeriod.year == year,
                                                  FiscalPeriod.month == month).with_for_update())
    if period is None or period.status != "closed":
        raise BusinessRuleViolation("El periodo no está cerrado")
    if period.closed_by_id == p.user_id and not p.user.is_superadmin:
        raise BusinessRuleViolation("La reapertura debe autorizarla un usuario distinto a quien cerró el periodo")
    period.status, period.reopened_by_id, period.reopened_at, period.reopen_reason = \
        "open", p.user_id, datetime.now(UTC), reason
    log_action(db, "reopen", "fiscal_periods", period.id, reason)
    return period


def close_year(db: Session, p: Principal, year: int) -> JournalEntry:
    """Asiento de cierre: traslada ingresos, costos y gastos del año a resultados acumulados."""
    rows = db.execute(text("""
        select a.id, sum(l.debit - l.credit) bal from journal_lines l
          join journal_entries e on e.id = l.entry_id join accounts a on a.id = l.account_id
         where e.company_id = :c and e.status in ('posted','reversed') and e.journal_type <> 'closing'
           and e.entry_date between :s and :e and a.account_type in ('revenue','expense','cost')
         group by a.id having sum(l.debit - l.credit) <> 0"""),
        {"c": p.company_id, "s": date(year, 1, 1), "e": date(year, 12, 31)}).all()
    if not rows:
        raise BusinessRuleViolation("No hay saldos de resultados para cerrar")
    lines = [LineSpec(account_id=r.id, debit=-r.bal if r.bal < 0 else ZERO, credit=r.bal if r.bal > 0 else ZERO)
             for r in rows]
    net = sum((r.bal for r in rows), ZERO)  # >0 pérdida, <0 utilidad
    lines.append(LineSpec(account_id=posting_account(db, p.company_id, "retained_earnings"),
                          debit=net if net > 0 else ZERO, credit=-net if net < 0 else ZERO,
                          description="Resultado del ejercicio"))
    return post_entry(db, company_id=p.company_id, entry_date=date(year, 12, 31), journal_type="closing",
                      description=f"Cierre del ejercicio {year}", lines=lines, idempotency_key=f"year_close:{year}",
                      source_type="year_close", source_id=year, user_id=p.user_id)


# ---------------------------------------------------------------- tesorería
def register_payment(db: Session, p: Principal, data: dict) -> Payment:
    """Recaudo o pago aplicado a partidas abiertas. Idempotente por idempotency_key."""
    existing = db.scalar(select(Payment).where(Payment.company_id == p.company_id,
                                               Payment.idempotency_key == data["idempotency_key"]))
    if existing:
        return existing
    kind = data["kind"]
    party = get_owned(db, Party, data["party_id"], p.company_id)
    bank = get_owned(db, BankAccount, data["bank_account_id"], p.company_id)
    if bank.currency != data["currency"]:
        raise BusinessRuleViolation("La moneda del pago debe coincidir con la de la cuenta bancaria")
    from app.modules.purchasing.service import _resolve_rate

    rate = _resolve_rate(db, p.company, data["currency"], data["payment_date"], data.get("exchange_rate"))
    if kind == "disbursement":
        enforce_approval_limit(db, p, "payment", money(Decimal(data["amount"]) * rate))
    pay = Payment(company_id=p.company_id, number=next_number(db, p.company_id, f"payment_{kind}"), kind=kind,
                  party_id=party.id, payment_date=data["payment_date"], bank_account_id=bank.id,
                  method=data["method"], currency=data["currency"], exchange_rate=rate,
                  amount=money(data["amount"]), reference=data.get("reference"),
                  idempotency_key=data["idempotency_key"], created_by_id=p.user_id)
    if (kind == "receipt" and not party.is_customer) or (kind == "disbursement" and not party.is_supplier):
        raise BusinessRuleViolation("El tercero no es " + ("cliente" if kind == "receipt" else "proveedor"))
    wh_total = ZERO
    side = "sales" if kind == "receipt" else "purchases"
    for w in data.get("withholdings") or []:
        tax = get_owned(db, Tax, w["tax_id"], p.company_id)
        if not tax.is_withholding:
            raise BusinessRuleViolation(f"{tax.code} no es una retención")
        if tax.applies_to not in (side, "both"):
            raise BusinessRuleViolation(f"La retención {tax.code} no aplica a {'ventas' if side == 'sales' else 'compras'}")
        if kind == "disbursement" and not p.company.is_withholding_agent:
            raise BusinessRuleViolation("La empresa no es agente de retención")
        amount = money(w["amount"])
        # En recaudos se guarda el comprobante que entrega el cliente (libro de ventas); en pagos se genera.
        pay.withholdings.append(PaymentWithholding(
            tax_id=tax.id, base=money(w.get("base") or 0), amount=amount,
            certificate_number=(w.get("certificate_number") or None) if kind == "receipt" else None))
        wh_total += amount
    pay.withholding_amount = wh_total
    allocations = []
    alloc_total = ZERO
    for a in data["allocations"]:
        item = db.scalar(select(OpenItem).where(OpenItem.id == a["open_item_id"]).with_for_update())
        if item is None or item.company_id != p.company_id or item.party_id != party.id:
            raise BusinessRuleViolation("La partida no pertenece al tercero")
        if item.kind != ("receivable" if kind == "receipt" else "payable"):
            raise BusinessRuleViolation("Tipo de partida incompatible con el pago")
        if item.document_type in ADVANCE_TYPES:
            raise BusinessRuleViolation("Un anticipo no se paga: se cruza contra facturas")
        if item.currency != pay.currency:
            raise BusinessRuleViolation("La moneda del pago debe coincidir con la de la partida")
        amount = money(a["amount"])
        if amount <= 0 or amount > item.open_amount:
            raise BusinessRuleViolation(f"Monto inválido para {item.document_number}: saldo {item.open_amount}")
        item.open_amount -= amount
        item.status = "paid" if item.open_amount == 0 else "partial"
        pay.allocations.append(PaymentAllocation(open_item_id=item.id, amount=amount))
        allocations.append((item, amount))
        alloc_total += amount
    if kind == "disbursement" and pay.withholdings:
        _check_not_withheld(db, [it for it, _ in allocations], [w.tax_id for w in pay.withholdings])
        if p.company.country_code == "VE" and len(allocations) > 1:
            raise BusinessRuleViolation("En Venezuela la retención se practica por factura: registre un pago por "
                                        "cada factura con retención")
        wh_taxes = {t.id: t for t in db.scalars(select(Tax).where(Tax.id.in_([w.tax_id for w in pay.withholdings])))}
        for w in pay.withholdings:
            w.certificate_number = withholding_certificate_number(db, p, pay.payment_date, wh_taxes[w.tax_id])
    if wh_total and not allocations:
        raise BusinessRuleViolation("Las retenciones se practican sobre facturas: aplique el pago a una factura")
    if alloc_total > pay.amount + wh_total:
        raise BusinessRuleViolation("Lo aplicado supera el pago más las retenciones",
                                    details={"applied": str(alloc_total), "payment": str(pay.amount),
                                             "withholdings": str(wh_total)})
    if alloc_total < wh_total:
        raise BusinessRuleViolation("Las retenciones no pueden superar lo aplicado a facturas")
    # Lo que no se aplica a facturas queda como anticipo: saldo a favor del tercero para cruzar después.
    advance = pay.amount + wh_total - alloc_total
    igtf_tax = None
    if p.company.country_code == "VE" and pay.currency != p.company.functional_currency:
        igtf_tax = db.scalar(select(Tax).where(Tax.company_id == p.company_id, Tax.kind == "igtf",
                                               Tax.is_active.is_(True)))
        applies = igtf_tax is not None and (kind == "disbursement" or p.company.is_special_taxpayer)
        if applies:
            pay.igtf_amount = money(pay.amount * igtf_tax.rate / 100)
    db.add(pay)
    db.flush()
    entry = post_payment(db, pay, allocations, p.user_id, igtf_tax, advance)
    pay.journal_entry_id = entry.id
    if advance:
        db.add(OpenItem(company_id=p.company_id, kind="receivable" if kind == "receipt" else "payable",
                        party_id=party.id, document_type="advance", document_id=pay.id, document_number=pay.number,
                        issue_date=pay.payment_date, due_date=pay.payment_date, currency=pay.currency,
                        exchange_rate=pay.exchange_rate, original_amount=advance, open_amount=advance,
                        journal_entry_id=entry.id))
    log_action(db, "post", "payments", pay.id, f"{pay.number} {pay.amount} {pay.currency}")
    return pay


def void_payment(db: Session, p: Principal, payment_id: int, reason: str, on: date | None = None) -> Payment:
    pay = get_owned(db, Payment, payment_id, p.company_id, lock=True)
    if pay.status == "voided":
        raise Conflict("El pago ya está anulado")
    adv = db.scalar(select(OpenItem).where(OpenItem.company_id == p.company_id, OpenItem.document_type == "advance",
                                           OpenItem.document_id == pay.id).with_for_update())
    if adv is not None and adv.open_amount != adv.original_amount:
        raise Conflict("El anticipo de este pago ya se cruzó con facturas: anule primero esos cruces")
    reverse_entry(db, company_id=p.company_id, entry_id=pay.journal_entry_id, reversal_date=on or date.today(),
                  reason=f"Anulación pago {pay.number}: {reason}", user_id=p.user_id)
    for a in pay.allocations:
        item = db.get(OpenItem, a.open_item_id, with_for_update=True)
        item.open_amount += a.amount
        item.status = "open" if item.open_amount == item.original_amount else "partial"
    if adv is not None:
        adv.open_amount, adv.status = ZERO, "cancelled"
    pay.status = "voided"
    log_action(db, "void", "payments", pay.id, reason)
    return pay


# ---------------------------------------------------------------- anticipos y saldos a favor
def apply_advance(db: Session, p: Principal, advance_item_id: int, data: dict) -> list[AdvanceApplication]:
    """Cruza un anticipo (saldo a favor del tercero) contra sus facturas abiertas en la misma moneda."""
    adv = db.scalar(select(OpenItem).where(OpenItem.id == advance_item_id).with_for_update())
    if adv is None or adv.company_id != p.company_id or adv.document_type not in ADVANCE_TYPES:
        raise NotFound("Anticipo no encontrado")
    if adv.status not in ("open", "partial"):
        raise BusinessRuleViolation("El anticipo no tiene saldo disponible")
    on = data.get("application_date") or date.today()
    if on < adv.issue_date:
        raise BusinessRuleViolation("El cruce no puede ser anterior al anticipo")
    rows, total = [], ZERO
    for a in data["allocations"]:
        item = db.scalar(select(OpenItem).where(OpenItem.id == a["open_item_id"]).with_for_update())
        if item is None or item.company_id != p.company_id or item.party_id != adv.party_id or item.kind != adv.kind:
            raise BusinessRuleViolation("La partida no pertenece al mismo tercero")
        if item.document_type in ADVANCE_TYPES:
            raise BusinessRuleViolation("Un anticipo no se cruza contra otro anticipo")
        if item.currency != adv.currency:
            raise BusinessRuleViolation("El anticipo y la factura deben estar en la misma moneda")
        amount = money(a["amount"])
        if amount <= 0 or amount > item.open_amount:
            raise BusinessRuleViolation(f"Monto inválido para {item.document_number}: saldo {item.open_amount}")
        rows.append((item, amount))
        total += amount
    if not rows:
        raise BusinessRuleViolation("Indique al menos una factura")
    if total > adv.open_amount:
        raise BusinessRuleViolation(f"El cruce ({total}) supera el saldo del anticipo ({adv.open_amount})")
    apps = [AdvanceApplication(company_id=p.company_id, advance_item_id=adv.id, open_item_id=item.id, amount=amount,
                               application_date=on, created_by_id=p.user_id) for item, amount in rows]
    db.add_all(apps)
    db.flush()
    entry = post_advance_application(db, adv, rows, on, apps[0].id, p.user_id)
    for app_, (item, amount) in zip(apps, rows, strict=True):
        app_.journal_entry_id = entry.id
        item.open_amount -= amount
        item.status = "paid" if item.open_amount == 0 else "partial"
    adv.open_amount -= total
    adv.status = "paid" if adv.open_amount == 0 else "partial"
    log_action(db, "post", "advance_applications", apps[0].id,
               f"Cruce de {adv.document_number} por {total} {adv.currency}")
    return apps


def void_advance_application(db: Session, p: Principal, application_id: int, reason: str) -> list[AdvanceApplication]:
    first = get_owned(db, AdvanceApplication, application_id, p.company_id, lock=True)
    if first.status == "voided":
        raise Conflict("El cruce ya está anulado")
    apps = list(db.scalars(select(AdvanceApplication).where(
        AdvanceApplication.journal_entry_id == first.journal_entry_id).with_for_update()))
    reverse_entry(db, company_id=p.company_id, entry_id=first.journal_entry_id, reversal_date=date.today(),
                  reason=f"Anulación de cruce de anticipo: {reason}", user_id=p.user_id)
    adv = db.get(OpenItem, first.advance_item_id, with_for_update=True)
    for a in apps:
        item = db.get(OpenItem, a.open_item_id, with_for_update=True)
        item.open_amount += a.amount
        item.status = "open" if item.open_amount == item.original_amount else "partial"
        adv.open_amount += a.amount
        a.status = "voided"
    adv.status = "open" if adv.open_amount == adv.original_amount else "partial"
    log_action(db, "void", "advance_applications", first.id, reason)
    return apps


def aging(db: Session, company_id: int, kind: str, as_of: date, party_id: int | None = None) -> dict:
    stmt = select(OpenItem, Party.legal_name).join(Party, Party.id == OpenItem.party_id).where(
        OpenItem.company_id == company_id, OpenItem.kind == kind, OpenItem.status.in_(("open", "partial")))
    if party_id:
        stmt = stmt.where(OpenItem.party_id == party_id)
    rows = db.execute(stmt).all()
    buckets = ("current", "1_30", "31_60", "61_90", "over_90", "advances")
    out = []
    totals = defaultdict(lambda: ZERO)
    for oi, name in rows:
        advance = oi.document_type in ADVANCE_TYPES
        days = 0 if advance else (as_of - oi.due_date).days
        b = "advances" if advance else "current" if days <= 0 else "1_30" if days <= 30 else "31_60" if days <= 60 \
            else "61_90" if days <= 90 else "over_90"
        # Los anticipos son saldo a favor del tercero: restan de su cartera
        functional = money(oi.open_amount * oi.exchange_rate) * (-1 if advance else 1)
        totals[b] += functional
        out.append({"open_item_id": oi.id, "party_id": oi.party_id, "party": name, "document": oi.document_number,
                    "document_type": oi.document_type, "document_id": oi.document_id, "due_date": oi.due_date,
                    "days_overdue": max(days, 0), "bucket": b, "currency": oi.currency, "is_advance": advance,
                    "open_amount": -oi.open_amount if advance else oi.open_amount,
                    "open_amount_functional": functional})
    labels = {"current": "Por vencer", "1_30": "1 a 30 días", "31_60": "31 a 60 días", "61_90": "61 a 90 días",
              "over_90": "Más de 90 días", "advances": "Anticipos (saldo a favor)"}
    return {"as_of": as_of, "kind": kind, "items": sorted(out, key=lambda x: -x["days_overdue"]),
            "totals": {b: totals[b] for b in buckets}, "labels": labels, "total": sum(totals.values(), ZERO)}


# ---------------------------------------------------------------- conciliación bancaria
def import_statement(db: Session, p: Principal, data: dict) -> BankStatement:
    bank = get_owned(db, BankAccount, data["bank_account_id"], p.company_id)
    st = BankStatement(company_id=p.company_id, bank_account_id=bank.id, statement_date=data["statement_date"],
                       opening_balance=money(data["opening_balance"]), closing_balance=money(data["closing_balance"]),
                       source_filename=data.get("source_filename"), imported_by_id=p.user_id)
    total = ZERO
    for ln in data["lines"]:
        st.lines.append(BankStatementLine(txn_date=ln["txn_date"], description=ln["description"][:255],
                                          reference=ln.get("reference"), amount=money(ln["amount"])))
        total += money(ln["amount"])
    if st.opening_balance + total != st.closing_balance:
        raise BusinessRuleViolation("El extracto no cuadra: saldo inicial + movimientos ≠ saldo final",
                                    details={"computed": str(st.opening_balance + total)})
    db.add(st)
    db.flush()
    return st


def auto_match(db: Session, p: Principal, statement_id: int, window_days: int = 3) -> dict:
    st = get_owned(db, BankStatement, statement_id, p.company_id, lock=True)
    bank = db.get(BankAccount, st.bank_account_id)
    used = set(db.scalars(select(BankStatementLine.matched_journal_line_id).where(
        BankStatementLine.matched_journal_line_id.is_not(None))))
    matched = 0
    for ln in st.lines:
        if ln.status != "unmatched":
            continue
        cands = db.execute(select(JournalLine.id, JournalEntry.entry_date).join(JournalEntry).where(
            JournalLine.company_id == p.company_id, JournalLine.account_id == bank.gl_account_id,
            JournalEntry.status.in_(("posted", "reversed")),
            (JournalLine.debit - JournalLine.credit) == ln.amount,
            JournalEntry.entry_date.between(ln.txn_date - timedelta(days=window_days),
                                            ln.txn_date + timedelta(days=window_days)))).all()
        cands = [c for c in cands if c.id not in used]
        if len(cands) == 1:  # solo coincidencias inequívocas
            ln.matched_journal_line_id, ln.status, ln.matched_by_id = cands[0].id, "matched", p.user_id
            used.add(cands[0].id)
            matched += 1
    return {"matched": matched, "unmatched": sum(1 for x in st.lines if x.status == "unmatched")}


def manual_match(db: Session, p: Principal, line_id: int, journal_line_id: int | None, ignore: bool = False) -> None:
    ln = db.get(BankStatementLine, line_id)
    st = get_owned(db, BankStatement, ln.statement_id, p.company_id) if ln else None
    if st is None:
        raise BusinessRuleViolation("Línea de extracto inexistente")
    if ignore:
        ln.status, ln.matched_journal_line_id = "ignored", None
        return
    jl = db.get(JournalLine, journal_line_id)
    bank = db.get(BankAccount, st.bank_account_id)
    if jl is None or jl.company_id != p.company_id or jl.account_id != bank.gl_account_id:
        raise BusinessRuleViolation("La línea contable no corresponde a la cuenta bancaria")
    if jl.debit - jl.credit != ln.amount:
        raise BusinessRuleViolation("Los valores no coinciden")
    ln.matched_journal_line_id, ln.status, ln.matched_by_id = jl.id, "matched", p.user_id


def reconciliation_report(db: Session, p: Principal, statement_id: int) -> dict:
    st = get_owned(db, BankStatement, statement_id, p.company_id)
    bank = db.get(BankAccount, st.bank_account_id)
    book = db.scalar(select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)).join(JournalEntry)
                     .where(JournalLine.account_id == bank.gl_account_id, JournalEntry.entry_date <= st.statement_date,
                            JournalEntry.status.in_(("posted", "reversed"))))
    matched_ids = {x.matched_journal_line_id for x in st.lines if x.matched_journal_line_id}
    all_matched = set(db.scalars(select(BankStatementLine.matched_journal_line_id).where(
        BankStatementLine.matched_journal_line_id.is_not(None))))
    outstanding = db.execute(select(JournalLine.id, JournalEntry.number, JournalEntry.entry_date,
                                    (JournalLine.debit - JournalLine.credit).label("amount"))
                             .join(JournalEntry).where(JournalLine.account_id == bank.gl_account_id,
                                                       JournalEntry.entry_date <= st.statement_date,
                                                       JournalEntry.status.in_(("posted", "reversed")))).all()
    outstanding = [dict(r._mapping) for r in outstanding if r.id not in all_matched]
    return {
        "statement_balance": st.closing_balance, "book_balance": money(book),
        "unmatched_statement_lines": [{"id": x.id, "date": x.txn_date, "description": x.description,
                                       "amount": x.amount} for x in st.lines if x.status == "unmatched"],
        "outstanding_book_items": outstanding, "matched_in_statement": len(matched_ids),
        "difference": money(Decimal(book)) - st.closing_balance,
    }


# ---------------------------------------------------------------- reportes
def _balances(db: Session, company_id: int, start: date | None, end: date) -> dict[int, tuple[Decimal, Decimal]]:
    params = {"c": company_id, "e": end, "s": start or date(1900, 1, 1)}
    rows = db.execute(text("""
        select l.account_id, sum(l.debit) d, sum(l.credit) c from journal_lines l
          join journal_entries e on e.id = l.entry_id
         where e.company_id = :c and e.status in ('posted','reversed') and e.entry_date between :s and :e
         group by l.account_id"""), params).all()
    return {r.account_id: (Decimal(r.d), Decimal(r.c)) for r in rows}


def trial_balance(db: Session, company_id: int, start: date, end: date) -> dict:
    accounts = db.scalars(select(Account).where(Account.company_id == company_id).order_by(Account.code)).all()
    before = _balances(db, company_id, None, start - timedelta(days=1))
    during = _balances(db, company_id, start, end)
    by_id = {a.id: a for a in accounts}
    agg: dict[int, list[Decimal]] = {a.id: [ZERO, ZERO, ZERO] for a in accounts}  # inicial, débitos, créditos
    for acc_id in set(before) | set(during):
        bd, bc = before.get(acc_id, (ZERO, ZERO))
        dd, dc = during.get(acc_id, (ZERO, ZERO))
        node = by_id.get(acc_id)
        while node is not None:  # acumula en la cuenta y sus mayores
            agg[node.id][0] += bd - bc
            agg[node.id][1] += dd
            agg[node.id][2] += dc
            node = by_id.get(node.parent_id) if node.parent_id else None
    rows = []
    tot_d = tot_c = ZERO
    for a in accounts:
        opening, d, c = agg[a.id]
        if opening == 0 and d == 0 and c == 0:
            continue
        rows.append({"account_id": a.id, "code": a.code, "name": a.name, "type": a.account_type,
                     "is_postable": a.is_postable, "opening": opening, "debit": d, "credit": c,
                     "closing": opening + d - c})
        if a.is_postable:
            tot_d += d
            tot_c += c
    return {"start": start, "end": end, "rows": rows, "total_debit": tot_d, "total_credit": tot_c,
            "balanced": tot_d == tot_c}


def general_ledger(db: Session, company_id: int, account_id: int, start: date, end: date) -> dict:
    acc = get_owned(db, Account, account_id, company_id)
    bd, bc = _balances(db, company_id, None, start - timedelta(days=1)).get(acc.id, (ZERO, ZERO))
    rows = db.execute(select(JournalEntry.id, JournalEntry.number, JournalEntry.entry_date, JournalEntry.source_type,
                             JournalEntry.source_id, JournalLine.description, JournalLine.debit, JournalLine.credit,
                             JournalLine.party_id)
                      .join(JournalEntry).where(JournalLine.account_id == acc.id,
                                                JournalEntry.status.in_(("posted", "reversed")),
                                                JournalEntry.entry_date.between(start, end))
                      .order_by(JournalEntry.entry_date, JournalEntry.id)).all()
    bal = bd - bc
    out = []
    for r in rows:
        bal += r.debit - r.credit
        out.append({**r._mapping, "balance": bal})
    return {"account": {"id": acc.id, "code": acc.code, "name": acc.name}, "opening": bd - bc, "lines": out,
            "closing": bal}


def journal_book(db: Session, company_id: int, start: date, end: date, journal_type: str | None = None) -> list[dict]:
    stmt = select(JournalEntry).where(JournalEntry.company_id == company_id,
                                      JournalEntry.status.in_(("posted", "reversed")),
                                      JournalEntry.entry_date.between(start, end))
    if journal_type:
        stmt = stmt.where(JournalEntry.journal_type == journal_type)
    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.company_id == company_id))}
    return [{"id": e.id, "number": e.number, "date": e.entry_date, "type": e.journal_type, "description": e.description,
             "status": e.status, "source": f"{e.source_type}:{e.source_id}" if e.source_type else None,
             "lines": [{"account": accounts[ln.account_id].code, "account_name": accounts[ln.account_id].name,
                        "debit": ln.debit, "credit": ln.credit, "description": ln.description,
                        "party_id": ln.party_id, "cost_center_id": ln.cost_center_id} for ln in e.lines]}
            for e in db.scalars(stmt.order_by(JournalEntry.entry_date, JournalEntry.id))]


def income_statement(db: Session, company_id: int, start: date, end: date, cost_center_id: int | None = None) -> dict:
    cc = "and l.cost_center_id = :cc" if cost_center_id else ""
    rows = db.execute(text(f"""
        select a.id, a.code, a.name, a.account_type acct_type, sum(l.credit - l.debit) amount
          from journal_lines l join journal_entries e on e.id = l.entry_id join accounts a on a.id = l.account_id
         where e.company_id = :c and e.status in ('posted','reversed') and e.journal_type <> 'closing'
           and e.entry_date between :s and :e and a.account_type in ('revenue','cost','expense') {cc}
         group by a.id order by a.code"""), {"c": company_id, "s": start, "e": end, "cc": cost_center_id}).all()
    sections = {"revenue": [], "cost": [], "expense": []}
    for r in rows:
        sections[r.acct_type].append({"account_id": r.id, "code": r.code, "name": r.name,
                              "amount": Decimal(r.amount) if r.acct_type == "revenue" else -Decimal(r.amount)})
    revenue = sum((x["amount"] for x in sections["revenue"]), ZERO)
    cost = sum((x["amount"] for x in sections["cost"]), ZERO)
    expense = sum((x["amount"] for x in sections["expense"]), ZERO)
    return {"start": start, "end": end, "sections": sections, "revenue": revenue, "cost_of_sales": cost,
            "gross_profit": revenue - cost, "operating_expenses": expense, "net_income": revenue - cost - expense}


def balance_sheet(db: Session, company_id: int, as_of: date) -> dict:
    rows = db.execute(text("""
        select a.id, a.code, a.name, a.account_type acct_type, sum(l.debit - l.credit) bal
          from journal_lines l join journal_entries e on e.id = l.entry_id join accounts a on a.id = l.account_id
         where e.company_id = :c and e.status in ('posted','reversed') and e.entry_date <= :d
         group by a.id order by a.code"""), {"c": company_id, "d": as_of}).all()
    out = {"asset": [], "liability": [], "equity": []}
    result = ZERO
    for r in rows:
        bal = Decimal(r.bal)
        if r.acct_type in ("revenue", "cost", "expense"):
            result -= bal  # resultado no cerrado: ingresos (crédito) suman
            continue
        out[r.acct_type].append({"account_id": r.id, "code": r.code, "name": r.name,
                         "balance": bal if r.acct_type == "asset" else -bal})
    assets = sum((x["balance"] for x in out["asset"]), ZERO)
    liabilities = sum((x["balance"] for x in out["liability"]), ZERO)
    equity = sum((x["balance"] for x in out["equity"]), ZERO) + result
    return {"as_of": as_of, "assets": out["asset"], "liabilities": out["liability"], "equity": out["equity"],
            "current_result": result, "total_assets": assets, "total_liabilities": liabilities,
            "total_equity": equity, "balanced": assets == liabilities + equity}


def cash_flow(db: Session, company_id: int, start: date, end: date) -> dict:
    """Flujo de efectivo (método directo) a partir de los movimientos de cuentas de caja y bancos."""
    cash_ids = list(db.scalars(select(Account.id).where(Account.company_id == company_id, Account.is_cash.is_(True))))
    if not cash_ids:
        return {"status": "pendiente_configuracion", "message": "No hay cuentas marcadas como caja/bancos"}
    params = {"c": company_id, "ids": cash_ids, "s": start, "e": end}
    opening = db.scalar(text("""select coalesce(sum(l.debit - l.credit), 0) from journal_lines l
        join journal_entries e on e.id = l.entry_id where e.company_id = :c and e.status in ('posted','reversed')
        and l.account_id = any(:ids) and e.entry_date < :s"""), params)
    rows = db.execute(text("""
        select coalesce(p.kind, e.source_type, 'manual') src, sum(l.debit - l.credit) amount
          from journal_lines l join journal_entries e on e.id = l.entry_id
          left join payments p on e.source_type = 'payment' and p.id = e.source_id
         where e.company_id = :c and e.status in ('posted','reversed') and l.account_id = any(:ids)
           and e.entry_date between :s and :e
         group by 1"""), params).all()
    labels = {"receipt": "Cobros a clientes", "disbursement": "Pagos a proveedores", "manual": "Otros movimientos",
              "opening_balance": "Saldos iniciales"}
    items = [{"concept": labels.get(r.src, r.src), "amount": Decimal(r.amount)} for r in rows]
    net = sum((i["amount"] for i in items), ZERO)
    return {"start": start, "end": end, "opening_cash": Decimal(opening), "operating": items, "net_change": net,
            "closing_cash": Decimal(opening) + net,
            "note": "Clasificación operativa; inversión y financiación requieren marcar cuentas (cash_flow_activity)."}


def withholding_certificate_number(db: Session, p: Principal, on: date, tax: Tax | None = None) -> str:
    """Comprobante de retención al proveedor. Retención de IVA en Venezuela: AAAAMM + secuencia de 8 dígitos
    (formato SENIAT), con secuencia propia porque se declara en el TXT y debe ser consecutiva. Las demás
    (ISLR en Venezuela; fuente, IVA e ICA en Colombia, cuyo certificado del periodo se expide aparte):
    consecutivo interno CR-000001, que no se confunde con los de IVA."""
    if p.company.country_code == "VE" and tax is not None and tax.kind == "withholding_vat":
        seq = next_number(db, p.company_id, "withholding_certificate_vat")
        return f"{on:%Y%m}{int(seq.rsplit('-', 1)[-1]):08d}"
    return next_number(db, p.company_id, "withholding_certificate")


def _check_not_withheld(db: Session, items: list, tax_ids: list[int]) -> None:
    """Evita la doble retención: una factura de proveedor que ya liquidó esa retención no la repite en el pago."""
    from app.modules.purchasing.models import SupplierInvoice, SupplierInvoiceTax

    invoice_ids = [it.document_id for it in items if it.document_type == "supplier_invoice"]
    if not invoice_ids:
        return
    dup = db.execute(select(SupplierInvoice.supplier_invoice_number, Tax.code)
                     .join(SupplierInvoiceTax, SupplierInvoiceTax.invoice_id == SupplierInvoice.id)
                     .join(Tax, Tax.id == SupplierInvoiceTax.tax_id)
                     .where(SupplierInvoice.id.in_(invoice_ids), SupplierInvoiceTax.is_withholding.is_(True),
                            SupplierInvoiceTax.tax_id.in_(tax_ids))).first()
    if dup:
        raise BusinessRuleViolation(f"La factura {dup[0]} ya tiene la retención {dup[1]}; no se retiene dos veces")


def withholding_suggestions(db: Session, p: Principal, open_item_id: int, applied: Decimal) -> dict:
    """Retenciones que corresponde practicar al pagar una partida por pagar, proporcionales al valor aplicado.

    Usa las retenciones configuradas en el proveedor, las bases mínimas y, si la partida es una factura de
    proveedor, sus líneas con IVA (para la retención de IVA). Omite las que la factura ya liquidó."""
    from app.modules.masters.service import compute_taxes, party_withholdings
    from app.modules.purchasing.models import SupplierInvoice, SupplierInvoiceTax

    item = db.get(OpenItem, open_item_id)
    if item is None or item.company_id != p.company_id or item.kind != "payable":
        raise BusinessRuleViolation("La partida no es una cuenta por pagar de la empresa")
    party = db.get(Party, item.party_id)
    taxes = party_withholdings(db, party, p.company.is_withholding_agent, "purchases")
    ratio = min(Decimal(applied) / item.original_amount, Decimal("1")) if item.original_amount else Decimal("1")
    already: set[int] = set()
    if item.document_type == "supplier_invoice":
        inv = db.get(SupplierInvoice, item.document_id)
        already = set(db.scalars(select(SupplierInvoiceTax.tax_id).where(
            SupplierInvoiceTax.invoice_id == inv.id, SupplierInvoiceTax.is_withholding.is_(True))))
        lines = [(ln.line_subtotal * ratio, db.get(Tax, ln.tax_id) if ln.tax_id else None) for ln in inv.lines]
    else:
        lines = [(Decimal(applied), None)]
    res = compute_taxes(lines, [t for t in taxes if t.id not in already], "purchases")
    return {"agent": p.company.is_withholding_agent, "already_withheld": sorted(already),
            "suggestions": [{"tax_id": w.tax.id, "code": w.tax.code, "name": w.tax.name, "rate": w.tax.rate,
                             "base": w.base, "amount": w.amount} for w in res.withholdings]}

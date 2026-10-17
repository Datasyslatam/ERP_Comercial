"""Motor de contabilización por partida doble.

Reglas aplicadas:
- todo asiento contabilizado debe estar balanceado (servicio + trigger diferido en BD);
- un asiento contabilizado no se modifica ni borra (trigger); se corrige con reverso;
- no se contabiliza en periodos cerrados;
- clave de idempotencia por empresa: repetir una contabilización devuelve el asiento existente.
"""
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.errors import BusinessRuleViolation, Conflict, NotFound
from app.core.money import ZERO, money
from app.core.numbering import next_number
from app.modules.accounting.models import Account, FiscalPeriod, JournalEntry, JournalLine, PostingAccount
from app.modules.org.models import Company


@dataclass
class LineSpec:
    account_id: int
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    description: str | None = None
    party_id: int | None = None
    cost_center_id: int | None = None
    currency: str | None = None
    amount_currency: Decimal | None = None
    exchange_rate: Decimal | None = None


def posting_account(db: Session, company_id: int, key: str) -> int:
    pa = db.scalar(select(PostingAccount).where(PostingAccount.company_id == company_id, PostingAccount.key == key))
    if pa is None:
        raise BusinessRuleViolation(
            f"Falta parametrizar la cuenta contable '{key}' para la empresa", details={"posting_key": key}
        )
    return pa.account_id


def get_open_period(db: Session, company_id: int, on: date, *, lock: bool = False) -> FiscalPeriod:
    stmt = select(FiscalPeriod).where(
        FiscalPeriod.company_id == company_id, FiscalPeriod.year == on.year, FiscalPeriod.month == on.month
    )
    if lock:
        stmt = stmt.with_for_update(read=True)
    period = db.scalar(stmt)
    if period is None:
        raise BusinessRuleViolation(f"No existe periodo contable para {on:%Y-%m}")
    if period.status != "open":
        raise BusinessRuleViolation(f"El periodo {on:%Y-%m} está cerrado; no admite contabilizaciones")
    return period


def _normalize(lines: list[LineSpec]) -> list[LineSpec]:
    out = []
    for ln in lines:
        d, c = money(ln.debit), money(ln.credit)
        if d < 0 or c < 0:
            raise BusinessRuleViolation("Los valores débito/crédito no pueden ser negativos")
        net = d - c
        if net == 0:
            continue  # se omiten líneas en cero (p. ej. impuestos exentos)
        ln.debit, ln.credit = (net, ZERO) if net > 0 else (ZERO, -net)
        out.append(ln)
    return out


def post_entry(
    db: Session,
    *,
    company_id: int,
    entry_date: date,
    journal_type: str,
    description: str,
    lines: list[LineSpec],
    idempotency_key: str,
    source_type: str | None = None,
    source_id: int | None = None,
    user_id: int | None = None,
    reversal_of_id: int | None = None,
    created_by_id: int | None = None,
) -> JournalEntry:
    existing = db.scalar(
        select(JournalEntry).where(JournalEntry.company_id == company_id,
                                   JournalEntry.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return existing

    period = get_open_period(db, company_id, entry_date, lock=True)
    lines = _normalize(lines)
    if len(lines) < 2:
        raise BusinessRuleViolation("Un asiento requiere al menos dos líneas con valor")
    total_d = sum((ln.debit for ln in lines), ZERO)
    total_c = sum((ln.credit for ln in lines), ZERO)
    if total_d != total_c:
        raise BusinessRuleViolation(
            "El asiento no está balanceado", details={"debit": str(total_d), "credit": str(total_c)}
        )

    accounts = {a.id: a for a in db.scalars(select(Account).where(Account.id.in_({ln.account_id for ln in lines})))}
    for ln in lines:
        acc = accounts.get(ln.account_id)
        if acc is None or acc.company_id != company_id:
            raise BusinessRuleViolation(f"Cuenta {ln.account_id} inexistente para la empresa")
        if not acc.is_postable or not acc.is_active:
            raise BusinessRuleViolation(f"La cuenta {acc.code} no es de movimiento o está inactiva")
        if acc.requires_party and ln.party_id is None:
            raise BusinessRuleViolation(f"La cuenta {acc.code} exige tercero")
        if acc.requires_cost_center and ln.cost_center_id is None:
            raise BusinessRuleViolation(f"La cuenta {acc.code} exige centro de costo")

    entry = JournalEntry(
        company_id=company_id, number=next_number(db, company_id, "journal_entry"), entry_date=entry_date,
        period_id=period.id, journal_type=journal_type, description=description[:500], status="posted",
        source_type=source_type, source_id=source_id, idempotency_key=idempotency_key,
        created_by_id=created_by_id or user_id,
        posted_by_id=user_id, posted_at=datetime.now(UTC), total_debit=total_d, total_credit=total_c,
        reversal_of_id=reversal_of_id,
    )
    for i, ln in enumerate(lines, start=1):
        entry.lines.append(JournalLine(
            company_id=company_id, line_no=i, account_id=ln.account_id, debit=ln.debit, credit=ln.credit,
            description=(ln.description or description)[:255], party_id=ln.party_id, cost_center_id=ln.cost_center_id,
            currency=ln.currency, amount_currency=ln.amount_currency, exchange_rate=ln.exchange_rate,
        ))
    db.add(entry)
    db.flush()
    log_action(db, "post", "journal_entries", entry.id, f"Asiento {entry.number}: {description[:200]}")
    return entry


def reverse_entry(db: Session, *, company_id: int, entry_id: int, reversal_date: date, reason: str,
                  user_id: int | None) -> JournalEntry:
    entry = db.get(JournalEntry, entry_id)
    if entry is None or entry.company_id != company_id:
        raise NotFound("Asiento no encontrado")
    if entry.status == "reversed":
        raise Conflict("El asiento ya fue reversado")
    if entry.status != "posted":
        raise BusinessRuleViolation("Solo se reversan asientos contabilizados")
    lines = [
        LineSpec(account_id=ln.account_id, debit=ln.credit, credit=ln.debit, description=f"Reverso: {ln.description}",
                 party_id=ln.party_id, cost_center_id=ln.cost_center_id, currency=ln.currency,
                 amount_currency=-ln.amount_currency if ln.amount_currency is not None else None,
                 exchange_rate=ln.exchange_rate)
        for ln in entry.lines
    ]
    rev = post_entry(
        db, company_id=company_id, entry_date=reversal_date, journal_type=entry.journal_type,
        description=f"Reverso de {entry.number}: {reason}", lines=lines, idempotency_key=f"reversal:{entry.id}",
        source_type=entry.source_type, source_id=entry.source_id, user_id=user_id, reversal_of_id=entry.id,
    )
    # La única modificación permitida sobre un asiento contabilizado es marcarlo como reversado (ver trigger).
    entry.status = "reversed"
    db.flush()
    log_action(db, "void", "journal_entries", entry.id, f"Reversado por {rev.number}: {reason}")
    return rev


def functional_currency(db: Session, company_id: int) -> str:
    return db.get(Company, company_id).functional_currency

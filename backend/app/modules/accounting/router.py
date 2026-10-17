import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import crud_router, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require
from app.core.schemas import CurrencyField, ReasonIn
from app.core.serialize import paginate, to_dict
from app.modules.accounting import service as svc
from app.modules.accounting.models import (
    BankStatement,
    BudgetLine,
    FiscalPeriod,
    JournalEntry,
    OpenItem,
    Payment,
    StrategicGoal,
)

router = APIRouter(prefix="/accounting", tags=["Contabilidad y finanzas"])
router.include_router(crud_router(BudgetLine, prefix="/budgets", tag="Presupuestos", read_perm="accounting.budget.read",
                                  write_perm="accounting.budget.create", export_perm="accounting.reports.export",
                                  search_fields=("category",)))
router.include_router(crud_router(StrategicGoal, prefix="/goals", tag="Metas estratégicas",
                                  read_perm="kpi.dashboard.read", write_perm="kpi.config.admin"))


class LineIn(BaseModel):
    account_id: int
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = Field(default=None, max_length=255)
    party_id: int | None = None
    cost_center_id: int | None = None


class EntryIn(BaseModel):
    entry_date: date
    journal_type: str = Field(default="general", pattern="^(general|adjustment)$")
    description: str = Field(min_length=5, max_length=500)
    lines: list[LineIn] = Field(min_length=2)

    @model_validator(mode="after")
    def _balanced(self):
        if sum(x.debit for x in self.lines) != sum(x.credit for x in self.lines):
            raise ValueError("El comprobante no está balanceado")
        return self


class ReverseIn(BaseModel):
    reversal_date: date
    reason: str = Field(min_length=5, max_length=500)


class PeriodIn(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class ReopenIn(PeriodIn):
    reason: str = Field(min_length=10, max_length=1000)


class AllocationIn(BaseModel):
    open_item_id: int
    amount: Decimal = Field(gt=0)


class WithholdingIn(BaseModel):
    tax_id: int
    base: Decimal = Field(default=Decimal("0"), ge=0)
    amount: Decimal = Field(gt=0)


class PaymentIn(BaseModel):
    kind: str = Field(pattern="^(receipt|disbursement)$")
    party_id: int
    payment_date: date
    bank_account_id: int
    method: str = Field(pattern="^(transfer|cash|check|card|mobile_payment|other)$")
    currency: str = CurrencyField()
    exchange_rate: Decimal | None = Field(default=None, gt=0)
    amount: Decimal = Field(gt=0)
    reference: str | None = Field(default=None, max_length=80)
    idempotency_key: str = Field(min_length=8, max_length=160)
    allocations: list[AllocationIn] = Field(min_length=1)
    withholdings: list[WithholdingIn] = []


class StatementLineIn(BaseModel):
    txn_date: date
    description: str = Field(max_length=255)
    reference: str | None = Field(default=None, max_length=80)
    amount: Decimal


class StatementIn(BaseModel):
    bank_account_id: int
    statement_date: date
    opening_balance: Decimal
    closing_balance: Decimal
    source_filename: str | None = None
    lines: list[StatementLineIn] = Field(min_length=1)


class MatchIn(BaseModel):
    journal_line_id: int | None = None
    ignore: bool = False


# ------------------------------------------------------------------ comprobantes
@router.get("/entries")
def list_entries(start: date | None = None, end: date | None = None, status: str | None = None,
                 source_type: str | None = None, source_id: int | None = None, limit: int = Query(50, le=500),
                 offset: int = 0, p: Principal = Depends(require("accounting.journal.read")),
                 db: Session = Depends(get_db)):
    stmt = select(JournalEntry).where(JournalEntry.company_id == p.company_id)
    for col, val in ((JournalEntry.status, status), (JournalEntry.source_type, source_type),
                     (JournalEntry.source_id, source_id)):
        if val is not None:
            stmt = stmt.where(col == val)
    if start:
        stmt = stmt.where(JournalEntry.entry_date >= start)
    if end:
        stmt = stmt.where(JournalEntry.entry_date <= end)
    return paginate(db, stmt.order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc()), limit, offset, "lines")


@router.get("/entries/{entry_id}")
def get_entry(entry_id: int, p: Principal = Depends(require("accounting.journal.read")), db: Session = Depends(get_db)):
    return to_dict(get_owned(db, JournalEntry, entry_id, p.company_id), "lines")


@router.post("/entries", status_code=201)
def create_entry(body: EntryIn, p: Principal = Depends(require("accounting.journal.create")),
                 db: Session = Depends(get_db)):
    e = svc.create_manual_entry(db, p, body.model_dump())
    db.commit()
    return to_dict(e, "lines")


@router.post("/entries/{entry_id}/post")
def post_entry(entry_id: int, p: Principal = Depends(require("accounting.journal.post")),
               db: Session = Depends(get_db)):
    e = svc.post_manual_entry(db, p, entry_id)
    db.commit()
    return to_dict(e, "lines")


@router.delete("/entries/{entry_id}", status_code=204)
def delete_draft(entry_id: int, p: Principal = Depends(require("accounting.journal.create")),
                 db: Session = Depends(get_db)):
    svc.delete_draft(db, p, entry_id)
    db.commit()


@router.post("/entries/{entry_id}/reverse")
def reverse(entry_id: int, body: ReverseIn, p: Principal = Depends(require("accounting.journal.void")),
            db: Session = Depends(get_db)):
    e = svc.reverse(db, p, entry_id, body.reversal_date, body.reason)
    db.commit()
    return to_dict(e, "lines")


# ------------------------------------------------------------------ periodos
@router.get("/periods")
def periods(year: int | None = None, p: Principal = Depends(require("accounting.period.read")),
            db: Session = Depends(get_db)):
    stmt = select(FiscalPeriod).where(FiscalPeriod.company_id == p.company_id)
    if year:
        stmt = stmt.where(FiscalPeriod.year == year)
    return [to_dict(x) for x in db.scalars(stmt.order_by(FiscalPeriod.year, FiscalPeriod.month))]


@router.post("/periods/open-year")
def open_year(body: PeriodIn, p: Principal = Depends(require("accounting.period.admin")), db: Session = Depends(get_db)):
    from app.modules.org.service import ensure_periods

    ensure_periods(db, p.company_id, body.year)
    db.commit()
    return {"year": body.year}


@router.post("/periods/close")
def close_period(body: PeriodIn, p: Principal = Depends(require("accounting.period.admin")),
                 db: Session = Depends(get_db)):
    per = svc.close_period(db, p, body.year, body.month)
    db.commit()
    return to_dict(per)


@router.post("/periods/reopen")
def reopen_period(body: ReopenIn, p: Principal = Depends(require("accounting.period.admin")),
                  db: Session = Depends(get_db)):
    per = svc.reopen_period(db, p, body.year, body.month, body.reason)
    db.commit()
    return to_dict(per)


@router.post("/year-close")
def year_close(body: PeriodIn, p: Principal = Depends(require("accounting.period.admin")),
               db: Session = Depends(get_db)):
    e = svc.close_year(db, p, body.year)
    db.commit()
    return to_dict(e, "lines")


# ------------------------------------------------------------------ cartera y tesorería
@router.get("/open-items")
def open_items(kind: str = Query(pattern="^(receivable|payable)$"), party_id: int | None = None,
               only_open: bool = True, limit: int = Query(100, le=1000), offset: int = 0,
               p: Principal = Depends(require("accounting.payments.read")), db: Session = Depends(get_db)):
    stmt = select(OpenItem).where(OpenItem.company_id == p.company_id, OpenItem.kind == kind)
    if party_id:
        stmt = stmt.where(OpenItem.party_id == party_id)
    if only_open:
        stmt = stmt.where(OpenItem.status.in_(("open", "partial")))
    return paginate(db, stmt.order_by(OpenItem.due_date), limit, offset)


@router.get("/aging")
def aging(kind: str = Query(pattern="^(receivable|payable)$"), as_of: date | None = None,
          p: Principal = Depends(require("accounting.reports.read")), db: Session = Depends(get_db)):
    return svc.aging(db, p.company_id, kind, as_of or date.today())


@router.get("/payments")
def list_payments(kind: str | None = None, party_id: int | None = None, limit: int = Query(50, le=500),
                  offset: int = 0, p: Principal = Depends(require("accounting.payments.read")),
                  db: Session = Depends(get_db)):
    stmt = select(Payment).where(Payment.company_id == p.company_id)
    if kind:
        stmt = stmt.where(Payment.kind == kind)
    if party_id:
        stmt = stmt.where(Payment.party_id == party_id)
    return paginate(db, stmt.order_by(Payment.id.desc()), limit, offset, "allocations", "withholdings")


@router.post("/payments", status_code=201)
def register_payment(body: PaymentIn, p: Principal = Depends(require("accounting.payments.create")),
                     db: Session = Depends(get_db)):
    pay = svc.register_payment(db, p, body.model_dump())
    db.commit()
    return to_dict(pay, "allocations", "withholdings")


@router.post("/payments/{payment_id}/void")
def void_payment(payment_id: int, body: ReasonIn, p: Principal = Depends(require("accounting.payments.void")),
                 db: Session = Depends(get_db)):
    pay = svc.void_payment(db, p, payment_id, body.reason)
    db.commit()
    return to_dict(pay, "allocations")


# ------------------------------------------------------------------ conciliación bancaria
@router.post("/bank-statements", status_code=201)
def import_statement(body: StatementIn, p: Principal = Depends(require("accounting.bank.create")),
                     db: Session = Depends(get_db)):
    st = svc.import_statement(db, p, body.model_dump())
    db.commit()
    return to_dict(st, "lines")


@router.get("/bank-statements")
def list_statements(bank_account_id: int | None = None, p: Principal = Depends(require("accounting.bank.read")),
                    db: Session = Depends(get_db)):
    stmt = select(BankStatement).where(BankStatement.company_id == p.company_id)
    if bank_account_id:
        stmt = stmt.where(BankStatement.bank_account_id == bank_account_id)
    return [to_dict(s) for s in db.scalars(stmt.order_by(BankStatement.statement_date.desc()))]


@router.post("/bank-statements/{statement_id}/auto-match")
def auto_match(statement_id: int, p: Principal = Depends(require("accounting.bank.approve")),
               db: Session = Depends(get_db)):
    r = svc.auto_match(db, p, statement_id)
    db.commit()
    return r


@router.post("/bank-statement-lines/{line_id}/match")
def manual_match(line_id: int, body: MatchIn, p: Principal = Depends(require("accounting.bank.approve")),
                 db: Session = Depends(get_db)):
    svc.manual_match(db, p, line_id, body.journal_line_id, body.ignore)
    db.commit()
    return {"ok": True}


@router.get("/bank-statements/{statement_id}/reconciliation")
def reconciliation(statement_id: int, p: Principal = Depends(require("accounting.bank.read")),
                   db: Session = Depends(get_db)):
    return svc.reconciliation_report(db, p, statement_id)


# ------------------------------------------------------------------ reportes
@router.get("/reports/trial-balance")
def trial_balance(start: date, end: date, p: Principal = Depends(require("accounting.reports.read")),
                  db: Session = Depends(get_db)):
    return svc.trial_balance(db, p.company_id, start, end)


@router.get("/reports/general-ledger/{account_id}")
def general_ledger(account_id: int, start: date, end: date, p: Principal = Depends(require("accounting.reports.read")),
                   db: Session = Depends(get_db)):
    return svc.general_ledger(db, p.company_id, account_id, start, end)


@router.get("/reports/journal")
def journal(start: date, end: date, journal_type: str | None = None,
            p: Principal = Depends(require("accounting.reports.read")), db: Session = Depends(get_db)):
    return svc.journal_book(db, p.company_id, start, end, journal_type)


@router.get("/reports/income-statement")
def income_statement(start: date, end: date, cost_center_id: int | None = None,
                     p: Principal = Depends(require("accounting.reports.read")), db: Session = Depends(get_db)):
    return svc.income_statement(db, p.company_id, start, end, cost_center_id)


@router.get("/reports/balance-sheet")
def balance_sheet(as_of: date, p: Principal = Depends(require("accounting.reports.read")),
                  db: Session = Depends(get_db)):
    return svc.balance_sheet(db, p.company_id, as_of)


@router.get("/reports/cash-flow")
def cash_flow(start: date, end: date, p: Principal = Depends(require("accounting.reports.read")),
              db: Session = Depends(get_db)):
    return svc.cash_flow(db, p.company_id, start, end)


@router.get("/reports/trial-balance.csv")
def trial_balance_csv(start: date, end: date, p: Principal = Depends(require("accounting.reports.export")),
                      db: Session = Depends(get_db)):
    tb = svc.trial_balance(db, p.company_id, start, end)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["cuenta", "nombre", "saldo_inicial", "debitos", "creditos", "saldo_final"])
    for r in tb["rows"]:
        w.writerow([r["code"], r["name"], r["opening"], r["debit"], r["credit"], r["closing"]])
    log_action(db, "export", "trial_balance", None, f"{start}..{end}")
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="balance_prueba_{start}_{end}.csv"'})

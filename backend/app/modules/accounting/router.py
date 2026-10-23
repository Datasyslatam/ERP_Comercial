import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import crud_router, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require
from app.core.schemas import CurrencyField, ReasonIn
from app.core.serialize import paginate, to_dict
from app.modules.accounting import receivables as cartera
from app.modules.accounting import service as svc
from app.modules.accounting.models import (
    AdvanceApplication,
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
    # Recaudos: número del comprobante de retención que entrega el cliente
    certificate_number: str | None = Field(default=None, max_length=30)


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
    # Sin facturas (o por menos del pago): el excedente queda como anticipo del tercero
    allocations: list[AllocationIn] = Field(default_factory=list, max_length=200)
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
def aging(kind: str = Query(pattern="^(receivable|payable)$"), as_of: date | None = None, party_id: int | None = None,
          p: Principal = Depends(require("accounting.reports.read")), db: Session = Depends(get_db)):
    return svc.aging(db, p.company_id, kind, as_of or date.today(), party_id)


@router.get("/aging/by-party")
def aging_by_party(kind: str = Query(pattern="^(receivable|payable)$"), as_of: date | None = None,
                   p: Principal = Depends(require("accounting.reports.read")), db: Session = Depends(get_db)):
    """Cartera por tercero: saldo por rango de vencimiento, anticipos y total neto."""
    return cartera.aging_by_party(db, p.company, kind, as_of or date.today())


@router.get("/aging.xlsx")
def aging_xlsx(kind: str = Query(pattern="^(receivable|payable)$"), as_of: date | None = None,
               p: Principal = Depends(require("accounting.reports.export")), db: Session = Depends(get_db)):
    from app.modules.accounting.fiscal import xlsx

    as_of = as_of or date.today()
    by_party = cartera.aging_by_party(db, p.company, kind, as_of)
    detail = svc.aging(db, p.company_id, kind, as_of)
    labels = detail["labels"]
    party_cols = [("tax_id", "Identificación"), ("party", "Tercero"), ("documents", "Documentos")] + \
        [(b, labels[b]) for b in cartera.BUCKETS] + [("advances", labels["advances"]), ("total", "Saldo neto")]
    totals = {k: sum((r[k] for r in by_party), svc.ZERO) for k, _ in party_cols[3:]}
    doc_cols = [("party", "Tercero"), ("document", "Documento"), ("due_date", "Vence"), ("days_overdue", "Días vencido"),
                ("currency", "Moneda"), ("open_amount", "Saldo (moneda del documento)"),
                ("open_amount_functional", f"Saldo ({p.company.functional_currency})")]
    title = "Cuentas por cobrar por edades" if kind == "receivable" else "Cuentas por pagar por edades"
    data = xlsx(title, p.company.legal_name, p.company.tax_id, f"Corte al {as_of:%d/%m/%Y}", [
        ("Por tercero", party_cols, by_party, totals),
        ("Por documento", doc_cols, detail["items"], {"open_amount_functional": detail["total"]})])
    log_action(db, "export", "aging", None, f"{title} al {as_of}")
    db.commit()
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="cartera_{kind}_{as_of:%Y%m%d}.xlsx"'})


@router.get("/reconciliation")
def subledger_reconciliation(kind: str = Query(pattern="^(receivable|payable)$"),
                             p: Principal = Depends(require("accounting.reports.read")), db: Session = Depends(get_db)):
    """Conciliación del auxiliar de cartera (partidas abiertas) contra las cuentas de control del mayor."""
    return cartera.reconciliation(db, p.company, kind)


@router.get("/party-statement")
def party_statement(party_id: int, start: date, end: date, kind: str = Query(pattern="^(receivable|payable)$"),
                    p: Principal = Depends(require("accounting.payments.read")), db: Session = Depends(get_db)):
    """Estado de cuenta del tercero: saldo inicial, movimientos con saldo corrido y documentos pendientes."""
    return cartera.party_statement(db, p.company, party_id, kind, start, end)


@router.get("/party-statement/pdf")
def party_statement_pdf(party_id: int, start: date, end: date, kind: str = Query(pattern="^(receivable|payable)$"),
                        p: Principal = Depends(require("accounting.payments.read")), db: Session = Depends(get_db)):
    filename, data = cartera.statement_pdf(db, p.company, party_id, kind, start, end)
    log_action(db, "export", "party_statement", party_id, f"Estado de cuenta {start}..{end}")
    db.commit()
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/party-statement/email-defaults")
def party_statement_email_defaults(party_id: int, start: date, end: date,
                                   kind: str = Query(pattern="^(receivable|payable)$"),
                                   p: Principal = Depends(require("accounting.payments.read")),
                                   db: Session = Depends(get_db)):
    return cartera.statement_message(db, p.company, party_id, kind, end)


class StatementEmailIn(BaseModel):
    party_id: int
    kind: str = Field(pattern="^(receivable|payable)$")
    start: date
    end: date
    to: list[str] = Field(min_length=1, max_length=10)
    cc: list[str] = Field(default_factory=list, max_length=10)
    subject: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=5000)


@router.post("/party-statement/email", status_code=202)
def party_statement_email(body: StatementEmailIn, p: Principal = Depends(require("accounting.payments.create")),
                          db: Session = Depends(get_db)):
    """Envía el estado de cuenta en PDF por correo (cola con reintentos; el PDF se genera al enviar)."""
    em = cartera.queue_statement_email(db, p, **body.model_dump())
    db.commit()
    return to_dict(em)


class ApplyAdvanceIn(BaseModel):
    application_date: date | None = None
    allocations: list[AllocationIn] = Field(min_length=1, max_length=200)


@router.post("/advances/{item_id}/apply", status_code=201)
def apply_advance(item_id: int, body: ApplyAdvanceIn, p: Principal = Depends(require("accounting.payments.create")),
                  db: Session = Depends(get_db)):
    """Cruza un anticipo (saldo a favor del tercero) contra sus facturas abiertas."""
    apps = svc.apply_advance(db, p, item_id, body.model_dump())
    db.commit()
    return [to_dict(a) for a in apps]


@router.get("/advance-applications")
def list_advance_applications(party_id: int | None = None, limit: int = Query(50, le=500), offset: int = 0,
                              p: Principal = Depends(require("accounting.payments.read")),
                              db: Session = Depends(get_db)):
    stmt = select(AdvanceApplication).where(AdvanceApplication.company_id == p.company_id)
    if party_id:
        stmt = stmt.join(OpenItem, OpenItem.id == AdvanceApplication.advance_item_id).where(OpenItem.party_id == party_id)
    return paginate(db, stmt.order_by(AdvanceApplication.id.desc()), limit, offset)


@router.post("/advance-applications/{app_id}/void")
def void_advance_application(app_id: int, body: ReasonIn, p: Principal = Depends(require("accounting.payments.void")),
                             db: Session = Depends(get_db)):
    apps = svc.void_advance_application(db, p, app_id, body.reason)
    db.commit()
    return [to_dict(a) for a in apps]


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


@router.get("/payments/withholding-suggestions")
def withholding_suggestions(open_item_id: int, applied: Decimal = Query(gt=0),
                            p: Principal = Depends(require("accounting.payments.create")), db: Session = Depends(get_db)):
    """Retenciones sugeridas al pagar una cuenta por pagar (configuración del proveedor y bases mínimas)."""
    return svc.withholding_suggestions(db, p, open_item_id, applied)


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


@router.post("/bank-statements/parse")
async def parse_statement_file(file: UploadFile = File(...), p: Principal = Depends(require("accounting.bank.create"))):
    """Lee un extracto (CSV, Excel .xlsx u OFX) y devuelve los movimientos y saldos para revisar antes de cargarlo."""
    from app.modules.accounting.statements import parse_statement

    return parse_statement(file.filename or "", await file.read())


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

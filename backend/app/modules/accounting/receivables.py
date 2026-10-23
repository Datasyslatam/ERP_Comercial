"""Cartera (CxC y CxP): conciliación del auxiliar contra el mayor, estado de cuenta por tercero y cartera por
tercero. El auxiliar son las partidas abiertas (open_items); el mayor, las cuentas de control con el tercero."""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolation, NotFound
from app.core.money import ZERO, money
from app.modules.accounting.ledger import posting_account
from app.modules.accounting.models import ADVANCE_TYPES, Account, JournalEntry, JournalLine, OpenItem
from app.modules.masters.models import Party
from app.modules.org.models import Company

KINDS = {"receivable": ("accounts_receivable", "customer_advances"),
         "payable": ("accounts_payable", "supplier_advances")}
BUCKETS = ("current", "1_30", "31_60", "61_90", "over_90")
BUCKET_LABELS = {"current": "Por vencer", "1_30": "1 a 30 días", "31_60": "31 a 60 días", "61_90": "61 a 90 días",
                 "over_90": "Más de 90 días"}
SOURCE_LABELS = {"sales_invoice": "Factura / nota", "supplier_invoice": "Factura de proveedor", "payment": "Pago",
                 "opening_balance": "Saldo inicial", "advance_application": "Cruce de anticipo",
                 "manual": "Comprobante manual"}


def _check(kind: str) -> tuple[str, str]:
    if kind not in KINDS:
        raise BusinessRuleViolation("Tipo de cartera inválido (receivable o payable)")
    return KINDS[kind]


def _sign(kind: str) -> int:
    """Signo para leer el mayor como saldo del tercero: positivo = nos debe (CxC) o le debemos (CxP)."""
    return 1 if kind == "receivable" else -1


def _gl_by_party(db: Session, company_id: int, account_id: int, until: date | None = None, start: date | None = None,
                 party_id: int | None = None) -> dict[int | None, object]:
    q = (select(JournalLine.party_id, func.sum(JournalLine.debit - JournalLine.credit))
         .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
         .where(JournalLine.company_id == company_id, JournalLine.account_id == account_id,
                JournalEntry.status.in_(("posted", "reversed"))).group_by(JournalLine.party_id))
    if until:
        q = q.where(JournalEntry.entry_date <= until)
    if start:
        q = q.where(JournalEntry.entry_date >= start)
    if party_id:
        q = q.where(JournalLine.party_id == party_id)
    return {pid: money(v or 0) for pid, v in db.execute(q).all()}


def _open_items(db: Session, company_id: int, kind: str, party_id: int | None = None) -> list[OpenItem]:
    q = select(OpenItem).where(OpenItem.company_id == company_id, OpenItem.kind == kind,
                               OpenItem.status.in_(("open", "partial")))
    if party_id:
        q = q.where(OpenItem.party_id == party_id)
    return list(db.scalars(q.order_by(OpenItem.due_date, OpenItem.id)))


def functional(oi: OpenItem) -> object:
    """Saldo en moneda funcional con signo: los anticipos son saldo a favor del tercero (negativos)."""
    value = money(oi.open_amount * oi.exchange_rate)
    return -value if oi.document_type in ADVANCE_TYPES else value


# ---------------------------------------------------------------- conciliación auxiliar vs mayor
def reconciliation(db: Session, company: Company, kind: str) -> dict:
    """Compara, a hoy, las partidas abiertas (auxiliar) con el saldo de las cuentas de control (mayor), en total y
    por tercero. Una diferencia indica asientos manuales a la cuenta de control, partidas sin contabilizar o
    diferencias de cambio por documentos en divisas."""
    main_key, adv_key = _check(kind)
    sign = _sign(kind)
    items = _open_items(db, company.id, kind)
    sub_main, sub_adv = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    for oi in items:
        value = money(oi.open_amount * oi.exchange_rate)
        (sub_adv if oi.document_type in ADVANCE_TYPES else sub_main)[oi.party_id] += value
    accounts, by_party = [], defaultdict(lambda: {"gl": ZERO, "subledger": ZERO})
    for key, sub, label in ((main_key, sub_main, "Cartera" if kind == "receivable" else "Proveedores"),
                            (adv_key, sub_adv, "Anticipos")):
        acc_id = posting_account(db, company.id, key)
        acc = db.get(Account, acc_id)
        # Anticipos: el saldo a favor del tercero tiene la naturaleza contraria a la cartera
        gl_sign = sign if key == main_key else -sign
        gl = {pid: gl_sign * v for pid, v in _gl_by_party(db, company.id, acc_id).items()}
        gl_total, sub_total = sum(gl.values(), ZERO), sum(sub.values(), ZERO)
        accounts.append({"key": key, "label": label, "account_code": acc.code, "account_name": acc.name,
                         "gl": gl_total, "subledger": sub_total, "difference": gl_total - sub_total,
                         "without_party": gl.get(None, ZERO)})
        net = 1 if key == main_key else -1  # por tercero: cartera menos anticipos
        for pid in set(gl) | set(sub):
            if pid is None:
                continue
            by_party[pid]["gl"] += net * gl.get(pid, ZERO)
            by_party[pid]["subledger"] += net * sub.get(pid, ZERO)
    parties = {p.id: p for p in db.scalars(select(Party).where(Party.id.in_(by_party.keys())))} if by_party else {}
    rows = []
    for pid, v in by_party.items():
        diff = v["gl"] - v["subledger"]
        if v["gl"] or v["subledger"]:
            rows.append({"party_id": pid, "party": parties[pid].legal_name, "tax_id": parties[pid].tax_id,
                         "gl": v["gl"], "subledger": v["subledger"], "difference": diff})
    rows.sort(key=lambda r: (-abs(r["difference"]), r["party"]))
    diff_total = sum((a["difference"] for a in accounts), ZERO)
    return {"kind": kind, "as_of": date.today(), "currency": company.functional_currency, "accounts": accounts,
            "parties": rows, "difference": diff_total, "balanced": diff_total == 0 and all(
                r["difference"] == 0 for r in rows),
            "parties_with_difference": sum(1 for r in rows if r["difference"] != 0)}


# ---------------------------------------------------------------- cartera por tercero
def aging_by_party(db: Session, company: Company, kind: str, as_of: date) -> list[dict]:
    _check(kind)
    acc: dict[int, dict] = {}
    for oi in _open_items(db, company.id, kind):
        row = acc.setdefault(oi.party_id, {"party_id": oi.party_id, **{b: ZERO for b in BUCKETS}, "advances": ZERO,
                                           "total": ZERO, "documents": 0, "max_days_overdue": 0})
        value = functional(oi)
        if oi.document_type in ADVANCE_TYPES:
            row["advances"] += value
        else:
            days = (as_of - oi.due_date).days
            b = "current" if days <= 0 else "1_30" if days <= 30 else "31_60" if days <= 60 else "61_90" \
                if days <= 90 else "over_90"
            row[b] += value
            row["documents"] += 1
            row["max_days_overdue"] = max(row["max_days_overdue"], days)
        row["total"] += value
    parties = {p.id: p for p in db.scalars(select(Party).where(Party.id.in_(acc.keys())))} if acc else {}
    for pid, row in acc.items():
        p = parties[pid]
        row.update({"party": p.legal_name, "tax_id": p.tax_id, "email": p.email,
                    "credit_limit": p.credit_limit if kind == "receivable" else None})
    return sorted(acc.values(), key=lambda r: -r["total"])


# ---------------------------------------------------------------- estado de cuenta
def party_statement(db: Session, company: Company, party_id: int, kind: str, start: date, end: date) -> dict:
    """Movimientos del tercero en las cuentas de control (cartera y anticipos) con saldo inicial, saldo corrido y
    los documentos pendientes. Positivo: el tercero nos debe (CxC) o le debemos (CxP)."""
    main_key, adv_key = _check(kind)
    if end < start:
        raise BusinessRuleViolation("La fecha final no puede ser anterior a la inicial")
    party = db.get(Party, party_id)
    if party is None or party.company_id != company.id:
        raise NotFound("Tercero no encontrado")
    sign = _sign(kind)
    acc_ids = [posting_account(db, company.id, k) for k in (main_key, adv_key)]
    opening = ZERO
    for acc_id in acc_ids:
        before = _gl_by_party(db, company.id, acc_id, until=start - timedelta(days=1), party_id=party_id)
        opening += sign * before.get(party_id, ZERO)
    q = (select(JournalLine, JournalEntry).join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
         .where(JournalLine.company_id == company.id, JournalLine.party_id == party_id,
                JournalLine.account_id.in_(acc_ids), JournalEntry.status.in_(("posted", "reversed")),
                JournalEntry.entry_date >= start, JournalEntry.entry_date <= end)
         .order_by(JournalEntry.entry_date, JournalEntry.id, JournalLine.line_no))
    # Un renglón por comprobante con su efecto neto para el tercero: un recaudo aplicado a varias facturas es un abono
    # y un cruce de anticipo (baja el anticipo y la factura a la vez) no cambia su saldo.
    by_entry: dict[int, dict] = {}
    for ln, je in db.execute(q).all():
        row = by_entry.setdefault(je.id, {
            "date": je.entry_date, "entry": je.number, "entry_id": je.id,
            "source": "Anulación" if je.reversal_of_id else SOURCE_LABELS.get(je.source_type or "manual", je.source_type),
            "description": je.description, "net": ZERO, "advance": False})
        # Del lado del tercero: lo que aumenta su saldo es "cargo"; lo que lo disminuye, "abono".
        row["net"] += (ln.debit - ln.credit) if kind == "receivable" else (ln.credit - ln.debit)
        row["advance"] = row["advance"] or ln.account_id == acc_ids[1]
    rows, balance, debits, credits = [], opening, ZERO, ZERO
    for row in by_entry.values():
        net = row.pop("net")
        charge, credit = (net, ZERO) if net > 0 else (ZERO, -net)
        balance += net
        debits += charge
        credits += credit
        rows.append({**row, "charge": charge, "credit": credit, "balance": balance})
    pending = []
    for oi in _open_items(db, company.id, kind, party_id):
        adv = oi.document_type in ADVANCE_TYPES
        pending.append({"open_item_id": oi.id, "document": oi.document_number, "document_type": oi.document_type,
                        "is_advance": adv, "issue_date": oi.issue_date, "due_date": oi.due_date,
                        "days_overdue": 0 if adv else max((end - oi.due_date).days, 0), "currency": oi.currency,
                        "open_amount": -oi.open_amount if adv else oi.open_amount, "functional": functional(oi)})
    return {"party": {"id": party.id, "name": party.legal_name, "tax_id": party.tax_id, "check_digit": party.check_digit,
                      "email": party.email}, "kind": kind, "start": start, "end": end,
            "currency": company.functional_currency, "opening": opening, "charges": debits, "credits": credits,
            "closing": balance, "rows": rows, "pending": pending,
            "pending_total": sum((p["functional"] for p in pending), ZERO)}


STATEMENT_TITLES = {"receivable": "Estado de cuenta", "payable": "Estado de cuenta de proveedor"}


def statement_number(kind: str, start: date, end: date) -> str:
    return f"EC-{'C' if kind == 'receivable' else 'P'}-{start:%Y%m%d}-{end:%Y%m%d}"


def parse_statement_number(number: str) -> tuple[str, date, date]:
    _, k, s, e = number.split("-")
    return ("receivable" if k == "C" else "payable", date(int(s[:4]), int(s[4:6]), int(s[6:])),
            date(int(e[:4]), int(e[4:6]), int(e[6:])))


def statement_docdata(db: Session, company: Company, party_id: int, kind: str, start: date, end: date):
    from app.modules.documents.pdf import DocData, fdate
    from app.modules.documents.pdf import money as fmt
    from app.modules.documents.service import _company_block, _party_block

    st = party_statement(db, company, party_id, kind, start, end)
    party = db.get(Party, party_id)
    rows = [[fdate(r["date"]), f"{r['source']} · {r['description']}", fmt(r["charge"]) if r["charge"] else "",
             fmt(r["credit"]) if r["credit"] else "", fmt(r["balance"])] for r in st["rows"]]
    if st["pending"]:
        rows.append(["", f"DOCUMENTOS PENDIENTES AL {fdate(end)}", "", "", ""])
        for p in st["pending"]:
            detail = "Anticipo / saldo a favor" if p["is_advance"] else (
                f"Vence {fdate(p['due_date'])}" + (f" · {p['days_overdue']} días vencido" if p["days_overdue"] else ""))
            rows.append([fdate(p["issue_date"]), f"{p['document']} · {detail}", "", "", fmt(p["functional"])])
    closing = st["closing"]
    whose = ("Saldo a cargo del cliente" if closing >= 0 else "Saldo a favor del cliente") if kind == "receivable" \
        else ("Saldo a favor del proveedor" if closing >= 0 else "Saldo a cargo del proveedor")
    return DocData(
        title=STATEMENT_TITLES[kind], number=statement_number(kind, start, end), company=_company_block(company),
        party_label="Cliente" if kind == "receivable" else "Proveedor", party=_party_block(party),
        fields=[("Periodo", f"{fdate(start)} a {fdate(end)}"), ("Moneda", company.functional_currency),
                ("Saldo inicial", fmt(st["opening"])), ("Saldo final", fmt(closing))],
        lines=[], columns=[("Fecha", 22, "L"), ("Concepto", 89.9, "L"), ("Cargos", 25, "R"), ("Abonos", 25, "R"),
                           ("Saldo", 26, "R")],
        rows=rows, totals=[("Saldo inicial", fmt(st["opening"]), False), ("Cargos", fmt(st["charges"]), False),
                           ("Abonos", fmt(st["credits"]), False), (whose, fmt(abs(closing)), True)],
        currency=company.functional_currency,
        notes="Valores en moneda funcional. Si encuentra diferencias con sus registros, por favor infórmenos dentro "
              "de los 10 días siguientes al recibo de este estado de cuenta.")


def statement_pdf(db: Session, company: Company, party_id: int, kind: str, start: date, end: date) -> tuple[str, bytes]:
    from app.modules.documents.pdf import render
    from app.modules.documents.service import filename_for

    data = statement_docdata(db, company, party_id, kind, start, end)
    return filename_for(data), render(data)


# ---------------------------------------------------------------- envío por correo
def statement_message(db: Session, company: Company, party_id: int, kind: str, end: date) -> dict:
    from app.modules.documents.pdf import fdate

    party = db.get(Party, party_id)
    if party is None or party.company_id != company.id:
        raise NotFound("Tercero no encontrado")
    name = company.trade_name or company.legal_name
    ask = ("Le agradecemos revisarlo y programar el pago de los documentos vencidos." if kind == "receivable"
           else "Le agradecemos confirmar que coincide con sus registros.")
    return {"to": [party.email] if party.email else [],
            "subject": f"Estado de cuenta al {fdate(end)} · {name}",
            "body": (f"Señores {party.legal_name}:\n\nCordial saludo; adjuntamos su estado de cuenta con corte al "
                     f"{fdate(end)}. {ask}\n\nQuedamos atentos a cualquier inquietud.\n\n{name}")}


def queue_statement_email(db: Session, p, party_id: int, kind: str, start: date, end: date, to: list[str],
                          cc: list[str] | None = None, subject: str | None = None, body: str | None = None):
    from app.core.audit import log_action
    from app.modules.documents import mailer
    from app.modules.documents.models import DocumentEmail
    from app.modules.documents.service import _split
    from app.modules.org.models import IntegrationEvent

    _check(kind)
    if end < start:
        raise BusinessRuleViolation("La fecha final no puede ser anterior a la inicial")
    defaults = statement_message(db, p.company, party_id, kind, end)
    to, cc = _split(to), _split(cc)
    if not to:
        raise BusinessRuleViolation("Indique al menos un destinatario")
    if len(to) + len(cc) > 10:
        raise BusinessRuleViolation("Máximo 10 destinatarios por envío")
    mailer.ensure_configured()
    em = DocumentEmail(company_id=p.company_id, doc_type="party_statement", doc_id=party_id,
                       doc_number=statement_number(kind, start, end), to_addresses=", ".join(to),
                       cc_addresses=", ".join(cc) or None, subject=(subject or defaults["subject"])[:255],
                       body=body or defaults["body"], created_by_id=p.user_id)
    db.add(em)
    db.flush()
    db.add(IntegrationEvent(company_id=p.company_id, event_type="document.email", payload={"email_id": em.id},
                            idempotency_key=f"document_email:{em.id}", max_attempts=5))
    log_action(db, "send", "parties", party_id, f"Envío del estado de cuenta {em.doc_number} a {em.to_addresses}")
    return em

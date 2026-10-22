"""Tesorería: retenciones al pagar, extractos bancarios desde archivo y recibos / comprobantes de egreso en PDF."""
import io
from decimal import Decimal

from conftest import TODAY, build_company
from helpers import D, all_entries_balanced, approved_po, receive, run_outbox

from app.core.db import SessionLocal
from app.modules.documents import service as docs


def _supplier_invoice(env, number="FE-2001", qty=10, price=100):
    po = approved_po(env, qty=qty, price=price)
    gr = receive(env, po, qty)
    contador = env.api("contador")
    inv = contador.post("/purchasing/invoices", {
        "supplier_id": env["supplier_id"], "supplier_invoice_number": number, "invoice_date": str(TODAY),
        "currency": "COP", "lines": [{"receipt_line_id": gr["lines"][0]["id"], "description": "Artículo A",
                                      "quantity": str(qty), "unit_price": str(price)}]})
    contador.post(f"/purchasing/invoices/{inv['id']}/post")
    items = contador.get(f"/accounting/open-items?kind=payable&party_id={env['supplier_id']}")["items"]
    item = next(i for i in items if i["document_type"] == "supplier_invoice" and i["document_id"] == inv["id"])
    return inv, item


def _pay(env, item, amount, withholdings=None, key="pago-prueba-1", expect=None):
    return env.api("admin1").post("/accounting/payments", {
        "kind": "disbursement", "party_id": env["supplier_id"], "payment_date": str(TODAY),
        "bank_account_id": env["bank_account_id"], "method": "transfer", "currency": "COP", "amount": str(amount),
        "idempotency_key": key, "withholdings": withholdings or [],
        "allocations": [{"open_item_id": item["id"],
                         "amount": str(D(amount) + sum(D(w["amount"]) for w in withholdings or []))}]},
        expect=expect)


def test_withholding_at_invoice_is_not_repeated_at_payment(env):
    inv, item = _supplier_invoice(env)
    assert D(inv["withholding_total"]) == D("25.00")  # 2,5 % sobre 1.000 al causar la factura
    rtec = env.api("admin1").get("/taxes?limit=200")["items"]
    rtec25 = next(t for t in rtec if t["code"] == "RTEC25")
    r = _pay(env, item, D(item["open_amount"]) - 25, [{"tax_id": rtec25["id"], "base": "1000", "amount": "25"}],
             expect=422)
    assert "no se retiene dos veces" in r.json()["error"]["message"]
    sugg = env.api("admin1").get(
        f"/accounting/payments/withholding-suggestions?open_item_id={item['id']}&applied={item['open_amount']}")
    assert rtec25["id"] in sugg["already_withheld"] and all(s["tax_id"] != rtec25["id"] for s in sugg["suggestions"])


def test_withholding_on_payment_policy(env):
    admin = env.api("admin1")
    admin.patch("/company/settings", {"settings": {"withholding_on_payment": True}})
    inv, item = _supplier_invoice(env, number="FE-2002")
    assert D(inv["withholding_total"]) == 0 and D(inv["payable_total"]) == D("1190.00")
    sugg = admin.get(f"/accounting/payments/withholding-suggestions?open_item_id={item['id']}&applied=1190")
    s = next(x for x in sugg["suggestions"] if x["code"] == "RTEC25")
    assert D(s["base"]) == D("1000.00") and D(s["amount"]) == D("25.00")
    # Pago parcial: la base es proporcional a lo aplicado
    half = admin.get(f"/accounting/payments/withholding-suggestions?open_item_id={item['id']}&applied=595")
    assert D(next(x for x in half["suggestions"] if x["code"] == "RTEC25")["base"]) == D("500.00")

    pay = _pay(env, item, "1165.00", [{"tax_id": s["tax_id"], "base": "1000", "amount": "25"}], key="pago-retencion")
    assert D(pay["withholding_amount"]) == 25 and pay["withholdings"][0]["certificate_number"] == "CR-000001"
    still_open = admin.get(f"/accounting/open-items?kind=payable&party_id={env['supplier_id']}")["items"]
    assert all(i["id"] != item["id"] for i in still_open)  # quedó pagada por completo
    entry = admin.get(f"/accounting/entries/{pay['journal_entry_id']}")
    credits = sorted(D(ln["credit"]) for ln in entry["lines"] if D(ln["credit"]) > 0)
    assert credits == [D("25.00"), D("1165.00")]  # retención por pagar y salida de banco
    assert all_entries_balanced(env["company_id"])


def test_venezuela_withholding_certificate_format(env, client):
    with SessionLocal() as db:
        ve = build_company(db, "VE", code="VEWH")
        db.commit()
        from app.core.deps import Principal
        from app.modules.accounting.service import withholding_certificate_number
        from app.modules.iam.models import User

        user = db.query(User).first()
        p = Principal(user=user, company=ve)
        first = withholding_certificate_number(db, p, TODAY)
        second = withholding_certificate_number(db, p, TODAY)
    assert first == f"{TODAY:%Y%m}00000001" and second == f"{TODAY:%Y%m}00000002"


CSV_LOCAL = """Banco de Pruebas S.A.
Cuenta corriente 123-456
Fecha;Descripción;Documento;Valor Débito;Valor Crédito;Saldo
01/10/2026;Consignación cliente;RC-000001;;1.500.000,50;2.500.000,50
02/10/2026;Pago proveedor;CE-000004;850.000,00;;1.650.000,50
03/10/2026;Comisión bancaria;;12.000;;1.638.000,50
"""


def test_parse_statement_csv_local_format(env):
    admin = env.api("admin1")
    r = admin.client.post("/api/v1/accounting/bank-statements/parse", headers=admin.headers,
                          files={"file": ("extracto.csv", CSV_LOCAL.encode("cp1252"), "text/csv")})
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["format"] == "csv" and len(st["lines"]) == 3
    assert [D(ln["amount"]) for ln in st["lines"]] == [D("1500000.50"), D("-850000.00"), D("-12000")]
    assert st["lines"][0]["reference"] == "RC-000001" and st["lines"][0]["txn_date"] == "2026-10-01"
    assert D(st["opening_balance"]) == D("1000000.00") and D(st["closing_balance"]) == D("1638000.50")
    assert st["statement_date"] == "2026-10-03" and not st["warnings"]


def test_parse_statement_xlsx_and_ofx(env):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Fecha", "Concepto", "Referencia", "Monto"])
    ws.append([TODAY, "Transferencia recibida", "T-1", 250000])
    ws.append([TODAY, "Pago nómina", "T-2", -100000.5])
    buf = io.BytesIO()
    wb.save(buf)
    admin = env.api("admin1")
    r = admin.client.post("/api/v1/accounting/bank-statements/parse", headers=admin.headers,
                          files={"file": ("extracto.xlsx", buf.getvalue(),
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    st = r.json()
    assert r.status_code == 200 and st["format"] == "xlsx"
    assert [D(ln["amount"]) for ln in st["lines"]] == [D("250000"), D("-100000.5")]

    ofx = b"""OFXHEADER:100
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261005120000<TRNAMT>300000.00<FITID>A1<NAME>Abono cliente</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261006<TRNAMT>-45000.00<FITID>A2<MEMO>Pago servicios</STMTTRN>
</BANKTRANLIST><LEDGERBAL><BALAMT>755000.00<DTASOF>20261006</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    r = admin.client.post("/api/v1/accounting/bank-statements/parse", headers=admin.headers,
                          files={"file": ("banco.ofx", ofx, "application/octet-stream")})
    st = r.json()
    assert st["format"] == "ofx" and len(st["lines"]) == 2 and st["lines"][1]["description"] == "Pago servicios"
    assert D(st["closing_balance"]) == D("755000.00") and D(st["opening_balance"]) == D("500000.00")
    bad = admin.client.post("/api/v1/accounting/bank-statements/parse", headers=admin.headers,
                            files={"file": ("x.csv", b"a;b;c\n1;2;3\n", "text/csv")})
    assert bad.status_code == 422 and "encabezados" in bad.json()["error"]["message"]
    vend = env.api("vendedor")
    assert vend.client.post("/api/v1/accounting/bank-statements/parse", headers=vend.headers,
                            files={"file": ("x.csv", b"x", "text/csv")}).status_code == 403


def test_number_parsing_heuristics():
    from app.modules.accounting.statements import parse_number

    cases = {"1.234,56": "1234.56", "1,234.56": "1234.56", "1.234.567": "1234567", "12,5": "12.5", "1,234": "1234",
             "(1.200,00)": "-1200.00", "$ 1.200": "1200", "-850000.25": "-850000.25", "": None}
    for raw, expected in cases.items():
        got = parse_number(raw)
        assert (got is None and expected is None) or got == Decimal(expected), (raw, got)


def test_payment_pdf_and_email(env):
    admin = env.api("admin1")
    admin.patch("/company/settings", {"settings": {"withholding_on_payment": True}})
    _, item = _supplier_invoice(env, number="FE-2003")
    rt = next(t for t in admin.get("/taxes?limit=200")["items"] if t["code"] == "RTEC25")
    pay = _pay(env, item, "1165.00", [{"tax_id": rt["id"], "base": "1000", "amount": "25"}], key="pago-documento")
    r = admin._call("GET", f"/documents/payment/{pay['id']}/pdf", 200)
    assert r.content.startswith(b"%PDF") and "Comprobante_de_egreso" in r.headers["content-disposition"]
    with SessionLocal() as db:
        from app.modules.accounting.models import Payment

        data = docs.document_data(db, "payment", db.get(Payment, pay["id"]))
    assert data.title == "Comprobante de egreso" and data.party_label == "Pagado a"
    assert data.notes == "Son: MIL CIENTO SESENTA Y CINCO PESOS CON 00/100"
    assert "CR-000001" in data.fiscal[0][1] and data.rows[0][-1] == "1.190,00"
    em = admin.post(f"/documents/payment/{pay['id']}/email", {"to": ["pagos@proveedor-pruebas.co"]}, expect=202).json()
    assert "Comprobante de egreso" in em["subject"]
    run_outbox()
    assert admin.get(f"/documents/payment/{pay['id']}/emails")[0]["status"] == "sent"
    admin.post(f"/accounting/payments/{pay['id']}/void", {"reason": "Pago registrado por error"})
    with SessionLocal() as db:
        from app.modules.accounting.models import Payment

        assert docs.document_data(db, "payment", db.get(Payment, pay["id"])).notice == "ANULADO"
    admin.post(f"/documents/payment/{pay['id']}/email", {"to": ["pagos@proveedor-pruebas.co"]}, expect=422)

"""Cartera: anticipos y saldos a favor, cruces, pago de varias facturas, conciliación del auxiliar contra el mayor y
estado de cuenta por tercero."""
from helpers import TODAY, D, all_entries_balanced, confirmed_so, run_outbox, scalar, shipped_dispatch, stock_in


def _invoice(env, qty=2, price=200):
    """Factura de venta emitida: 2 × 200 + IVA 19 % = 476."""
    so = confirmed_so(env, "A", qty=qty, price=price)
    d = shipped_dispatch(env, so)
    a = env.api("admin1")
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    inv = a.post(f"/einvoicing/invoices/{inv['id']}/issue")
    return next(i for i in a.get(f"/accounting/open-items?kind=receivable&party_id={env['customer_id']}")["items"]
                if i["document_type"] == "invoice" and i["document_id"] == inv["id"])


def _pay(env, amount, allocations, kind="receipt", key="cobro-cartera-1", withholdings=None, expect=None):
    party = env["customer_id"] if kind == "receipt" else env["supplier_id"]
    return env.api("admin1").post("/accounting/payments", {
        "kind": kind, "party_id": party, "payment_date": str(TODAY), "bank_account_id": env["bank_account_id"],
        "method": "transfer", "currency": "COP", "amount": str(amount), "idempotency_key": key,
        "withholdings": withholdings or [], "allocations": allocations}, expect=expect)


def _gl(env, code, party=None):
    sql = """select coalesce(sum(l.debit - l.credit), 0) from journal_lines l
             join journal_entries e on e.id = l.entry_id join accounts a on a.id = l.account_id
             where a.company_id = :c and a.code = :k and e.status in ('posted','reversed')"""
    if party:
        sql += " and l.party_id = :p"
    return scalar(sql, c=env["company_id"], k=code, p=party)


def _advance(env, kind="receivable"):
    return next(i for i in env.api("admin1").get(f"/accounting/open-items?kind={kind}")["items"]
                if i["document_type"] == "advance")


def test_customer_advance_apply_and_void(env):
    a = env.api("admin1")
    stock_in(env, "A", qty=20, price=100)
    pay = _pay(env, 500, [])  # anticipo: recaudo sin factura
    adv = _advance(env)
    assert D(adv["open_amount"]) == 500 and adv["document_number"] == pay["number"]
    assert _gl(env, "280505", env["customer_id"]) == D("-500")  # anticipo recibido: pasivo con el tercero
    aging = a.get("/accounting/aging?kind=receivable")
    assert D(aging["totals"]["advances"]) == D("-500") and D(aging["total"]) == D("-500")
    assert aging["labels"]["current"] == "Por vencer"

    inv = _invoice(env)
    # Un anticipo no se paga, se cruza; y no se cruza más de su saldo ni de la factura
    _pay(env, 100, [{"open_item_id": adv["id"], "amount": "100"}], key="cobro-invalido", expect=422)
    a.post(f"/accounting/advances/{adv['id']}/apply", {"allocations": [{"open_item_id": inv["id"], "amount": "600"}]},
           expect=422)
    apps = a.post(f"/accounting/advances/{adv['id']}/apply",
                  {"allocations": [{"open_item_id": inv["id"], "amount": "300"}]})
    assert len(apps) == 1 and apps[0]["status"] == "posted"
    items = {i["id"]: i for i in a.get("/accounting/open-items?kind=receivable")["items"]}
    assert D(items[inv["id"]]["open_amount"]) == D("176.00") and D(items[adv["id"]]["open_amount"]) == D("200.00")
    assert _gl(env, "280505", env["customer_id"]) == D("-200") and all_entries_balanced(env["company_id"])

    # El pago que originó el anticipo no se anula mientras el anticipo esté cruzado
    a.post(f"/accounting/payments/{pay['id']}/void", {"reason": "Pago duplicado"}, expect=409)
    env.api("admin2").post(f"/accounting/advance-applications/{apps[0]['id']}/void", {"reason": "Cruce equivocado"})
    items = {i["id"]: i for i in a.get("/accounting/open-items?kind=receivable")["items"]}
    assert D(items[inv["id"]]["open_amount"]) == D("476.00") and D(items[adv["id"]]["open_amount"]) == D("500.00")
    a.post(f"/accounting/payments/{pay['id']}/void", {"reason": "Pago duplicado"})
    assert all(i["document_type"] != "advance" for i in a.get("/accounting/open-items?kind=receivable")["items"])
    rec = a.get("/accounting/reconciliation?kind=receivable")
    assert rec["balanced"], rec


def test_multi_invoice_payment_with_overpayment(env):
    stock_in(env, "A", qty=20, price=100)
    i1, i2 = _invoice(env), _invoice(env, qty=1, price=300)  # 476 y 357
    # Lo aplicado no puede superar el pago; las retenciones exigen facturas
    _pay(env, 100, [{"open_item_id": i1["id"], "amount": "476"}], key="cobro-excede", expect=422)
    rtec = scalar("select id from taxes where company_id = :c and code = 'RTEC25'", c=env["company_id"])
    _pay(env, 100, [], key="cobro-ret-sin-factura", expect=422,
         withholdings=[{"tax_id": rtec, "base": "100", "amount": "2.50"}])
    pay = _pay(env, 933, [{"open_item_id": i1["id"], "amount": "476"}, {"open_item_id": i2["id"], "amount": "357"}])
    assert len(pay["allocations"]) == 2
    adv = _advance(env)
    assert D(adv["open_amount"]) == 100  # el excedente queda como saldo a favor
    a = env.api("admin1")
    by_party = a.get("/accounting/aging/by-party?kind=receivable")
    row = next(r for r in by_party if r["party_id"] == env["customer_id"])
    assert D(row["advances"]) == D("-100") and D(row["total"]) == D("-100") and row["documents"] == 0
    rec = a.get("/accounting/reconciliation?kind=receivable")
    assert rec["balanced"] and D(rec["accounts"][1]["gl"]) == D("100.00")
    x = a._call("GET", "/accounting/aging.xlsx?kind=receivable", 200)
    assert x.content[:2] == b"PK"


def test_reconciliation_detects_manual_entries_and_statement(env):
    a, b = env.api("admin1"), env.api("admin2")
    stock_in(env, "A", qty=20, price=100)
    inv = _invoice(env)
    _pay(env, 200, [{"open_item_id": inv["id"], "amount": "200"}], key="abono-parcial")
    rec = a.get("/accounting/reconciliation?kind=receivable")
    assert rec["balanced"] and D(rec["accounts"][0]["subledger"]) == D("276.00")
    # Un asiento manual a la cuenta de control descuadra el auxiliar contra el mayor
    acc = scalar("select id from accounts where company_id = :c and code = '130505'", c=env["company_id"])
    other = scalar("select id from accounts where company_id = :c and code = '425050'", c=env["company_id"])
    e = a.post("/accounting/entries", {"entry_date": str(TODAY), "description": "Ajuste manual a cartera",
                                        "lines": [{"account_id": acc, "debit": "50", "party_id": env["customer_id"]},
                                                  {"account_id": other, "credit": "50"}]})
    b.post(f"/accounting/entries/{e['id']}/post")
    rec = a.get("/accounting/reconciliation?kind=receivable")
    assert not rec["balanced"] and D(rec["difference"]) == D("50.00") and rec["parties_with_difference"] == 1
    assert rec["parties"][0]["party_id"] == env["customer_id"] and D(rec["parties"][0]["difference"]) == D("50.00")

    st = a.get(f"/accounting/party-statement?party_id={env['customer_id']}&kind=receivable"
               f"&start={TODAY.replace(day=1)}&end={TODAY}")
    assert D(st["opening"]) == 0 and D(st["charges"]) == D("526.00") and D(st["credits"]) == D("200.00")
    assert D(st["closing"]) == D("326.00") and D(st["rows"][-1]["balance"]) == D("326.00")
    assert [p["document"] for p in st["pending"]] == [inv["document_number"]]
    pdf = a._call("GET", f"/accounting/party-statement/pdf?party_id={env['customer_id']}&kind=receivable"
                         f"&start={TODAY.replace(day=1)}&end={TODAY}", 200)
    assert pdf.content.startswith(b"%PDF")
    defaults = a.get(f"/accounting/party-statement/email-defaults?party_id={env['customer_id']}&kind=receivable"
                     f"&start={TODAY.replace(day=1)}&end={TODAY}")
    assert defaults["to"] == ["cliente@pruebas.datasys.co"] and "Estado de cuenta" in defaults["subject"]
    em = a.post("/accounting/party-statement/email", {
        "party_id": env["customer_id"], "kind": "receivable", "start": str(TODAY.replace(day=1)), "end": str(TODAY),
        "to": defaults["to"]}, expect=202).json()
    run_outbox()
    assert scalar("select status from document_emails where id = :i", i=em["id"]) == "sent"
    env.api("vendedor").get("/accounting/reconciliation?kind=receivable", expect=403)


def test_supplier_advance_and_opening_advances(env):
    from test_treasury import _supplier_invoice

    a, b = env.api("admin1"), env.api("admin2")
    pay = _pay(env, 300, [], kind="disbursement", key="anticipo-proveedor")
    adv = _advance(env, "payable")
    assert D(adv["open_amount"]) == 300 and _gl(env, "133005", env["supplier_id"]) == D("300")
    _, item = _supplier_invoice(env, number="FE-9001")  # por pagar 1.165
    a.post(f"/accounting/advances/{adv['id']}/apply", {"allocations": [{"open_item_id": item["id"], "amount": "300"}]})
    items = {i["id"]: i for i in a.get("/accounting/open-items?kind=payable&only_open=false")["items"]}
    assert D(items[item["id"]]["open_amount"]) == D("865.00") and items[adv["id"]]["status"] == "paid"
    assert _gl(env, "133005", env["supplier_id"]) == 0
    assert a.get("/accounting/reconciliation?kind=payable")["balanced"]
    assert pay["number"].startswith("CE-")

    # Saldos iniciales: un saldo negativo es un anticipo (saldo a favor) del tercero
    batch = a.post("/imports/opening-batches", {"kind": "receivables", "cutoff_date": str(TODAY),
                                                "source_description": "Cartera y anticipos del sistema anterior"})
    csv_data = ("party_code,document_number,issue_date,due_date,currency,amount\n"
                f"CLI1,FV-OLD-7,{TODAY},{TODAY},COP,1000\nCLI1,ANT-OLD-1,{TODAY},{TODAY},COP,-250\n"
                f"CLI1,CERO-1,{TODAY},{TODAY},COP,0\n")
    job = a.client.post("/api/v1/imports/jobs", headers=a.headers,
                        data={"entity": "opening_receivables", "opening_batch_id": str(batch["id"])},
                        files={"file": ("cartera.csv", csv_data.encode("utf-8"), "text/csv")}).json()
    assert job["valid_rows"] == 2 and job["invalid_rows"] == 1
    a.post(f"/imports/jobs/{job['id']}/commit")
    b.post(f"/imports/opening-batches/{batch['id']}/approve")
    b.post(f"/imports/opening-batches/{batch['id']}/post")
    ar = a.get(f"/accounting/open-items?kind=receivable&party_id={env['customer_id']}")["items"]
    kinds = {i["document_number"]: (i["document_type"], D(i["open_amount"])) for i in ar}
    assert kinds["ANT-OLD-1"] == ("opening_advance", D("250.00")) and kinds["FV-OLD-7"] == ("opening", D("1000.00"))
    assert _gl(env, "280505", env["customer_id"]) == D("-250") and _gl(env, "130505", env["customer_id"]) == D("1000")
    assert a.get("/accounting/reconciliation?kind=receivable")["balanced"]
    # El anticipo inicial se cruza contra la factura inicial
    opening_adv = next(i for i in ar if i["document_number"] == "ANT-OLD-1")
    opening_inv = next(i for i in ar if i["document_number"] == "FV-OLD-7")
    a.post(f"/accounting/advances/{opening_adv['id']}/apply",
           {"allocations": [{"open_item_id": opening_inv["id"], "amount": "250"}]})
    st = a.get(f"/accounting/party-statement?party_id={env['customer_id']}&kind=receivable&start={TODAY}&end={TODAY}")
    assert D(st["closing"]) == D("750.00") and D(st["pending_total"]) == D("750.00")
    assert all_entries_balanced(env["company_id"])

"""Empresa venezolana: moneda funcional VES, operación en USD con tasa, IVA 16 %, IGTF y retención de IVA."""
from datetime import timedelta
from decimal import Decimal

from conftest import PASSWORD, Api, build_company
from helpers import TODAY, D, run_outbox, scalar
from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.accounting.models import Account, BankAccount
from app.modules.einvoicing.models import NumberingRange
from app.modules.iam.models import Role, UserCompanyRole
from app.modules.iam.service import create_user
from app.modules.inventory.models import Warehouse
from app.modules.masters.models import Item, Party, Tax, UnitOfMeasure
from app.modules.masters.validation import rif_check_digit
from app.modules.org.models import ExchangeRate


def test_ve_sale_in_usd_with_igtf(client):
    with SessionLocal() as db:
        c = build_company(db, "VE", code="TESTVE", special=True)
        role = db.scalar(select(Role).where(Role.code == "admin"))
        for n in ("ve1", "ve2"):
            u = create_user(db, email=f"{n}@pruebas.datasys.co", full_name=n, password=PASSWORD)
            db.add(UserCompanyRole(user_id=u.id, company_id=c.id, role_id=role.id))
        und = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "UND"))
        iva = db.scalar(select(Tax).where(Tax.company_id == c.id, Tax.code == "IVA16"))
        item = Item(company_id=c.id, sku="VE-1", name="Producto VE", item_type="service", is_stocked=False,
                    base_uom_id=und.id, sales_tax_id=iva.id, list_price=Decimal("100"))
        cust = Party(company_id=c.id, code="CVE", legal_name="Cliente Venezuela C.A.", id_type="RIF", tax_id="J00124134",
                     check_digit=rif_check_digit("J00124134"), is_customer=True, address="Av. Principal, Valencia",
                     email="cliente@pruebas.datasys.co", country_code="VE")
        db.add_all([item, cust])
        db.add(ExchangeRate(from_currency="USD", to_currency="VES", rate_date=TODAY, rate=Decimal("40"),
                            source="Tasa de prueba"))
        gl = db.scalar(select(Account).where(Account.company_id == c.id, Account.code == "1.1.01.03"))
        bank = BankAccount(company_id=c.id, name="Cuenta USD", bank_name="Banco", account_number_masked="****9",
                           currency="USD", gl_account_id=gl.id)
        db.add(bank)
        db.add(NumberingRange(company_id=c.id, doc_type="invoice", prefix="A", range_from=1, range_to=999, next_number=1,
                              valid_from=TODAY - timedelta(days=1), valid_to=TODAY + timedelta(days=30),
                              authorization_number="IMPRENTA-SBX", environment="sandbox"))
        wh = db.scalar(select(Warehouse).where(Warehouse.company_id == c.id))
        db.commit()
        ids = dict(c=c.id, item=item.id, cust=cust.id, bank=bank.id, wh=wh.id, site=wh.site_id)
    a, b = Api(client, "ve1@pruebas.datasys.co", ids["c"]), Api(client, "ve2@pruebas.datasys.co", ids["c"])
    so = a.post("/sales/orders", {"site_id": ids["site"], "customer_id": ids["cust"], "warehouse_id": ids["wh"],
                                  "order_date": str(TODAY), "currency": "USD",
                                  "lines": [{"item_id": ids["item"], "quantity": "2"}]})
    assert D(so["exchange_rate"]) == 40 and D(so["total"]) == D(232)
    b.post(f"/sales/orders/{so['id']}/confirm")
    d = a.post("/logistics/dispatches", {"sales_order_id": so["id"]})
    a.post(f"/logistics/dispatches/{d['id']}/start-picking")
    a.post(f"/logistics/dispatches/{d['id']}/picking", {"picks": [{"dispatch_line_id": d["lines"][0]["id"],
                                                                  "qty_picked": "2"}]})
    a.post(f"/logistics/dispatches/{d['id']}/pack", {"packages_count": 1})
    a.post(f"/logistics/dispatches/{d['id']}/ship", {})
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    inv = a.post(f"/einvoicing/invoices/{inv['id']}/issue")
    run_outbox()
    inv = a.get(f"/einvoicing/invoices/{inv['id']}")
    assert inv["edoc_status"] == "accepted" and inv["control_number"] == "SBX-A-00000001"
    assert not inv["legal_validity"]
    # Contabilidad en bolívares: 232 USD × 40 = 9.280 Bs.
    je = scalar("select total_debit from journal_entries where source_type = 'sales_invoice'")
    assert je == D(9280)
    ar = a.get("/accounting/open-items?kind=receivable")["items"][0]
    riva = scalar("select id from taxes where company_id = :c and code = 'RIVA75'", c=ids["c"])
    # Cobro en USD (contribuyente especial: percibe IGTF 3 %) con retención de IVA 75 % (24 USD)
    pay = a.post("/accounting/payments", {
        "kind": "receipt", "party_id": ids["cust"], "payment_date": str(TODAY), "bank_account_id": ids["bank"],
        "method": "transfer", "currency": "USD", "amount": "208", "idempotency_key": "cobro-ve-0001",
        "withholdings": [{"tax_id": riva, "base": "32", "amount": "24"}],
        "allocations": [{"open_item_id": ar["id"], "amount": "232"}]})
    assert D(pay["igtf_amount"]) == D("6.24")
    igtf = scalar("""select sum(l.credit) from journal_lines l join accounts a on a.id = l.account_id
                     where a.code = '2.1.03.04' and l.company_id = :c""", c=ids["c"])
    assert igtf == D("249.60")
    bs = a.get(f"/accounting/reports/balance-sheet?as_of={TODAY}")
    assert bs["balanced"]

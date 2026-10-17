"""Concurrencia real con varias conexiones a PostgreSQL: reservas, numeración e idempotencia."""
import threading
from decimal import Decimal

import pytest
from helpers import TODAY, D, stock_in

from app.core.db import SessionLocal

pytestmark = pytest.mark.concurrency


def _parallel(n, fn):
    barrier = threading.Barrier(n)
    results = [None] * n

    def run(i):
        barrier.wait()
        try:
            results[i] = fn(i)
        except Exception as exc:  # noqa: BLE001
            results[i] = exc

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    return results


def test_concurrent_reservations_never_oversell(env):
    stock_in(env, "A", qty=10, price=10)
    a = env.api("admin1")
    orders = [a.post("/sales/orders", {"site_id": env["site_id"], "customer_id": env["customer_id"],
                                       "warehouse_id": env["warehouse_id"], "order_date": str(TODAY),
                                       "currency": "COP",
                                       "lines": [{"item_id": env["items"]["A"], "quantity": "4"}]}) for _ in range(5)]
    from fastapi.testclient import TestClient

    from app.main import app

    def confirm(i):
        c = TestClient(app)
        return c.post(f"/api/v1/sales/orders/{orders[i]['id']}/confirm", headers=a.headers).status_code

    codes = _parallel(5, confirm)
    assert sorted(codes) == [200, 200, 422, 422, 422], codes  # 4+4 ≤ 10 < 12
    assert D(a.get(f"/inventory/availability/{env['items']['A']}")["available"]) == 2
    assert a.get("/inventory/consistency")["consistent"]


def test_concurrent_document_numbers_are_unique(env):
    from app.core.numbering import next_number

    def take(_):
        with SessionLocal() as db:
            n = next_number(db, env["company_id"], "purchase_order")
            db.commit()
            return n

    nums = _parallel(10, take)
    assert len(set(nums)) == 10 and all(isinstance(n, str) for n in nums)


def test_concurrent_payment_retries_are_idempotent(env):
    from helpers import approved_po, receive

    po = approved_po(env, qty=1, price=100)
    gr = receive(env, po, 1)
    c = env.api("contador")
    inv = c.post("/purchasing/invoices", {"supplier_id": env["supplier_id"], "supplier_invoice_number": "CC-1",
                                          "invoice_date": str(TODAY), "currency": "COP",
                                          "lines": [{"receipt_line_id": gr["lines"][0]["id"], "description": "A",
                                                     "quantity": "1", "unit_price": "100"}]})
    c.post(f"/purchasing/invoices/{inv['id']}/post")
    item = c.get("/accounting/open-items?kind=payable")["items"][0]
    from fastapi.testclient import TestClient

    from app.main import app

    body = {"kind": "disbursement", "party_id": env["supplier_id"], "payment_date": str(TODAY),
            "bank_account_id": env["bank_account_id"], "method": "transfer", "currency": "COP",
            "amount": item["open_amount"], "idempotency_key": "pago-concurrente-1",
            "allocations": [{"open_item_id": item["id"], "amount": item["open_amount"]}]}
    admin = env.api("admin1")

    def pay(_):
        return TestClient(app).post("/api/v1/accounting/payments", json=body, headers=admin.headers).status_code

    codes = _parallel(4, pay)
    assert codes.count(201) + codes.count(200) >= 1
    assert all(code in (200, 201, 409, 422) for code in codes), codes
    from sqlalchemy import func, select

    from app.modules.accounting.models import Payment

    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
    assert Decimal(c.get("/accounting/open-items?kind=payable&only_open=false")["items"][0]["open_amount"]) == 0

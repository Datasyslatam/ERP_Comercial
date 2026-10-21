"""Documentos comerciales en PDF y envío por correo con cola, reintentos y bitácora."""
import email
from datetime import UTC, datetime, timedelta
from pathlib import Path

from conftest import TODAY
from helpers import approved_po, confirmed_so, run_outbox, shipped_dispatch, stock_in
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.documents import service as docs
from app.modules.documents.models import DocumentEmail
from app.modules.org.models import IntegrationEvent
from app.modules.sales.models import SalesOrder


def _quote(env):
    return env.api("vendedor").post("/sales/quotes", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "quote_date": str(TODAY),
        "valid_until": str(TODAY + timedelta(days=10)), "currency": "COP",
        "lines": [{"item_id": env["items"]["A"], "quantity": "2", "unit_price": "100", "discount_pct": "5"}]})


def _mail_files(company_id) -> list[Path]:
    folder = Path(get_settings().storage_path).resolve() / "mail" / str(company_id)
    return sorted(folder.glob("*.eml"), key=lambda f: f.stat().st_mtime) if folder.exists() else []


def test_pdfs_for_the_four_documents(env):
    admin = env.api("admin1")
    q = _quote(env)
    stock_in(env, qty=10)
    so = confirmed_so(env, qty=3)
    po = approved_po(env, qty=4, price=50)
    d = shipped_dispatch(env, so)
    inv = admin.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    admin.post(f"/einvoicing/invoices/{inv['id']}/issue")
    run_outbox()  # el adaptador sandbox acepta el documento
    for doc_type, doc_id in (("sales_quote", q["id"]), ("sales_order", so["id"]), ("purchase_order", po["id"]),
                             ("sales_invoice", inv["id"])):
        r = admin._call("GET", f"/documents/{doc_type}/{doc_id}/pdf", 200)
        assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF") and len(r.content) > 1500
    admin._call("GET", "/documents/no_existe/1/pdf", 404)
    env.api("comprador")._call("GET", f"/documents/sales_invoice/{inv['id']}/pdf", 403)

    # Contenido: datos de la factura en sandbox y de la cotización con descuento
    with SessionLocal() as db:
        from app.modules.einvoicing.models import SalesInvoice
        from app.modules.sales.models import SalesQuote

        data = docs.document_data(db, "sales_invoice", db.get(SalesInvoice, inv["id"]))
        assert data.notice == "Documento de PRUEBAS: sin validez fiscal" and data.party_label == "Adquiriente"
        assert any(label.startswith("CUFE") for label, _ in data.fiscal)
        assert data.totals[-1][0] == "Total COP" and data.totals[-1][2] is True
        qd = docs.document_data(db, "sales_quote", db.get(SalesQuote, q["id"]))
        assert qd.lines[0].discount_pct == 5 and str(qd.lines[0].subtotal) == "190.00"
        assert ("Vigente hasta", (TODAY + timedelta(days=10)).strftime("%d/%m/%Y")) in qd.fields


def test_email_is_queued_sent_with_pdf_and_logged(env):
    stock_in(env, qty=10)
    admin = env.api("admin1")
    so = admin.post("/sales/orders", {
        "site_id": env["site_id"], "customer_id": env["customer_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "currency": "COP", "lines": [{"item_id": env["items"]["A"], "quantity": "2"}]})
    body = {"to": ["compras@cliente-pruebas.co"], "cc": ["vendedor@pruebas.datasys.co"]}
    r = admin.post(f"/documents/sales_order/{so['id']}/email", body, expect=422)
    assert "draft" in r.json()["error"]["message"]
    admin.post(f"/sales/orders/{so['id']}/confirm")
    defaults = admin.get(f"/documents/sales_order/{so['id']}/email-defaults")
    assert defaults["to"] == ["cliente@pruebas.datasys.co"] and so["number"] in defaults["subject"]

    before = len(_mail_files(env["company_id"]))
    em = admin.post(f"/documents/sales_order/{so['id']}/email", body, expect=202).json()
    assert em["status"] == "queued" and so["number"] in em["subject"]
    assert run_outbox() >= 1
    log = admin.get(f"/documents/sales_order/{so['id']}/emails")
    assert log[0]["status"] == "sent" and log[0]["sent_at"] and log[0]["message_id"]
    files = _mail_files(env["company_id"])
    assert len(files) == before + 1
    msg = email.message_from_bytes(files[-1].read_bytes())
    assert msg["To"] == "compras@cliente-pruebas.co" and msg["Cc"] == "vendedor@pruebas.datasys.co"
    pdfs = [p for p in msg.walk() if p.get_content_type() == "application/pdf"]
    assert len(pdfs) == 1 and pdfs[0].get_payload(decode=True).startswith(b"%PDF")
    assert so["number"] in pdfs[0].get_filename()


def test_quote_send_marks_sent_and_rules_by_state(env):
    vend = env.api("vendedor")
    q = _quote(env)
    vend.post(f"/documents/sales_quote/{q['id']}/email", {"to": ["cliente@pruebas.datasys.co"]}, expect=202)
    assert vend.get(f"/sales/quotes/{q['id']}")["status"] == "sent"
    vend.post(f"/documents/sales_quote/{q['id']}/email", {"to": []}, expect=422)
    vend.post(f"/documents/sales_quote/{q['id']}/email", {"to": ["no-es-un-correo"]}, expect=422)

    admin = env.api("admin1")
    po = admin.post("/purchasing/orders", {
        "site_id": env["site_id"], "supplier_id": env["supplier_id"], "warehouse_id": env["warehouse_id"],
        "order_date": str(TODAY), "currency": "COP",
        "lines": [{"item_id": env["items"]["A"], "quantity": "1", "unit_price": "10"}]})
    admin.post(f"/documents/purchase_order/{po['id']}/email", {"to": ["ventas@proveedor.co"]}, expect=422)
    vend.post(f"/documents/purchase_order/{po['id']}/email", {"to": ["ventas@proveedor.co"]}, expect=403)


def test_email_retries_then_fails_with_error(env, monkeypatch):
    stock_in(env, qty=5)
    so = confirmed_so(env, qty=1)
    admin = env.api("admin1")
    em = admin.post(f"/documents/sales_order/{so['id']}/email", {"to": ["cliente@pruebas.datasys.co"]}, expect=202).json()

    def boom(msg, company_id):
        raise ConnectionRefusedError("servidor SMTP no disponible")

    monkeypatch.setattr("app.modules.documents.mailer.send", boom)
    for _ in range(5):
        run_outbox()
        with SessionLocal() as db:  # adelanta el siguiente intento
            db.execute(update(IntegrationEvent).where(IntegrationEvent.event_type == "document.email")
                       .values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1)))
            db.commit()
    with SessionLocal() as db:
        row = db.get(DocumentEmail, em["id"])
        assert row.status == "failed" and row.attempts == 5 and "SMTP no disponible" in row.error
        ev = db.scalar(select(IntegrationEvent).where(IntegrationEvent.idempotency_key == f"document_email:{em['id']}"))
        assert ev.status == "failed"


def test_email_requires_smtp_outside_development(env, monkeypatch):
    stock_in(env, qty=5)
    so = confirmed_so(env, qty=1)
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", settings.effective_jwt_secret)
    monkeypatch.setattr(settings, "environment", "production")
    r = env.api("admin1").post(f"/documents/sales_order/{so['id']}/email", {"to": ["cliente@pruebas.datasys.co"]},
                               expect=422)
    assert "no está configurado" in r.json()["error"]["message"]
    with SessionLocal() as db:
        assert db.scalar(select(DocumentEmail).where(DocumentEmail.doc_id == so["id"])) is None
        assert db.get(SalesOrder, so["id"]).status == "confirmed"

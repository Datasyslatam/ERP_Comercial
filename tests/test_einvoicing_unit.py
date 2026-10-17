"""Pruebas unitarias del módulo de integración de facturación (sin base de datos donde es posible)."""
import hashlib
import json
from datetime import date, time
from decimal import Decimal

import pytest

from app.modules.masters.validation import nit_check_digit, rif_check_digit
from integrations.einvoicing import ADAPTERS, get_adapter
from integrations.einvoicing.base import EDocument, ELine, EParty, ETax, SubmissionResult, TransientProviderError
from integrations.einvoicing.dian import compute_cufe


def _doc(**kw):
    tax = ETax(code="01", name="IVA", rate=Decimal("19"), base=Decimal("1500000.00"), amount=Decimal("285000.00"))
    base = dict(
        internal_id=1, doc_type="invoice", prefix="SETP", number=990000000, issue_date=date(2019, 1, 16),
        issue_time=time(10, 53, 10), due_date=date(2019, 2, 16), currency="COP", exchange_rate=Decimal("1"),
        functional_currency="COP",
        issuer=EParty("NIT", "700085371", "1", "Emisor", "e@x.co", "Calle 1", "Bogotá"),
        customer=EParty("NIT", "800199436", "5", "Adquiriente", "c@x.co", "Cra 2", "Cali"),
        lines=[ELine(1, "SKU", "Producto", Decimal("1"), "UND", Decimal("1500000"), Decimal("0"),
                     Decimal("1500000.00"), tax)],
        taxes=[tax], subtotal=Decimal("1500000.00"), discount_total=Decimal("0"), tax_total=Decimal("285000.00"),
        total=Decimal("1785000.00"), payment_form="credit", authorization_number="18760000001",
        authorization_range=(990000000, 995000000), authorization_valid=(date(2019, 1, 1), date(2030, 1, 1)),
        technical_key="693ff6f2a553c3646a063436fd4dd9ded0311471",
    )
    base.update(kw)
    return EDocument(**base)


def test_check_digits():
    assert nit_check_digit("800197268") == "4"  # NIT DIAN
    assert nit_check_digit("900123456") == "8"
    assert rif_check_digit("J00124134") == "5"
    assert rif_check_digit("J00002961") == "0"


def test_cufe_follows_annex_formula():
    doc = _doc()
    expected_src = ("SETP9900000002019-01-1610:53:10-05:001500000.0001285000.00040.00030.001785000.00"
                    "700085371800199436693ff6f2a553c3646a063436fd4dd9ded03114712")
    assert compute_cufe(doc, "2", doc.technical_key) == hashlib.sha384(expected_src.encode()).hexdigest()


def test_sandbox_dian_accepts_only_as_sandbox_and_builds_ubl():
    res = get_adapter("sandbox_dian").submit(_doc())
    assert res.status == "accepted" and res.environment == "sandbox" and res.legal_validity is False
    assert "NO tiene validez fiscal" in res.message
    assert b"<cbc:UUID schemeID=\"2\" schemeName=\"CUFE-SHA384\">" in res.document
    assert b"<Invoice" in res.document and b"<cac:AccountingCustomerParty>" in res.document


def test_sandbox_dian_rejects_invalid_documents():
    res = get_adapter("sandbox_dian").submit(_doc(number=1, technical_key=None))
    assert res.status == "rejected"
    assert any("rango" in e for e in res.errors) and any("clave técnica" in e for e in res.errors)
    bad_total = get_adapter("sandbox_dian").submit(_doc(total=Decimal("1")))
    assert bad_total.status == "rejected"


def test_sandbox_seniat_amounts_in_bolivares():
    issuer = EParty("RIF", "J12345678", "0", "Emisor VE", None, "Caracas")
    customer = EParty("RIF", "J00124134", "5", "Cliente VE", "c@x.ve", "Valencia")
    tax = ETax("IVA", "IVA 16%", Decimal("16"), Decimal("100.00"), Decimal("16.00"))
    doc = _doc(prefix="A", number=7, currency="USD", exchange_rate=Decimal("40.5"), functional_currency="VES",
               issuer=issuer, customer=customer, taxes=[tax], subtotal=Decimal("100.00"), tax_total=Decimal("16.00"),
               total=Decimal("116.00"), lines=[ELine(1, "S", "Servicio", Decimal("1"), "UND", Decimal("100"),
                                                     Decimal("0"), Decimal("100.00"), tax)])
    res = get_adapter("sandbox_seniat").submit(doc)
    assert res.status == "accepted" and res.control_number == "SBX-A-00000007" and not res.legal_validity
    payload = json.loads(res.document)
    assert payload["totales"]["total_bs"] == "4698.00" and payload["tasa_bcv"] == "40.5"


class _FlakyAdapter:
    """Doble de prueba: simula caídas temporales del proveedor (solo existe en las pruebas)."""

    name, country, environment = "flaky", "CO", "sandbox"
    calls = 0

    def submit(self, doc):
        type(self).calls += 1
        raise TransientProviderError("timeout simulado")

    def status(self, doc, tracking_id):  # pragma: no cover
        return SubmissionResult(status="sent", environment="sandbox", legal_validity=False)


@pytest.fixture
def flaky(monkeypatch):
    from app.core.config import get_settings

    ADAPTERS["flaky"] = _FlakyAdapter
    monkeypatch.setattr(get_settings(), "einvoice_adapter_co", "flaky")
    yield
    ADAPTERS.pop("flaky", None)


def test_transient_errors_retry_then_fail_with_alert(env, flaky):
    from helpers import confirmed_so, run_outbox, shipped_dispatch, stock_in
    from sqlalchemy import select, update

    from app.core.db import SessionLocal
    from app.modules.kpi.models import Alert
    from app.modules.org.models import IntegrationEvent

    stock_in(env, "A", qty=2, price=10)
    d = shipped_dispatch(env, confirmed_so(env, "A", qty=1))
    a = env.api("admin1")
    inv = a.post("/einvoicing/invoices/from-dispatch", {"dispatch_id": d["id"]})
    a.post(f"/einvoicing/invoices/{inv['id']}/issue")
    for _ in range(8):
        run_outbox()
        with SessionLocal() as db:  # adelanta el reloj del reintento
            db.execute(update(IntegrationEvent).values(next_attempt_at=IntegrationEvent.created_at))
            db.commit()
    with SessionLocal() as db:
        ev = db.scalar(select(IntegrationEvent))
        assert ev.status == "failed" and ev.attempts == 8
        assert db.scalar(select(Alert).where(Alert.source == "integration:einvoice.submit")).severity == "critical"
    inv = a.get(f"/einvoicing/invoices/{inv['id']}")
    assert inv["edoc_status"] == "error" and inv["legal_validity"] is False
    assert _FlakyAdapter.calls == 8

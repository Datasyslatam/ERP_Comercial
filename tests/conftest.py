"""Infraestructura de pruebas: PostgreSQL real (TEST_DATABASE_URL), migraciones Alembic y datos sintéticos.

Cada prueba parte de una base vacía (TRUNCATE de todas las tablas) con permisos y roles sincronizados.
"""
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]


def _load_env_file() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env_file()
TEST_DB = os.environ.get("TEST_DATABASE_URL")
if not TEST_DB:
    raise RuntimeError("Defina TEST_DATABASE_URL (base de datos PostgreSQL exclusiva para pruebas)")
os.environ["DATABASE_URL"] = TEST_DB
os.environ["ENVIRONMENT"] = "test"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["STORAGE_PATH"] = str(ROOT / ".pytest_cache" / "storage")
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_KIB"] = "8192"
os.environ["ARGON2_PARALLELISM"] = "1"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402
from app.core.http import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.accounting.models import Account, BankAccount  # noqa: E402
from app.modules.einvoicing.models import NumberingRange  # noqa: E402
from app.modules.iam.models import Role, UserCompanyRole  # noqa: E402
from app.modules.iam.service import create_user  # noqa: E402
from app.modules.inventory.models import Location, Warehouse  # noqa: E402
from app.modules.masters.models import Item, ItemCategory, Party, PaymentTerm, Tax, UnitOfMeasure  # noqa: E402
from app.modules.masters.validation import nit_check_digit, rif_check_digit  # noqa: E402
from app.modules.org import service as org  # noqa: E402

PASSWORD = "Prueba-Segura-2026!"
TODAY = date.today()


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    with engine.begin() as conn:
        conn.execute(text("drop schema public cascade; create schema public;"))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    os.environ["ALEMBIC_DATABASE_URL"] = TEST_DB
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(migrated_db):
    with engine.begin() as conn:
        tables = conn.execute(text("""select tablename from pg_tables where schemaname = 'public'
                                      and tablename <> 'alembic_version'""")).scalars().all()
        # DELETE con session_replication_role=replica (sin triggers ni FK) es mucho más rápido que TRUNCATE
        # para tablas pequeñas; requiere que el usuario de pruebas sea superusuario de su clúster.
        conn.execute(text("set local session_replication_role = replica"))
        for t in tables:
            conn.execute(text(f'delete from "{t}"'))
    with SessionLocal() as db:
        org.sync_reference_data(db)
        db.commit()
    limiter.reset()
    yield


class Api:
    """Cliente autenticado para un usuario y una empresa."""

    def __init__(self, client: TestClient, email: str, company_id: int | None):
        self.client = client
        r = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        self.tokens = r.json()
        self.headers = {"Authorization": f"Bearer {self.tokens['access_token']}"}
        if company_id:
            self.headers["X-Company-Id"] = str(company_id)

    def _call(self, method, path, expect=None, **kw):
        r = self.client.request(method, "/api/v1" + path, headers=self.headers, **kw)
        if expect is not None:
            assert r.status_code == expect, f"{method} {path} → {r.status_code}: {r.text}"
        return r

    def get(self, path, expect=200, **kw):
        r = self._call("GET", path, expect, **kw)
        return r.json() if expect == 200 else r

    def post(self, path, json=None, expect=None, **kw):
        r = self._call("POST", path, expect, json=json, **kw)
        if expect is None:
            assert r.status_code in (200, 201), f"POST {path} → {r.status_code}: {r.text}"
            return r.json()
        return r

    def put(self, path, json=None, expect=200):
        return self._call("PUT", path, expect, json=json).json()

    def patch(self, path, json=None, expect=200):
        return self._call("PATCH", path, expect, json=json).json()


@pytest.fixture
def client():
    return TestClient(app)


def _user(db, email, company_id, role_code, superadmin=False):
    u = create_user(db, email=email, full_name=email.split("@")[0], password=PASSWORD, is_superadmin=superadmin)
    if role_code:
        role = db.scalar(select(Role).where(Role.code == role_code))
        db.add(UserCompanyRole(user_id=u.id, company_id=company_id, role_id=role.id))
    return u


def build_company(db, country="CO", code="TESTCO", sector="commercial", agent=True, special=False):
    tax_id = "900123456" if country == "CO" else "J12345678"
    dv = nit_check_digit(tax_id) if country == "CO" else rif_check_digit(tax_id)
    c = org.create_company(db, code=code, legal_name=f"Empresa de Pruebas {code} S.A.S.", tax_id=tax_id,
                           check_digit=dv, country_code=country, sector=sector, is_withholding_agent=agent,
                           is_special_taxpayer=special)
    c.email, c.address, c.city = "facturacion@pruebas.datasys.co", "Calle de pruebas 1", "Bogotá"
    db.flush()
    return c


@pytest.fixture
def env(client):
    """Empresa colombiana comercial con usuarios por rol y maestros sintéticos mínimos."""
    with SessionLocal() as db:
        c = build_company(db)
        users = {}
        for name, role in (("admin1", "admin"), ("admin2", "admin"), ("comprador", "comprador"),
                           ("aprobador", "aprobador_compras"), ("almacen", "almacenista"),
                           ("calidad", "inspector_calidad"), ("vendedor", "vendedor"), ("despacho", "despachador"),
                           ("contador", "contador"), ("auditor", "auditor"), ("gerente", "gerente")):
            users[name] = _user(db, f"{name}@pruebas.datasys.co", c.id, role)
        _user(db, "root@pruebas.datasys.co", c.id, None, superadmin=True)
        und = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "UND"))
        iva19 = db.scalar(select(Tax).where(Tax.company_id == c.id, Tax.code == "IVA19"))
        term = db.scalar(select(PaymentTerm).where(PaymentTerm.company_id == c.id, PaymentTerm.code == "30D"))
        cat = ItemCategory(company_id=c.id, code="MERC", name="Mercancía")
        db.add(cat)
        db.flush()
        items = {
            "A": Item(company_id=c.id, sku="ART-A", name="Artículo A", item_type="merchandise", category_id=cat.id,
                      base_uom_id=und.id, sales_tax_id=iva19.id, purchase_tax_id=iva19.id, list_price=Decimal("150"),
                      min_stock=Decimal("5"), max_stock=Decimal("50")),
            "LOT": Item(company_id=c.id, sku="ART-LOT", name="Artículo con lote", item_type="merchandise",
                        category_id=cat.id, base_uom_id=und.id, sales_tax_id=iva19.id, purchase_tax_id=iva19.id,
                        track_lots=True, track_expiry=True, list_price=Decimal("80")),
            "QC": Item(company_id=c.id, sku="ART-QC", name="Artículo con inspección", item_type="raw_material",
                       category_id=cat.id, base_uom_id=und.id, purchase_tax_id=iva19.id, sales_tax_id=iva19.id,
                       requires_inspection=True, track_lots=True, list_price=Decimal("40")),
        }
        db.add_all(items.values())
        customer = Party(company_id=c.id, code="CLI1", legal_name="Cliente de Pruebas S.A.S.", id_type="NIT",
                         tax_id="800200300", check_digit=nit_check_digit("800200300"), is_customer=True,
                         email="cliente@pruebas.datasys.co", address="Cra 1 # 2-3", city="Medellín",
                         payment_term_id=term.id, is_withholding_agent=True)
        supplier = Party(company_id=c.id, code="PRO1", legal_name="Proveedor de Pruebas Ltda.", id_type="NIT",
                         tax_id="830100200", check_digit=nit_check_digit("830100200"), is_supplier=True,
                         payment_term_id=term.id)
        carrier = Party(company_id=c.id, code="TRA1", legal_name="Transportes Prueba", id_type="NIT",
                        tax_id="860500600", check_digit=nit_check_digit("860500600"), is_carrier=True)
        db.add_all([customer, supplier, carrier])
        db.flush()
        rtec = db.scalar(select(Tax).where(Tax.company_id == c.id, Tax.code == "RTEC25"))
        supplier.withholdings = [rtec]
        bank_gl = db.scalar(select(Account).where(Account.company_id == c.id, Account.code == "111005"))
        bank = BankAccount(company_id=c.id, name="Banco pruebas", bank_name="Banco", account_number_masked="****1",
                           currency="COP", gl_account_id=bank_gl.id)
        db.add(bank)
        db.add(NumberingRange(company_id=c.id, doc_type="invoice", prefix="SETP", range_from=990000000,
                              range_to=995000000, next_number=990000000, valid_from=TODAY - timedelta(days=60),
                              valid_to=TODAY + timedelta(days=300), authorization_number="18760000001",
                              technical_key="fc8eac422eba16e22ffd8c6f94b3f40a6e38162c", environment="sandbox"))
        db.add(NumberingRange(company_id=c.id, doc_type="credit_note", prefix="NC", range_from=1, range_to=1000,
                              next_number=1, valid_from=TODAY - timedelta(days=60), valid_to=TODAY + timedelta(days=300),
                              authorization_number="NC-SANDBOX", environment="sandbox"))
        wh = db.scalar(select(Warehouse).where(Warehouse.company_id == c.id))
        locs = {loc.location_type: loc.id for loc in db.scalars(select(Location).where(Location.warehouse_id == wh.id))}
        db.commit()
        data = {
            "company_id": c.id, "site_id": wh.site_id, "warehouse_id": wh.id, "locations": locs,
            "items": {k: v.id for k, v in items.items()}, "customer_id": customer.id, "supplier_id": supplier.id,
            "carrier_id": carrier.id, "bank_account_id": bank.id, "iva19": iva19.id, "category_id": cat.id, "uom_id": und.id,
        }

    class Env(dict):
        def api(self, user: str) -> Api:
            return Api(client, f"{user}@pruebas.datasys.co", self["company_id"])

    e = Env(data)
    e.client = client
    return e

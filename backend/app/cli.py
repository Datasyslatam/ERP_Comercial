"""Comandos de administración.

  python -m app.cli init                                   # permisos, roles, monedas, unidades
  python -m app.cli create-company --code DLCO --name "..." --tax-id 900123456 --dv 7 --country CO
  python -m app.cli create-admin --email admin@empresa.com --name "Admin" --company DLCO   (clave: ERP_ADMIN_PASSWORD o prompt)
  python -m app.cli open-year --company DLCO --year 2027
  python -m app.cli seed-demo --company DLCO              # datos SINTÉTICOS de desarrollo, prefijo DEMO-
"""
import argparse
import getpass
import os
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.audit import register_audit_listener
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.modules.iam.models import Role, UserCompanyRole
from app.modules.iam.service import create_user
from app.modules.org import service as org


def _company(db, code):
    from app.modules.org.models import Company

    c = db.scalar(select(Company).where(Company.code == code))
    if c is None:
        sys.exit(f"Empresa {code} no existe")
    return c


def cmd_init(args):
    with SessionLocal() as db:
        org.sync_reference_data(db)
        db.commit()
    print("Datos de referencia sincronizados")


def cmd_create_company(args):
    from app.modules.masters.validation import validate_tax_id

    validate_tax_id("NIT" if args.country == "CO" else "RIF", args.tax_id, args.dv, args.country)
    with SessionLocal() as db:
        c = org.create_company(db, code=args.code, legal_name=args.name, tax_id=args.tax_id, check_digit=args.dv,
                               country_code=args.country, sector=args.sector,
                               is_withholding_agent=args.withholding_agent, is_special_taxpayer=args.special_taxpayer)
        db.commit()
        print(f"Empresa creada id={c.id} moneda={c.functional_currency}")


def cmd_create_admin(args):
    password = os.environ.get("ERP_ADMIN_PASSWORD") or getpass.getpass("Contraseña del administrador: ")
    with SessionLocal() as db:
        org.sync_reference_data(db)
        user = create_user(db, email=args.email, full_name=args.name, password=password,
                           is_superadmin=args.superadmin)
        if args.company:
            c = _company(db, args.company)
            role = db.scalar(select(Role).where(Role.code == "admin"))
            db.add(UserCompanyRole(user_id=user.id, company_id=c.id, role_id=role.id))
        db.commit()
        print(f"Usuario creado id={user.id}")


def cmd_open_year(args):
    with SessionLocal() as db:
        c = _company(db, args.company)
        org.ensure_periods(db, c.id, args.year)
        db.commit()
    print(f"Periodos {args.year} disponibles")


def cmd_seed_demo(args):
    """Datos sintéticos claramente identificados (prefijo DEMO-). Bloqueado en producción."""
    if get_settings().environment == "production":
        sys.exit("seed-demo no está permitido en producción")
    from app.modules.accounting.models import Account, BankAccount
    from app.modules.einvoicing.models import NumberingRange
    from app.modules.masters.models import Item, ItemCategory, Party, PaymentTerm, Tax, UnitOfMeasure
    from app.modules.org.models import ExchangeRate

    with SessionLocal() as db:
        c = _company(db, args.company)
        und = db.scalar(select(UnitOfMeasure).where(UnitOfMeasure.code == "UND"))
        vat = db.scalar(select(Tax).where(Tax.company_id == c.id, Tax.kind == "vat", Tax.rate > 10))
        term30 = db.scalar(select(PaymentTerm).where(PaymentTerm.company_id == c.id, PaymentTerm.code == "30D"))
        cat = ItemCategory(company_id=c.id, code="DEMO-MERC", name="[DEMO] Mercancía")
        db.add(cat)
        db.flush()
        for i in range(1, 6):
            db.add(Item(company_id=c.id, sku=f"DEMO-{i:03d}", name=f"[DEMO] Producto sintético {i}",
                        item_type="merchandise", category_id=cat.id, base_uom_id=und.id, sales_tax_id=vat.id,
                        purchase_tax_id=vat.id, min_stock=Decimal("10"), max_stock=Decimal("100"),
                        list_price=Decimal("1000") * i, track_lots=(i == 5), track_expiry=(i == 5),
                        requires_inspection=(i == 4)))
        if c.country_code == "CO":
            parties = [("DEMO-C1", "[DEMO] Cliente sintético S.A.S.", "NIT", "900000001", "1", True, False, False),
                       ("DEMO-P1", "[DEMO] Proveedor sintético Ltda.", "NIT", "800000003", "6", False, True, False),
                       ("DEMO-T1", "[DEMO] Transportes sintéticos", "NIT", "830000000", "8", False, False, True)]
        else:
            parties = [("DEMO-C1", "[DEMO] Cliente sintético C.A.", "RIF", "J00000001", "8", True, False, False),
                       ("DEMO-P1", "[DEMO] Proveedor sintético C.A.", "RIF", "J00000002", "6", False, True, False),
                       ("DEMO-T1", "[DEMO] Transportes sintéticos C.A.", "RIF", "J00000003", "4", False, False, True)]
        from app.modules.masters.validation import nit_check_digit, rif_check_digit

        for code, name, idt, tid, _dv, cust, supp, carr in parties:
            dv = nit_check_digit(tid) if idt == "NIT" else rif_check_digit(tid)
            db.add(Party(company_id=c.id, code=code, legal_name=name, id_type=idt, tax_id=tid, check_digit=dv,
                         is_customer=cust, is_supplier=supp, is_carrier=carr, email="demo@example.invalid",
                         address="Dirección sintética 123", city="Ciudad DEMO", country_code=c.country_code,
                         payment_term_id=term30.id))
        bank_gl = db.scalar(select(Account).where(Account.company_id == c.id, Account.is_cash.is_(True),
                                                  Account.is_postable.is_(True)).order_by(Account.code.desc()))
        db.add(BankAccount(company_id=c.id, name="DEMO Banco principal", bank_name="[DEMO] Banco",
                           account_number_masked="****0000", currency=c.functional_currency, gl_account_id=bank_gl.id))
        db.add(NumberingRange(company_id=c.id, doc_type="invoice", prefix="SETT" if c.country_code == "CO" else "A",
                              range_from=1, range_to=5000, next_number=1, valid_from=date.today() - timedelta(days=30),
                              valid_to=date.today() + timedelta(days=365), authorization_number="SANDBOX-0000",
                              technical_key="clave-tecnica-de-pruebas-sandbox", environment="sandbox"))
        db.add(NumberingRange(company_id=c.id, doc_type="credit_note", prefix="NC", range_from=1, range_to=5000,
                              next_number=1, valid_from=date.today() - timedelta(days=30),
                              valid_to=date.today() + timedelta(days=365), authorization_number="SANDBOX-NC",
                              environment="sandbox"))
        if c.country_code == "VE":
            db.add(ExchangeRate(from_currency="USD", to_currency="VES", rate_date=date.today(),
                                rate=Decimal("1"), source="DEMO-sintetica (usar tasa BCV)"))
        db.commit()
    print("Datos DEMO creados (sintéticos, prefijo DEMO-; no usar en producción)")


def main(argv=None):
    register_audit_listener()
    ap = argparse.ArgumentParser(prog="erp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    p = sub.add_parser("create-company")
    p.add_argument("--code", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--tax-id", required=True)
    p.add_argument("--dv")
    p.add_argument("--country", required=True, choices=["CO", "VE"])
    p.add_argument("--sector", default="commercial", choices=["commercial", "manufacturing", "services", "mixed"])
    p.add_argument("--withholding-agent", action="store_true")
    p.add_argument("--special-taxpayer", action="store_true")
    p.set_defaults(fn=cmd_create_company)
    p = sub.add_parser("create-admin")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--company")
    p.add_argument("--superadmin", action="store_true")
    p.set_defaults(fn=cmd_create_admin)
    p = sub.add_parser("open-year")
    p.add_argument("--company", required=True)
    p.add_argument("--year", type=int, required=True)
    p.set_defaults(fn=cmd_open_year)
    p = sub.add_parser("seed-demo")
    p.add_argument("--company", required=True)
    p.set_defaults(fn=cmd_seed_demo)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()

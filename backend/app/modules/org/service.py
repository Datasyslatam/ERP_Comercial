"""Inicialización del sistema y alta de empresas a partir del paquete de su jurisdicción."""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleViolation, Conflict
from app.core.permissions import PERMISSIONS, ROLES
from app.modules.accounting.models import Account, FiscalPeriod, PostingAccount
from app.modules.iam.models import Permission, Role
from app.modules.inventory.models import Location, Warehouse
from app.modules.masters.models import PaymentTerm, Tax, UnitOfMeasure
from app.modules.org.jurisdictions import CURRENCIES, PACKS, UOMS
from app.modules.org.models import Company, CompanyModule, Currency, Site

TOGGLEABLE_MODULES = ("purchasing", "inventory", "quality", "sales", "logistics", "operations", "einvoicing")
SECTOR_DISABLED = {"commercial": ("operations",), "manufacturing": (), "services": ("logistics",), "mixed": ()}


def sync_reference_data(db: Session) -> None:
    """Idempotente: permisos, roles del sistema, monedas y unidades de medida."""
    perms = {p.code: p for p in db.scalars(select(Permission))}
    for code, module, desc in PERMISSIONS:
        if code not in perms:
            perms[code] = Permission(code=code, module=module, description=desc)
            db.add(perms[code])
        elif perms[code].description != desc:
            perms[code].description = desc
    db.flush()
    for code, (name, codes) in ROLES.items():
        role = db.scalar(select(Role).where(Role.code == code, Role.company_id.is_(None)))
        if role is None:
            role = Role(code=code, name=name, is_system=True)
            db.add(role)
        if role.is_system:
            role.permissions = [perms[c] for c in codes]
    for code, name, decimals in CURRENCIES:
        if db.get(Currency, code) is None:
            db.add(Currency(code=code, name=name, decimals=decimals))
    existing = set(db.scalars(select(UnitOfMeasure.code)))
    for code, name, cat in UOMS:
        if code not in existing:
            db.add(UnitOfMeasure(code=code, name=name, category=cat))
    db.flush()


def ensure_periods(db: Session, company_id: int, year: int) -> None:
    have = set(db.scalars(select(FiscalPeriod.month).where(FiscalPeriod.company_id == company_id,
                                                           FiscalPeriod.year == year)))
    for m in range(1, 13):
        if m in have:
            continue
        start = date(year, m, 1)
        end = date(year + (m == 12), m % 12 + 1, 1)
        db.add(FiscalPeriod(company_id=company_id, year=year, month=m, start_date=start,
                            end_date=end - timedelta(days=1)))
    db.flush()


def create_company(db: Session, *, code: str, legal_name: str, tax_id: str, country_code: str,
                   check_digit: str | None = None, sector: str = "commercial", site_code: str = "PRINCIPAL",
                   site_name: str = "Sede principal", is_withholding_agent: bool = False,
                   is_special_taxpayer: bool = False, year: int | None = None) -> Company:
    country_code = country_code.upper()
    if country_code not in PACKS:
        raise BusinessRuleViolation(f"País no soportado: {country_code}")
    if sector not in SECTOR_DISABLED:
        raise BusinessRuleViolation(f"Sector desconocido: {sector}")
    if db.scalar(select(Company).where(Company.code == code)):
        raise Conflict(f"Ya existe la empresa {code}")
    pack = PACKS[country_code]
    sync_reference_data(db)
    company = Company(code=code, legal_name=legal_name, tax_id=tax_id, tax_id_check_digit=check_digit,
                      country_code=country_code, functional_currency=pack["currency"],
                      is_withholding_agent=is_withholding_agent, is_special_taxpayer=is_special_taxpayer)
    db.add(company)
    db.flush()

    for mod in TOGGLEABLE_MODULES:
        db.add(CompanyModule(company_id=company.id, module_code=mod,
                             enabled=mod not in SECTOR_DISABLED[sector]))

    by_code: dict[str, Account] = {}
    for acc_code, name, acc_type, postable, opts in pack["accounts"]:
        parent = None
        for other in sorted(by_code, key=len, reverse=True):
            if acc_code.startswith(other) and acc_code != other:
                parent = by_code[other]
                break
        normal = opts.get("normal") or ("debit" if acc_type in ("asset", "expense", "cost") else "credit")
        acc = Account(company_id=company.id, code=acc_code, name=name, account_type=acc_type, normal_balance=normal,
                      parent_id=parent.id if parent else None, is_postable=postable,
                      requires_party=opts.get("requires_party", False), is_cash=opts.get("is_cash", False),
                      cash_flow_activity="operating" if opts.get("is_cash") else None)
        db.add(acc)
        db.flush()
        by_code[acc_code] = acc
    for key, acc_code in pack["posting"].items():
        db.add(PostingAccount(company_id=company.id, key=key, account_id=by_code[acc_code].id))
    for t_code, name, kind, rate, base, applies, sales_acc, purch_acc, ecode in pack["taxes"]:
        db.add(Tax(company_id=company.id, code=t_code, name=name, kind=kind, rate=Decimal(rate), base=base,
                   applies_to=applies, electronic_code=ecode,
                   sales_account_id=by_code[sales_acc].id if sales_acc else None,
                   purchase_account_id=by_code[purch_acc].id if purch_acc else None))
    for pt_code, pt_name, days in (("CONTADO", "Contado", 0), ("30D", "Crédito 30 días", 30),
                                   ("60D", "Crédito 60 días", 60)):
        db.add(PaymentTerm(company_id=company.id, code=pt_code, name=pt_name, days=days))

    site = Site(company_id=company.id, code=site_code, name=site_name)
    db.add(site)
    db.flush()
    wh = Warehouse(company_id=company.id, site_id=site.id, code="BOD01", name="Bodega principal")
    db.add(wh)
    db.flush()
    for loc_code, loc_name, loc_type in (("REC", "Muelle de recepción", "receiving"),
                                         ("CAL", "Cuarentena / calidad", "quality"),
                                         ("A-01", "Estantería A-01", "storage"),
                                         ("DES", "Zona de despacho", "dispatch"),
                                         ("BAJ", "Bajas y mermas", "scrap")):
        db.add(Location(company_id=company.id, warehouse_id=wh.id, code=loc_code, name=loc_name,
                        location_type=loc_type))
    ensure_periods(db, company.id, year or date.today().year)
    db.flush()
    return company

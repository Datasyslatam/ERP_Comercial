"""Endpoints de datos maestros y parametrización (generados con la fábrica CRUD + operaciones específicas)."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import crud_router, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require
from app.core.errors import BusinessRuleViolation, NotFound
from app.modules.accounting.models import POSTING_KEYS, Account, BankAccount, PostingAccount
from app.modules.iam.models import ApprovalLimit, Role
from app.modules.inventory.models import Location, Warehouse
from app.modules.logistics.models import DeliveryRoute
from app.modules.masters.models import (
    Item,
    ItemCategory,
    Party,
    PartyWithholding,
    PaymentTerm,
    Tax,
    UnitOfMeasure,
    UomConversion,
)
from app.modules.org import service as org_service
from app.modules.org.models import (
    BusinessUnit,
    Company,
    CompanyModule,
    CostCenter,
    DocumentSequence,
    ExchangeRate,
    Site,
)

router = APIRouter()


def _validate_party(db: Session, p: Principal, obj: Party, data: dict) -> None:
    from app.modules.masters.validation import validate_tax_id

    validate_tax_id(obj.id_type, obj.tax_id, obj.check_digit, obj.country_code)


def _validate_item(db: Session, p: Principal, obj: Item, data: dict) -> None:
    if obj.max_stock and obj.min_stock and obj.max_stock < obj.min_stock:
        raise BusinessRuleViolation("La existencia máxima no puede ser menor que la mínima")
    if obj.track_serials and not obj.track_lots:
        obj.track_lots = True  # las series se gestionan como lotes de cantidad unitaria


def _validate_account(db: Session, p: Principal, obj: Account, data: dict) -> None:
    expected = "debit" if obj.account_type in ("asset", "expense", "cost") else "credit"
    if obj.normal_balance is None:
        obj.normal_balance = expected


CRUDS = [
    (Site, "/sites", "Sedes", "admin.company.read", "admin.company.admin", None, ("code", "name")),
    (BusinessUnit, "/business-units", "Unidades de negocio", "admin.company.read", "admin.company.admin", None,
     ("code", "name")),
    (CostCenter, "/cost-centers", "Centros de costo", "masters.config.read", "masters.config.admin", None,
     ("code", "name")),
    (Warehouse, "/warehouses", "Bodegas", "inventory.config.read", "inventory.config.admin", None, ("code", "name")),
    (Location, "/locations", "Ubicaciones", "inventory.config.read", "inventory.config.admin", None,
     ("code", "name", "zone")),
    (PaymentTerm, "/payment-terms", "Condiciones de pago", "masters.config.read", "masters.config.admin", None,
     ("code", "name")),
    (Tax, "/taxes", "Impuestos y retenciones", "masters.taxes.read", "masters.taxes.admin", None, ("code", "name")),
    (ItemCategory, "/item-categories", "Categorías de artículos", "masters.items.read", "masters.items.create", None,
     ("code", "name")),
    (Item, "/items", "Artículos", "masters.items.read", "masters.items.create", "masters.items.export",
     ("sku", "name", "barcode")),
    (Party, "/parties", "Terceros", "masters.parties.read", "masters.parties.create", "masters.parties.export",
     ("code", "legal_name", "trade_name", "tax_id")),
    (Account, "/accounts", "Plan de cuentas", "accounting.accounts.read", "accounting.accounts.admin",
     "accounting.reports.export", ("code", "name")),
    (BankAccount, "/bank-accounts", "Cuentas bancarias", "accounting.bank.read", "accounting.accounts.admin", None,
     ("name", "bank_name")),
    (DeliveryRoute, "/routes", "Rutas de entrega", "logistics.route.read", "logistics.route.admin", None,
     ("code", "name")),
    (DocumentSequence, "/document-sequences", "Secuencias de documentos", "masters.config.read",
     "masters.config.admin", None, ("doc_type", "prefix")),
]
_HOOKS = {Party: _validate_party, Item: _validate_item, Account: _validate_account}

for model, prefix, tag, rp, wp, ep, search in CRUDS:
    router.include_router(crud_router(model, prefix=prefix, tag=tag, read_perm=rp, write_perm=wp, export_perm=ep,
                                      search_fields=search, before_save=_HOOKS.get(model),
                                      order_by="code" if hasattr(model, "code") else "id"))


# ------------------------------------------------------------------ unidades y conversiones (globales)
class UomIn(BaseModel):
    code: str = Field(max_length=10)
    name: str = Field(max_length=60)
    category: str = Field(pattern="^(unit|weight|volume|length|time|area)$")


@router.get("/uoms", tags=["Unidades de medida"])
def list_uoms(_: Principal = Depends(require("masters.items.read")), db: Session = Depends(get_db)):
    return [{"id": u.id, "code": u.code, "name": u.name, "category": u.category}
            for u in db.scalars(select(UnitOfMeasure).order_by(UnitOfMeasure.code))]


@router.post("/uoms", tags=["Unidades de medida"], status_code=201)
def create_uom(body: UomIn, _: Principal = Depends(require("masters.config.admin")), db: Session = Depends(get_db)):
    u = UnitOfMeasure(**body.model_dump())
    db.add(u)
    db.commit()
    return {"id": u.id, **body.model_dump()}


class ConversionIn(BaseModel):
    item_id: int | None = None
    from_uom_id: int
    to_uom_id: int
    factor: Decimal = Field(gt=0)


@router.post("/uom-conversions", tags=["Unidades de medida"], status_code=201)
def create_conversion(body: ConversionIn, p: Principal = Depends(require("masters.items.create")),
                      db: Session = Depends(get_db)):
    if body.item_id:
        get_owned(db, Item, body.item_id, p.company_id)
    c = UomConversion(**body.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.get("/uom-conversions/convert", tags=["Unidades de medida"])
def convert(item_id: int, qty: Decimal, from_uom_id: int, to_uom_id: int,
            p: Principal = Depends(require("masters.items.read")), db: Session = Depends(get_db)):
    from app.modules.masters.service import convert_qty

    get_owned(db, Item, item_id, p.company_id)
    return {"quantity": convert_qty(db, item_id, qty, from_uom_id, to_uom_id)}


# ------------------------------------------------------------------ retenciones por tercero
class WithholdingsIn(BaseModel):
    tax_ids: list[int]


@router.put("/parties/{party_id}/withholdings", tags=["Terceros"])
def set_withholdings(party_id: int, body: WithholdingsIn, p: Principal = Depends(require("masters.parties.create")),
                     db: Session = Depends(get_db)):
    party = get_owned(db, Party, party_id, p.company_id)
    for tid in body.tax_ids:
        tax = get_owned(db, Tax, tid, p.company_id)
        if not tax.is_withholding and tax.kind != "igtf":
            raise BusinessRuleViolation(f"El impuesto {tax.code} no es una retención")
    db.execute(delete(PartyWithholding).where(PartyWithholding.party_id == party.id))
    for tid in body.tax_ids:
        db.add(PartyWithholding(party_id=party.id, tax_id=tid))
    db.commit()
    return {"party_id": party.id, "tax_ids": body.tax_ids}


# ------------------------------------------------------------------ empresa, módulos y políticas
class CompanySettingsIn(BaseModel):
    settings: dict


@router.get("/company", tags=["Empresa"])
def get_company(p: Principal = Depends(require("admin.company.read")), db: Session = Depends(get_db)):
    c = p.company
    mods = {m.module_code: m.enabled for m in db.scalars(select(CompanyModule).where(CompanyModule.company_id == c.id))}
    return {"id": c.id, "code": c.code, "legal_name": c.legal_name, "tax_id": c.tax_id, "country": c.country_code,
            "functional_currency": c.functional_currency, "settings": c.settings, "modules": mods}


@router.patch("/company/settings", tags=["Empresa"])
def update_settings(body: CompanySettingsIn, p: Principal = Depends(require("admin.company.admin")),
                    db: Session = Depends(get_db)):
    from app.modules.org.models import DEFAULT_COMPANY_SETTINGS

    unknown = set(body.settings) - set(DEFAULT_COMPANY_SETTINGS)
    if unknown:
        raise BusinessRuleViolation(f"Parámetros desconocidos: {sorted(unknown)}")
    company = db.get(Company, p.company_id)
    company.settings = {**(company.settings or {}), **body.settings}
    log_action(db, "admin", "companies", company.id, f"Cambio de políticas: {sorted(body.settings)}")
    db.commit()
    return company.settings


class ModuleToggleIn(BaseModel):
    enabled: bool


@router.put("/company/modules/{module_code}", tags=["Empresa"])
def toggle_module(module_code: str, body: ModuleToggleIn, p: Principal = Depends(require("admin.company.admin")),
                  db: Session = Depends(get_db)):
    if module_code not in org_service.TOGGLEABLE_MODULES:
        raise BusinessRuleViolation(f"Módulo no configurable: {module_code}")
    row = db.get(CompanyModule, (p.company_id, module_code)) or CompanyModule(company_id=p.company_id,
                                                                              module_code=module_code)
    row.enabled = body.enabled
    db.add(row)
    log_action(db, "admin", "company_modules", module_code, f"{'Activado' if body.enabled else 'Desactivado'}")
    db.commit()
    return {"module": module_code, "enabled": body.enabled}


# ------------------------------------------------------------------ tasas de cambio
class RateIn(BaseModel):
    from_currency: str = Field(min_length=3, max_length=3)
    to_currency: str = Field(min_length=3, max_length=3)
    rate_date: date
    rate: Decimal = Field(gt=0)
    source: str = Field(max_length=40)


@router.get("/exchange-rates", tags=["Monedas"])
def list_rates(from_currency: str | None = None, to_currency: str | None = None,
               _: Principal = Depends(require("masters.config.read")), db: Session = Depends(get_db)):
    stmt = select(ExchangeRate).order_by(ExchangeRate.rate_date.desc()).limit(200)
    if from_currency:
        stmt = stmt.where(ExchangeRate.from_currency == from_currency)
    if to_currency:
        stmt = stmt.where(ExchangeRate.to_currency == to_currency)
    return [{"id": r.id, "from": r.from_currency, "to": r.to_currency, "date": r.rate_date, "rate": r.rate,
             "source": r.source} for r in db.scalars(stmt)]


@router.post("/exchange-rates", tags=["Monedas"], status_code=201)
def create_rate(body: RateIn, _: Principal = Depends(require("masters.config.admin")), db: Session = Depends(get_db)):
    r = ExchangeRate(**body.model_dump())
    db.add(r)
    db.commit()
    return {"id": r.id}


# ------------------------------------------------------------------ parametrización contable
class PostingAccountIn(BaseModel):
    key: str
    account_id: int


@router.get("/posting-accounts", tags=["Plan de cuentas"])
def list_posting(p: Principal = Depends(require("accounting.accounts.read")), db: Session = Depends(get_db)):
    rows = {r.key: r.account_id for r in db.scalars(select(PostingAccount).where(PostingAccount.company_id == p.company_id))}
    return [{"key": k, "account_id": rows.get(k)} for k in POSTING_KEYS]


@router.put("/posting-accounts", tags=["Plan de cuentas"])
def set_posting(body: PostingAccountIn, p: Principal = Depends(require("accounting.accounts.admin")),
                db: Session = Depends(get_db)):
    if body.key not in POSTING_KEYS:
        raise BusinessRuleViolation("Clave de parametrización inválida")
    acc = get_owned(db, Account, body.account_id, p.company_id)
    if not acc.is_postable:
        raise BusinessRuleViolation("La cuenta debe ser de movimiento")
    row = db.scalar(select(PostingAccount).where(PostingAccount.company_id == p.company_id,
                                                 PostingAccount.key == body.key))
    if row is None:
        row = PostingAccount(company_id=p.company_id, key=body.key, account_id=acc.id)
        db.add(row)
    else:
        row.account_id = acc.id
    db.commit()
    return {"key": body.key, "account_id": acc.id}


# ------------------------------------------------------------------ límites de aprobación
class ApprovalLimitIn(BaseModel):
    role_code: str
    document_type: str = Field(pattern="^(purchase_requisition|purchase_order|inventory_adjustment|payment)$")
    max_amount: Decimal = Field(ge=0)


@router.get("/approval-limits", tags=["Empresa"])
def list_limits(p: Principal = Depends(require("admin.company.read")), db: Session = Depends(get_db)):
    rows = db.execute(select(ApprovalLimit, Role).join(Role, Role.id == ApprovalLimit.role_id)
                      .where(ApprovalLimit.company_id == p.company_id)).all()
    return [{"id": a.id, "role": r.code, "document_type": a.document_type, "max_amount": a.max_amount}
            for a, r in rows]


@router.put("/approval-limits", tags=["Empresa"])
def set_limit(body: ApprovalLimitIn, p: Principal = Depends(require("admin.company.admin")),
              db: Session = Depends(get_db)):
    role = db.scalar(select(Role).where(Role.code == body.role_code))
    if role is None:
        raise NotFound("Rol inexistente")
    row = db.scalar(select(ApprovalLimit).where(ApprovalLimit.company_id == p.company_id,
                                                ApprovalLimit.role_id == role.id,
                                                ApprovalLimit.document_type == body.document_type))
    if row is None:
        row = ApprovalLimit(company_id=p.company_id, role_id=role.id, document_type=body.document_type,
                            max_amount=body.max_amount)
        db.add(row)
    else:
        row.max_amount = body.max_amount
    log_action(db, "admin", "approval_limits", role.code, f"{body.document_type} <= {body.max_amount}")
    db.commit()
    return {"role": role.code, "document_type": body.document_type, "max_amount": body.max_amount}

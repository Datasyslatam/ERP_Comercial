from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import check_company_refs, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.errors import BusinessRuleViolation
from app.core.serialize import paginate, to_dict
from app.modules.quality import service as svc
from app.modules.quality.models import (
    Inspection,
    InspectionCharacteristic,
    InspectionPlan,
    NonConformity,
)

router = APIRouter(prefix="/quality", tags=["Calidad"], dependencies=[Depends(require_module("quality"))])


class CharacteristicIn(BaseModel):
    name: str = Field(max_length=120)
    kind: str = Field(pattern="^(numeric|boolean|text)$")
    target: Decimal | None = None
    lower_limit: Decimal | None = None
    upper_limit: Decimal | None = None
    unit: str | None = Field(default=None, max_length=20)
    acceptance_criteria: str | None = Field(default=None, max_length=255)
    is_critical: bool = False


class PlanIn(BaseModel):
    code: str = Field(max_length=30)
    name: str = Field(max_length=200)
    stage: str = Field(pattern="^(receiving|in_process|final|dispatch)$")
    item_id: int | None = None
    category_id: int | None = None
    sampling_rule: str | None = Field(default=None, max_length=255)
    characteristics: list[CharacteristicIn] = Field(min_length=1)


class InspectionIn(BaseModel):
    stage: str = Field(pattern="^(in_process|final|dispatch)$")
    item_id: int
    lot_id: int | None = None
    source_type: str = Field(max_length=40)
    source_id: int
    quantity: Decimal = Field(gt=0)
    due_date: date | None = None


class ResultIn(BaseModel):
    characteristic_id: int | None = None
    name: str | None = None
    numeric_value: Decimal | None = None
    bool_value: bool | None = None
    text_value: str | None = Field(default=None, max_length=255)
    is_conforming: bool | None = None


class InspectionResultIn(BaseModel):
    qty_accepted: Decimal = Field(ge=0)
    qty_rejected: Decimal = Field(ge=0)
    results: list[ResultIn] = []
    notes: str | None = Field(default=None, max_length=2000)
    deviation_approved: bool = False
    nc_description: str | None = Field(default=None, max_length=2000)
    nc_category: str | None = Field(default=None, max_length=60)


class NcIn(BaseModel):
    source: str = Field(pattern="^(customer|internal|supplier|delivery|production)$")
    description: str = Field(min_length=5, max_length=4000)
    severity: str = Field(default="minor", pattern="^(minor|major|critical)$")
    category: str | None = Field(default=None, max_length=60)
    item_id: int | None = None
    lot_id: int | None = None
    supplier_id: int | None = None
    customer_id: int | None = None
    quantity_affected: Decimal = Field(default=Decimal("0"), ge=0)
    cost_impact: Decimal = Field(default=Decimal("0"), ge=0)
    disposition: str | None = Field(default=None, pattern="^(rework|scrap|return_to_supplier|use_as_is)$")
    responsible_id: int | None = None


class NcAdvanceIn(BaseModel):
    to_status: str = Field(pattern="^(analysis|action|verification|closed)$")
    root_cause: str | None = Field(default=None, max_length=4000)
    root_cause_method: str | None = Field(default=None, max_length=20)


class ActionIn(BaseModel):
    action_type: str = Field(pattern="^(containment|corrective|preventive)$")
    description: str = Field(min_length=5, max_length=4000)
    responsible_id: int | None = None
    due_date: date | None = None


class ActionStatusIn(BaseModel):
    status: str = Field(pattern="^(done|verified|open|cancelled)$")
    notes: str | None = Field(default=None, max_length=2000)


class LotStatusIn(BaseModel):
    status: str = Field(pattern="^(released|blocked|quarantine)$")
    reason: str = Field(min_length=5, max_length=255)


@router.get("/plans")
def list_plans(p: Principal = Depends(require("quality.plan.read")), db: Session = Depends(get_db)):
    return [to_dict(x, "characteristics") for x in db.scalars(
        select(InspectionPlan).where(InspectionPlan.company_id == p.company_id).order_by(InspectionPlan.code))]


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, p: Principal = Depends(require("quality.plan.admin")), db: Session = Depends(get_db)):
    data = body.model_dump()
    chars = data.pop("characteristics")
    check_company_refs(db, InspectionPlan, p.company_id, data)
    for c in chars:
        if c["kind"] == "numeric" and c["lower_limit"] is None and c["upper_limit"] is None:
            raise BusinessRuleViolation(f"'{c['name']}' numérica requiere al menos un límite de tolerancia")
    plan = InspectionPlan(company_id=p.company_id, **data)
    plan.characteristics = [InspectionCharacteristic(**c) for c in chars]
    db.add(plan)
    db.commit()
    return to_dict(plan, "characteristics")


@router.get("/inspections")
def list_inspections(status: str | None = None, stage: str | None = None, supplier_id: int | None = None,
                     limit: int = Query(50, le=500), offset: int = 0,
                     p: Principal = Depends(require("quality.inspection.read")), db: Session = Depends(get_db)):
    stmt = select(Inspection).where(Inspection.company_id == p.company_id)
    for col, val in ((Inspection.status, status), (Inspection.stage, stage), (Inspection.supplier_id, supplier_id)):
        if val is not None:
            stmt = stmt.where(col == val)
    return paginate(db, stmt.order_by(Inspection.id.desc()), limit, offset, "results")


@router.get("/inspections/{insp_id}")
def get_inspection(insp_id: int, p: Principal = Depends(require("quality.inspection.read")),
                   db: Session = Depends(get_db)):
    insp = get_owned(db, Inspection, insp_id, p.company_id)
    out = to_dict(insp, "results")
    out["plan"] = to_dict(db.get(InspectionPlan, insp.plan_id), "characteristics") if insp.plan_id else None
    return out


@router.post("/inspections", status_code=201)
def create_inspection(body: InspectionIn, p: Principal = Depends(require("quality.inspection.create")),
                      db: Session = Depends(get_db)):
    insp = svc.create_inspection(db, p, body.model_dump())
    db.commit()
    return to_dict(insp)


@router.post("/inspections/{insp_id}/result")
def record_result(insp_id: int, body: InspectionResultIn,
                  p: Principal = Depends(require("quality.inspection.approve")), db: Session = Depends(get_db)):
    insp = svc.record_result(db, p, insp_id, body.model_dump())
    db.commit()
    return to_dict(insp, "results")


@router.post("/lots/{lot_id}/status")
def lot_status(lot_id: int, body: LotStatusIn, p: Principal = Depends(require("quality.inspection.approve")),
               db: Session = Depends(get_db)):
    lot = svc.set_lot_status(db, p, lot_id, body.status, body.reason)
    db.commit()
    return to_dict(lot)


@router.get("/nonconformities")
def list_ncs(status: str | None = None, supplier_id: int | None = None, item_id: int | None = None,
             limit: int = Query(50, le=500), offset: int = 0,
             p: Principal = Depends(require("quality.nonconformity.read")), db: Session = Depends(get_db)):
    stmt = select(NonConformity).where(NonConformity.company_id == p.company_id)
    for col, val in ((NonConformity.status, status), (NonConformity.supplier_id, supplier_id),
                     (NonConformity.item_id, item_id)):
        if val is not None:
            stmt = stmt.where(col == val)
    return paginate(db, stmt.order_by(NonConformity.id.desc()), limit, offset, "actions")


@router.post("/nonconformities", status_code=201)
def create_nc(body: NcIn, p: Principal = Depends(require("quality.nonconformity.create")),
              db: Session = Depends(get_db)):
    data = body.model_dump()
    check_company_refs(db, NonConformity, p.company_id, data)
    nc = svc.raise_nc(db, p, **data)
    db.commit()
    return to_dict(nc, "actions")


@router.post("/nonconformities/{nc_id}/advance")
def advance_nc(nc_id: int, body: NcAdvanceIn, p: Principal = Depends(require("quality.nonconformity.approve")),
               db: Session = Depends(get_db)):
    nc = svc.advance_nc(db, p, nc_id, body.to_status, body.model_dump())
    db.commit()
    return to_dict(nc, "actions")


@router.post("/nonconformities/{nc_id}/actions", status_code=201)
def add_action(nc_id: int, body: ActionIn, p: Principal = Depends(require("quality.nonconformity.create")),
               db: Session = Depends(get_db)):
    act = svc.add_action(db, p, nc_id, body.model_dump())
    db.commit()
    return to_dict(act)


@router.post("/actions/{action_id}/status")
def action_status(action_id: int, body: ActionStatusIn,
                  p: Principal = Depends(require("quality.nonconformity.approve")), db: Session = Depends(get_db)):
    act = svc.update_action(db, p, action_id, body.status, body.notes)
    db.commit()
    return to_dict(act)


@router.get("/history")
def history(item_id: int | None = None, supplier_id: int | None = None, lot_id: int | None = None,
            p: Principal = Depends(require("quality.inspection.read")), db: Session = Depends(get_db)):
    """Historial de calidad por proveedor, lote o producto (inspecciones y no conformidades)."""
    if not (item_id or supplier_id or lot_id):
        raise BusinessRuleViolation("Indique producto, proveedor o lote")
    ins = select(Inspection).where(Inspection.company_id == p.company_id)
    ncs = select(NonConformity).where(NonConformity.company_id == p.company_id)
    if item_id:
        ins, ncs = ins.where(Inspection.item_id == item_id), ncs.where(NonConformity.item_id == item_id)
    if supplier_id:
        ins, ncs = ins.where(Inspection.supplier_id == supplier_id), ncs.where(NonConformity.supplier_id == supplier_id)
    if lot_id:
        ins, ncs = ins.where(Inspection.lot_id == lot_id), ncs.where(NonConformity.lot_id == lot_id)
    return {"inspections": [to_dict(x) for x in db.scalars(ins.order_by(Inspection.id.desc()).limit(200))],
            "nonconformities": [to_dict(x, "actions") for x in db.scalars(ncs.order_by(NonConformity.id.desc()).limit(200))]}

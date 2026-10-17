from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import check_company_refs, get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.schemas import QtyField
from app.core.serialize import paginate, to_dict
from app.modules.operations import service as svc
from app.modules.operations.models import BillOfMaterials, BomLine, WorkOrder

router = APIRouter(prefix="/operations", tags=["Operaciones y producción"],
                   dependencies=[Depends(require_module("operations"))])


class BomLineIn(BaseModel):
    component_item_id: int
    quantity: Decimal = QtyField()
    scrap_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class BomIn(BaseModel):
    code: str = Field(max_length=30)
    item_id: int
    base_quantity: Decimal = QtyField(default=Decimal("1"))
    lines: list[BomLineIn] = Field(min_length=1)


class MaterialIn(BaseModel):
    item_id: int
    planned_qty: Decimal = QtyField()


class WorkOrderIn(BaseModel):
    wo_type: str = Field(pattern="^(production|service|maintenance)$")
    site_id: int
    item_id: int | None = None
    bom_id: int | None = None
    customer_id: int | None = None
    project_name: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    deliverables: str | None = Field(default=None, max_length=4000)
    production_location_id: int | None = None
    output_location_id: int | None = None
    planned_qty: Decimal = Field(default=Decimal("0"), ge=0)
    planned_hours: Decimal = Field(default=Decimal("0"), ge=0)
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    planned_start: date | None = None
    planned_end: date | None = None
    responsible_id: int | None = None
    cost_center_id: int | None = None
    materials: list[MaterialIn] | None = None


class IssueIn(BaseModel):
    item_id: int
    location_id: int
    quantity: Decimal = QtyField()
    lot_id: int | None = None


class IssuesIn(BaseModel):
    issues: list[IssueIn] = Field(min_length=1)


class TimeIn(BaseModel):
    log_date: date
    resource_name: str = Field(max_length=120)
    user_id: int | None = None
    activity: str = Field(max_length=200)
    hours: Decimal = Field(gt=0, le=24)
    cost_per_hour: Decimal = Field(default=Decimal("0"), ge=0)


class OutputIn(BaseModel):
    good_qty: Decimal = Field(ge=0)
    scrap_qty: Decimal = Field(default=Decimal("0"), ge=0)
    rework_qty: Decimal = Field(default=Decimal("0"), ge=0)
    lot_number: str | None = Field(default=None, max_length=60)
    expiry_date: date | None = None
    complete: bool = False


class IncidentIn(BaseModel):
    incident_type: str = Field(max_length=30)
    description: str = Field(min_length=5, max_length=2000)
    downtime_minutes: int = Field(default=0, ge=0)


class CompleteIn(BaseModel):
    progress_pct: Decimal | None = Field(default=None, ge=0, le=100)


@router.get("/boms")
def list_boms(p: Principal = Depends(require("operations.work_order.read")), db: Session = Depends(get_db)):
    return [to_dict(b, "lines") for b in db.scalars(select(BillOfMaterials).where(
        BillOfMaterials.company_id == p.company_id).order_by(BillOfMaterials.code))]


@router.post("/boms", status_code=201)
def create_bom(body: BomIn, p: Principal = Depends(require("operations.work_order.approve")),
               db: Session = Depends(get_db)):
    data = body.model_dump()
    lines = data.pop("lines")
    check_company_refs(db, BillOfMaterials, p.company_id, data)
    bom = BillOfMaterials(company_id=p.company_id, **data)
    for ln in lines:
        check_company_refs(db, BomLine, p.company_id, ln)
        bom.lines.append(BomLine(**ln))
    db.add(bom)
    db.commit()
    return to_dict(bom, "lines")


@router.get("/work-orders")
def list_work_orders(status: str | None = None, wo_type: str | None = None, late: bool = False,
                     limit: int = Query(50, le=500), offset: int = 0,
                     p: Principal = Depends(require("operations.work_order.read")), db: Session = Depends(get_db)):
    stmt = select(WorkOrder).where(WorkOrder.company_id == p.company_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if wo_type:
        stmt = stmt.where(WorkOrder.wo_type == wo_type)
    if late:
        stmt = stmt.where(WorkOrder.status.in_(("released", "in_progress")), WorkOrder.planned_end < date.today())
    return paginate(db, stmt.order_by(WorkOrder.id.desc()), limit, offset)


@router.get("/work-orders/{wo_id}")
def get_work_order(wo_id: int, p: Principal = Depends(require("operations.work_order.read")),
                   db: Session = Depends(get_db)):
    wo = get_owned(db, WorkOrder, wo_id, p.company_id)
    return {**to_dict(wo, "materials", "time_logs", "incidents"), "summary": svc.summary(wo)}


@router.post("/work-orders", status_code=201)
def create_work_order(body: WorkOrderIn, p: Principal = Depends(require("operations.work_order.create")),
                      db: Session = Depends(get_db)):
    wo = svc.create_work_order(db, p, body.model_dump())
    db.commit()
    return to_dict(wo, "materials")


@router.post("/work-orders/{wo_id}/release")
def release(wo_id: int, p: Principal = Depends(require("operations.work_order.approve")),
            db: Session = Depends(get_db)):
    wo = svc.release(db, p, wo_id)
    db.commit()
    return to_dict(wo, "materials")


@router.post("/work-orders/{wo_id}/issues")
def issue(wo_id: int, body: IssuesIn, p: Principal = Depends(require("operations.work_order.post")),
          db: Session = Depends(get_db)):
    wo = svc.issue_materials(db, p, wo_id, [x.model_dump() for x in body.issues])
    db.commit()
    return to_dict(wo, "materials")


@router.post("/work-orders/{wo_id}/time-logs", status_code=201)
def time_log(wo_id: int, body: TimeIn, p: Principal = Depends(require("operations.work_order.create")),
             db: Session = Depends(get_db)):
    tl = svc.log_time(db, p, wo_id, body.model_dump())
    db.commit()
    return to_dict(tl)


@router.post("/work-orders/{wo_id}/output")
def output(wo_id: int, body: OutputIn, p: Principal = Depends(require("operations.work_order.post")),
           db: Session = Depends(get_db)):
    wo = svc.report_output(db, p, wo_id, body.model_dump())
    db.commit()
    return {**to_dict(wo), "summary": svc.summary(wo)}


@router.post("/work-orders/{wo_id}/incidents", status_code=201)
def incident(wo_id: int, body: IncidentIn, p: Principal = Depends(require("operations.work_order.create")),
             db: Session = Depends(get_db)):
    inc = svc.report_incident(db, p, wo_id, body.model_dump())
    db.commit()
    return to_dict(inc)


@router.post("/work-orders/{wo_id}/complete")
def complete(wo_id: int, body: CompleteIn, p: Principal = Depends(require("operations.work_order.approve")),
             db: Session = Depends(get_db)):
    wo = svc.complete(db, p, wo_id, body.progress_pct)
    db.commit()
    return {**to_dict(wo), "summary": svc.summary(wo)}


@router.post("/work-orders/{wo_id}/close")
def close(wo_id: int, p: Principal = Depends(require("operations.work_order.approve")),
          db: Session = Depends(get_db)):
    wo = svc.close(db, p, wo_id)
    db.commit()
    return {**to_dict(wo), "summary": svc.summary(wo)}

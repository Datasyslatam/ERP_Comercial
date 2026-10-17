from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.core.schemas import QtyField, ReasonIn
from app.core.serialize import paginate, to_dict
from app.modules.logistics import service as svc
from app.modules.logistics.models import CustomerReturn, DeliveryIncident, DispatchOrder, ShipmentEvent

router = APIRouter(prefix="/logistics", tags=["Logística y despacho"],
                   dependencies=[Depends(require_module("logistics"))])


class DispatchLineIn(BaseModel):
    so_line_id: int
    quantity: Decimal = QtyField()


class DispatchIn(BaseModel):
    sales_order_id: int
    carrier_id: int | None = None
    route_id: int | None = None
    planned_ship_date: date | None = None
    delivery_address: str | None = Field(default=None, max_length=255)
    lines: list[DispatchLineIn] | None = None


class PickIn(BaseModel):
    dispatch_line_id: int
    qty_picked: Decimal = Field(ge=0)


class PickingIn(BaseModel):
    picks: list[PickIn] = Field(min_length=1)


class PackIn(BaseModel):
    packages_count: int = Field(gt=0)
    gross_weight_kg: Decimal = Field(default=Decimal("0"), ge=0)


class ShipIn(BaseModel):
    carrier_id: int | None = None
    route_id: int | None = None
    vehicle_plate: str | None = Field(default=None, max_length=20)
    driver_name: str | None = Field(default=None, max_length=120)
    tracking_number: str | None = Field(default=None, max_length=60)
    freight_cost: Decimal | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=1000)


class DeliveredLine(BaseModel):
    dispatch_line_id: int
    qty_delivered: Decimal = Field(ge=0)


class DeliverIn(BaseModel):
    received_by: str = Field(min_length=3, max_length=120)
    delivered_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    lines: list[DeliveredLine] | None = None


class EventIn(BaseModel):
    status: str = Field(max_length=30)
    location_text: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=1000)


class IncidentIn(BaseModel):
    incident_type: str = Field(pattern="^(damaged|missing|late|rejected|address|other)$")
    description: str = Field(min_length=5, max_length=2000)


class ResolveIn(BaseModel):
    resolution: str = Field(min_length=5, max_length=2000)


class ReturnLineIn(BaseModel):
    dispatch_line_id: int
    quantity: Decimal = QtyField()
    lot_id: int | None = None
    condition: str = Field(default="resellable", pattern="^(resellable|damaged)$")


class ReturnIn(BaseModel):
    location_id: int
    return_date: date
    reason: str = Field(min_length=5, max_length=255)
    lines: list[ReturnLineIn] = Field(min_length=1)


@router.get("/dispatches")
def list_dispatches(status: str | None = None, customer_id: int | None = None, start: date | None = None,
                    end: date | None = None, limit: int = Query(50, le=500), offset: int = 0,
                    p: Principal = Depends(require("logistics.dispatch.read")), db: Session = Depends(get_db)):
    stmt = select(DispatchOrder).where(DispatchOrder.company_id == p.company_id)
    if status:
        stmt = stmt.where(DispatchOrder.status == status)
    if customer_id:
        stmt = stmt.where(DispatchOrder.customer_id == customer_id)
    if start:
        stmt = stmt.where(DispatchOrder.created_at >= start)
    if end:
        stmt = stmt.where(DispatchOrder.created_at < datetime.combine(end, datetime.max.time()))
    return paginate(db, stmt.order_by(DispatchOrder.id.desc()), limit, offset, "lines")


@router.get("/dispatches/{d_id}")
def get_dispatch(d_id: int, p: Principal = Depends(require("logistics.dispatch.read")), db: Session = Depends(get_db)):
    d = get_owned(db, DispatchOrder, d_id, p.company_id)
    out = to_dict(d, "lines")
    out["events"] = [to_dict(e) for e in db.scalars(select(ShipmentEvent).where(ShipmentEvent.dispatch_id == d.id)
                                                     .order_by(ShipmentEvent.event_time))]
    out["incidents"] = [to_dict(i) for i in db.scalars(select(DeliveryIncident).where(DeliveryIncident.dispatch_id == d.id))]
    out["returns"] = [to_dict(r, "lines") for r in db.scalars(select(CustomerReturn).where(CustomerReturn.dispatch_id == d.id))]
    return out


@router.post("/dispatches", status_code=201)
def create_dispatch(body: DispatchIn, p: Principal = Depends(require("logistics.dispatch.create")),
                    db: Session = Depends(get_db)):
    data = body.model_dump(exclude_none=True)
    so_id = data.pop("sales_order_id")
    d = svc.create_dispatch(db, p, so_id, data)
    db.commit()
    return to_dict(d, "lines")


class PlanIn(BaseModel):
    route_id: int | None = None
    carrier_id: int | None = None
    planned_ship_date: date | None = None
    delivery_address: str | None = Field(default=None, max_length=255)


@router.patch("/dispatches/{d_id}/plan")
def plan(d_id: int, body: PlanIn, p: Principal = Depends(require("logistics.dispatch.create")),
         db: Session = Depends(get_db)):
    d = svc.plan_dispatch(db, p, d_id, body.model_dump(exclude_unset=True))
    db.commit()
    return to_dict(d, "lines")


@router.post("/dispatches/{d_id}/start-picking")
def start_picking(d_id: int, p: Principal = Depends(require("logistics.dispatch.create")),
                  db: Session = Depends(get_db)):
    d = svc.start_picking(db, p, d_id)
    db.commit()
    return to_dict(d, "lines")


@router.post("/dispatches/{d_id}/picking")
def confirm_picking(d_id: int, body: PickingIn, p: Principal = Depends(require("logistics.dispatch.create")),
                    db: Session = Depends(get_db)):
    d = svc.confirm_picking(db, p, d_id, [x.model_dump() for x in body.picks])
    db.commit()
    return to_dict(d, "lines")


@router.post("/dispatches/{d_id}/pack")
def pack(d_id: int, body: PackIn, p: Principal = Depends(require("logistics.dispatch.create")),
         db: Session = Depends(get_db)):
    d = svc.pack(db, p, d_id, body.packages_count, body.gross_weight_kg)
    db.commit()
    return to_dict(d, "lines")


@router.post("/dispatches/{d_id}/ship")
def ship(d_id: int, body: ShipIn, p: Principal = Depends(require("logistics.dispatch.post")),
         db: Session = Depends(get_db)):
    d = svc.ship(db, p, d_id, body.model_dump())
    db.commit()
    return to_dict(d, "lines")


@router.post("/dispatches/{d_id}/deliver")
def deliver(d_id: int, body: DeliverIn, p: Principal = Depends(require("logistics.dispatch.post")),
            db: Session = Depends(get_db)):
    data = body.model_dump()
    if data.get("lines"):
        data["lines"] = [x for x in data["lines"]]
    d = svc.deliver(db, p, d_id, data)
    db.commit()
    return to_dict(d, "lines")


@router.post("/dispatches/{d_id}/cancel")
def cancel(d_id: int, body: ReasonIn, p: Principal = Depends(require("logistics.dispatch.void")),
           db: Session = Depends(get_db)):
    d = svc.cancel_dispatch(db, p, d_id, body.reason)
    db.commit()
    return to_dict(d)


@router.post("/dispatches/{d_id}/events", status_code=201)
def add_event(d_id: int, body: EventIn, p: Principal = Depends(require("logistics.dispatch.create")),
              db: Session = Depends(get_db)):
    d = get_owned(db, DispatchOrder, d_id, p.company_id)
    svc._event(db, d, body.status, p.user_id, body.notes, body.location_text)
    db.commit()
    return {"ok": True}


@router.post("/dispatches/{d_id}/incidents", status_code=201)
def add_incident(d_id: int, body: IncidentIn, p: Principal = Depends(require("logistics.dispatch.create")),
                 db: Session = Depends(get_db)):
    inc = svc.register_incident(db, p, d_id, body.model_dump())
    db.commit()
    return to_dict(inc)


@router.get("/incidents")
def list_incidents(status: str | None = None, limit: int = Query(50, le=500), offset: int = 0,
                   p: Principal = Depends(require("logistics.dispatch.read")), db: Session = Depends(get_db)):
    stmt = select(DeliveryIncident).where(DeliveryIncident.company_id == p.company_id)
    if status:
        stmt = stmt.where(DeliveryIncident.status == status)
    return paginate(db, stmt.order_by(DeliveryIncident.id.desc()), limit, offset)


@router.post("/incidents/{inc_id}/resolve")
def resolve(inc_id: int, body: ResolveIn, p: Principal = Depends(require("logistics.dispatch.create")),
            db: Session = Depends(get_db)):
    inc = svc.resolve_incident(db, p, inc_id, body.resolution)
    db.commit()
    return to_dict(inc)


@router.post("/dispatches/{d_id}/returns", status_code=201)
def receive_return(d_id: int, body: ReturnIn, p: Principal = Depends(require("logistics.return.post")),
                   db: Session = Depends(get_db)):
    ret = svc.receive_return(db, p, d_id, body.model_dump())
    db.commit()
    return to_dict(ret, "lines")


@router.get("/returns")
def list_returns(limit: int = Query(50, le=500), offset: int = 0,
                 p: Principal = Depends(require("logistics.return.read")), db: Session = Depends(get_db)):
    stmt = select(CustomerReturn).where(CustomerReturn.company_id == p.company_id).order_by(CustomerReturn.id.desc())
    return paginate(db, stmt, limit, offset, "lines")


@router.get("/delivery-plan")
def delivery_plan(on: date, route_id: int | None = None, p: Principal = Depends(require("logistics.dispatch.read")),
                  db: Session = Depends(get_db)):
    """Planificación de entregas: despachos preparados o empacados programados para la fecha, por ruta."""
    stmt = select(DispatchOrder).where(DispatchOrder.company_id == p.company_id,
                                       DispatchOrder.status.in_(("picked", "packed", "shipped")),
                                       DispatchOrder.planned_ship_date == on)
    if route_id:
        stmt = stmt.where(DispatchOrder.route_id == route_id)
    rows = db.scalars(stmt.order_by(DispatchOrder.route_id, DispatchOrder.id)).all()
    by_route: dict = {}
    for d in rows:
        by_route.setdefault(d.route_id, []).append(to_dict(d))
    return [{"route_id": k, "dispatches": v, "count": len(v)} for k, v in by_route.items()]

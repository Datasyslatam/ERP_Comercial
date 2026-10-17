import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, require
from app.core.errors import BusinessRuleViolation, NotFound
from app.core.serialize import paginate, to_dict
from app.modules.kpi import service as svc
from app.modules.kpi.engine import REGISTRY, Filters
from app.modules.kpi.models import Alert, KpiTarget

router = APIRouter(prefix="/kpi", tags=["Indicadores y dashboards"])

# Módulo del KPI → permiso de lectura requerido para verlo (los KPI respetan los permisos del usuario).
MODULE_PERMS = {"finance": "accounting.reports.read", "management": "kpi.dashboard.read",
                "purchasing": "purchasing.order.read", "operations": "operations.work_order.read",
                "quality": "quality.inspection.read", "inventory": "inventory.stock.read",
                "logistics": "logistics.dispatch.read"}


def _filters(site_id: int | None = None, supplier_id: int | None = None, item_id: int | None = None,
             cost_center_id: int | None = None, customer_id: int | None = None,
             business_unit_id: int | None = None) -> Filters:
    return Filters(site_id, supplier_id, item_id, cost_center_id, customer_id, business_unit_id)


def _allowed(p: Principal) -> set[str]:
    return {m for m, perm in MODULE_PERMS.items() if p.has(perm)}


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    today = date.today()
    s = start or today.replace(day=1)
    e = end or today
    if s > e:
        raise BusinessRuleViolation("La fecha inicial es posterior a la final")
    return s, e


@router.get("/definitions")
def definitions(_: Principal = Depends(require("kpi.dashboard.read"))):
    return [{"code": d.code, "module": d.module, "name": d.name, "description": d.description, "formula": d.formula,
             "source": d.source, "unit": d.unit, "frequency": d.frequency, "direction": d.direction,
             "filters": d.filters, "drilldown": d.drilldown} for d in REGISTRY.values()]


@router.get("/dashboard")
def dashboard(start: date | None = None, end: date | None = None, module: str | None = None,
              f: Filters = Depends(_filters), p: Principal = Depends(require("kpi.dashboard.read")),
              db: Session = Depends(get_db)):
    """Dashboard general (sin módulo) o específico de un módulo. Filtrado por permisos y sedes del usuario."""
    s, e = _period(start, end)
    if f.site_id:
        p.ensure_site(f.site_id)
    elif p.site_ids is not None and len(p.site_ids) == 1:
        f.site_id = next(iter(p.site_ids))
    items = svc.dashboard(db, p.company, s, e, f, module, _allowed(p))
    return {"company": {"id": p.company.id, "name": p.company.legal_name, "currency": p.company.functional_currency},
            "period": {"start": s, "end": e}, "generated_at": datetime.now(UTC), "kpis": items,
            "summary": {st: sum(1 for k in items if k["status"] == st)
                        for st in ("ok", "warning", "critical", "no_target", "no_data")}}


@router.get("/kpis/{code}")
def kpi_detail(code: str, start: date | None = None, end: date | None = None, f: Filters = Depends(_filters),
               p: Principal = Depends(require("kpi.dashboard.read")), db: Session = Depends(get_db)):
    d = REGISTRY.get(code)
    if d is None:
        raise NotFound("Indicador inexistente")
    if d.module not in _allowed(p):
        from app.core.errors import Forbidden

        raise Forbidden("No tiene permiso sobre el módulo de este indicador")
    s, e = _period(start, end)
    return svc.compute(db, p.company, code, s, e, f)


@router.get("/kpis/{code}/trend")
def kpi_trend(code: str, months: int = Query(6, ge=1, le=24), end: date | None = None,
              f: Filters = Depends(_filters), p: Principal = Depends(require("kpi.dashboard.read")),
              db: Session = Depends(get_db)):
    d = REGISTRY.get(code)
    if d is None or d.module not in _allowed(p):
        raise NotFound("Indicador inexistente o sin permiso")
    return svc.trend(db, p.company, code, end or date.today(), months, f)


@router.get("/dashboard.csv")
def export_dashboard(start: date | None = None, end: date | None = None, module: str | None = None,
                     f: Filters = Depends(_filters), p: Principal = Depends(require("kpi.dashboard.export")),
                     db: Session = Depends(get_db)):
    s, e = _period(start, end)
    items = svc.dashboard(db, p.company, s, e, f, module, _allowed(p))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["codigo", "modulo", "indicador", "valor", "unidad", "meta", "estado", "confianza", "formula",
                "fuente", "periodo_inicio", "periodo_fin", "notas"])
    for k in items:
        w.writerow([k["code"], k["module"], k["name"], k["value"], k["unit_label"], k["target"], k["status"],
                    k["confidence"], k["formula"], k["source"], s, e, " | ".join(k["notes"])])
    log_action(db, "export", "kpi_dashboard", None, f"{module or 'general'} {s}..{e}")
    db.commit()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="indicadores_{s}_{e}.csv"'})


class TargetIn(BaseModel):
    kpi_code: str
    site_id: int | None = None
    target: Decimal | None = None
    warning_threshold: Decimal | None = None
    critical_threshold: Decimal | None = None
    owner_id: int | None = None
    alerts_enabled: bool = True


@router.get("/targets")
def list_targets(p: Principal = Depends(require("kpi.dashboard.read")), db: Session = Depends(get_db)):
    return [to_dict(t) for t in db.scalars(select(KpiTarget).where(KpiTarget.company_id == p.company_id))]


@router.put("/targets")
def set_target(body: TargetIn, p: Principal = Depends(require("kpi.config.admin")), db: Session = Depends(get_db)):
    if body.kpi_code not in REGISTRY:
        raise NotFound("Indicador inexistente")
    t = db.scalar(select(KpiTarget).where(KpiTarget.company_id == p.company_id, KpiTarget.kpi_code == body.kpi_code,
                                          KpiTarget.site_id.is_(None) if body.site_id is None
                                          else KpiTarget.site_id == body.site_id))
    if t is None:
        t = KpiTarget(company_id=p.company_id, kpi_code=body.kpi_code, site_id=body.site_id)
        db.add(t)
    for k, v in body.model_dump(exclude={"kpi_code", "site_id"}).items():
        setattr(t, k, v)
    log_action(db, "admin", "kpi_targets", body.kpi_code, f"Meta {body.target}")
    db.commit()
    return to_dict(t)


@router.get("/alerts")
def alerts(status: str = "open", limit: int = Query(100, le=500), offset: int = 0,
           p: Principal = Depends(require("kpi.alerts.read")), db: Session = Depends(get_db)):
    stmt = select(Alert).where(Alert.company_id == p.company_id, Alert.status == status)
    return paginate(db, stmt.order_by(Alert.id.desc()), limit, offset)


class AckIn(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)
    close: bool = False


@router.post("/alerts/{alert_id}/ack")
def acknowledge(alert_id: int, body: AckIn, p: Principal = Depends(require("kpi.alerts.approve")),
                db: Session = Depends(get_db)):
    a = get_owned(db, Alert, alert_id, p.company_id, lock=True)
    a.status = "closed" if body.close else "acknowledged"
    a.acknowledged_by_id, a.acknowledged_at, a.notes = p.user_id, datetime.now(UTC), body.notes
    db.commit()
    return to_dict(a)


@router.post("/alerts/evaluate")
def evaluate(p: Principal = Depends(require("kpi.config.admin")), db: Session = Depends(get_db)):
    n = svc.evaluate_alerts(db, p.company)
    db.commit()
    return {"created": n}

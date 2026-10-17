"""Servicio de indicadores: cálculo con metadatos completos, dashboards, tendencias, instantáneas y alertas."""
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.kpi.engine import REGISTRY, Filters, confidence_for, status_for
from app.modules.kpi.models import Alert, KpiSnapshot, KpiTarget
from app.modules.org.models import Company

UNITS = {"currency": "moneda funcional", "pct": "%", "days": "días", "count": "cantidad", "ratio": "veces",
         "qty_per_hour": "unidades/hora"}


def _target(db: Session, company_id: int, code: str, site_id: int | None) -> KpiTarget | None:
    rows = db.scalars(select(KpiTarget).where(KpiTarget.company_id == company_id, KpiTarget.kpi_code == code)).all()
    specific = next((t for t in rows if site_id and t.site_id == site_id), None)
    return specific or next((t for t in rows if t.site_id is None), None)


def compute(db: Session, company: Company, code: str, start: date, end: date, filters: Filters,
            persist: bool = False) -> dict:
    d = REGISTRY[code]
    applied = {k: v for k, v in asdict(filters).items() if v is not None}
    ignored = [k for k in applied if k not in d.filters]
    eff = Filters(**{k: v for k, v in applied.items() if k in d.filters})
    res = d.fn(db, company.id, start, end, eff)
    tgt = _target(db, company.id, code, filters.site_id)
    status = status_for(res.value, d.direction, tgt.target if tgt else None, tgt.critical_threshold if tgt else None)
    notes = list(res.notes) + ([f"Filtros no aplicables a este indicador: {', '.join(ignored)}"] if ignored else [])
    now = datetime.now(UTC)
    out = {
        "code": d.code, "module": d.module, "name": d.name, "description": d.description, "formula": d.formula,
        "source": d.source, "unit": d.unit, "unit_label": company.functional_currency if d.unit == "currency"
        else UNITS[d.unit], "frequency": d.frequency, "direction": d.direction,
        "period": {"start": start, "end": end}, "filters_applied": {k: v for k, v in applied.items() if k in d.filters},
        "value": res.value, "numerator": res.numerator, "denominator": res.denominator,
        "observations": res.observations, "target": tgt.target if tgt else None,
        "warning_threshold": tgt.warning_threshold if tgt else None,
        "critical_threshold": tgt.critical_threshold if tgt else None, "owner_id": tgt.owner_id if tgt else None,
        "status": status, "confidence": confidence_for(res), "notes": notes, "details": res.details,
        "last_updated": now, "drilldown": d.drilldown,
    }
    if persist:
        db.add(KpiSnapshot(company_id=company.id, kpi_code=code, period_start=start, period_end=end,
                           filters={k: v for k, v in applied.items()}, value=res.value, status=status,
                           confidence=out["confidence"], details={"notes": notes}))
    return out


def dashboard(db: Session, company: Company, start: date, end: date, filters: Filters,
              module: str | None = None, allowed_modules: set[str] | None = None) -> list[dict]:
    out = []
    for code, d in REGISTRY.items():
        if module and d.module != module:
            continue
        if allowed_modules is not None and d.module not in allowed_modules:
            continue
        out.append(compute(db, company, code, start, end, filters))
    return out


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    from datetime import timedelta

    return start, nxt - timedelta(days=1)


def trend(db: Session, company: Company, code: str, end: date, months: int, filters: Filters) -> list[dict]:
    pts = []
    y, m = end.year, end.month
    for _ in range(months):
        s, e = month_bounds(y, m)
        r = compute(db, company, code, s, min(e, end), filters)
        pts.append({"period": f"{y}-{m:02d}", "value": r["value"], "status": r["status"]})
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return list(reversed(pts))


def evaluate_alerts(db: Session, company: Company, today: date | None = None) -> int:
    """Evalúa KPIs del mes en curso con meta configurada y alertas activas; crea alertas sin duplicar."""
    today = today or date.today()
    start, _ = month_bounds(today.year, today.month)
    created = 0
    targets = db.scalars(select(KpiTarget).where(KpiTarget.company_id == company.id,
                                                 KpiTarget.alerts_enabled.is_(True))).all()
    for t in targets:
        if t.kpi_code not in REGISTRY:
            continue
        r = compute(db, company, t.kpi_code, start, today, Filters(site_id=t.site_id), persist=True)
        if r["status"] not in ("warning", "critical"):
            continue
        key = f"kpi:{t.kpi_code}:{t.site_id or 0}:{today:%Y-%m}:{r['status']}"
        if db.scalar(select(Alert.id).where(Alert.company_id == company.id, Alert.dedupe_key == key)):
            continue
        db.add(Alert(company_id=company.id, source=f"kpi:{t.kpi_code}", dedupe_key=key, severity=r["status"],
                     message=f"{r['name']}: {r['value']} {r['unit_label']} (meta {t.target})", value=r["value"],
                     threshold=t.target, link=r["drilldown"]))
        created += 1
    # Alertas operativas de inventario (faltantes y vencimientos)
    from app.modules.inventory.service import expiring_lots, replenishment_alerts

    for row in replenishment_alerts(db, company.id):
        key = f"stock:min:{row['item_id']}:{today:%Y-%m-%d}"
        if not db.scalar(select(Alert.id).where(Alert.company_id == company.id, Alert.dedupe_key == key)):
            db.add(Alert(company_id=company.id, source="stock:min", dedupe_key=key, severity="warning",
                         message=f"{row['sku']} {row['name']}: disponible {row['available']} < mínimo {row['min_stock']}",
                         value=Decimal(row["available"]), threshold=row["min_stock"], link="/inventario/reabastecimiento"))
            created += 1
    for row in expiring_lots(db, company.id, 30, today):
        key = f"stock:expiry:{row['lot_id']}"
        if not db.scalar(select(Alert.id).where(Alert.company_id == company.id, Alert.dedupe_key == key)):
            sev = "critical" if row["days_left"] <= 0 else "warning"
            db.add(Alert(company_id=company.id, source="stock:expiry", dedupe_key=key, severity=sev,
                         message=f"Lote {row['lot_number']} de {row['sku']} vence {row['expiry_date']} "
                                 f"({row['qty']} unidades)", link="/inventario/vencimientos"))
            created += 1
    return created

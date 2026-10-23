"""Motor de indicadores. Cada KPI se calcula directamente desde datos transaccionales persistidos.

Si no hay datos suficientes el valor es None y el estado 'no_data'; nunca se rellenan cifras.
Metas y umbrales son configuración por empresa (kpi_targets); sin meta el estado es 'no_target'.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

ZERO = Decimal("0")


@dataclass
class Filters:
    site_id: int | None = None
    supplier_id: int | None = None
    item_id: int | None = None
    cost_center_id: int | None = None
    customer_id: int | None = None
    business_unit_id: int | None = None


@dataclass
class Result:
    value: Decimal | None
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    observations: int | None = None
    notes: list[str] = field(default_factory=list)
    details: list[dict] | None = None


@dataclass
class KpiDef:
    code: str
    module: str
    name: str
    description: str
    formula: str
    source: str
    unit: str  # currency, pct, days, count, ratio, qty_per_hour
    frequency: str
    direction: str  # higher_better / lower_better / neutral
    filters: tuple[str, ...]
    fn: Callable[[Session, int, date, date, Filters], Result]
    drilldown: str


REGISTRY: dict[str, KpiDef] = {}


def kpi(code, module, name, description, formula, source, unit, direction, filters=(), frequency="diaria",
        drilldown=""):
    def deco(fn):
        REGISTRY[code] = KpiDef(code, module, name, description, formula, source, unit, frequency, direction,
                                tuple(filters), fn, drilldown)
        return fn
    return deco


def _one(db: Session, sql: str, **params):
    return db.execute(text(sql), params).one()


def _scalar(db: Session, sql: str, **params):
    return db.execute(text(sql), params).scalar()


def _pct(num, den) -> Decimal | None:
    if den is None or Decimal(den) == 0:
        return None
    return (Decimal(num or 0) / Decimal(den) * 100).quantize(Decimal("0.01"))


def _gl(db, c, s, e, types: tuple[str, ...], f: Filters, sign: str = "credit") -> Decimal:
    expr = "l.credit - l.debit" if sign == "credit" else "l.debit - l.credit"
    cc = "and l.cost_center_id = :cc" if f.cost_center_id else ""
    return Decimal(_scalar(db, f"""
        select coalesce(sum({expr}), 0) from journal_lines l join journal_entries e on e.id = l.entry_id
          join accounts a on a.id = l.account_id
         where e.company_id = :c and e.status in ('posted','reversed') and e.journal_type <> 'closing'
           and e.entry_date between :s and :e and a.account_type = any(:t) {cc}""",
        c=c, s=s, e=e, t=list(types), cc=f.cost_center_id))


def _has_gl(db, c, s, e) -> bool:
    return bool(_scalar(db, """select exists(select 1 from journal_entries where company_id = :c
        and status in ('posted','reversed') and entry_date between :s and :e)""", c=c, s=s, e=e))


# ================================================================ GERENCIA Y FINANZAS
@kpi("revenue", "finance", "Ingresos netos", "Ingresos contabilizados en el periodo, netos de devoluciones.",
     "Σ(créditos − débitos) de cuentas de ingreso del periodo", "journal_lines (cuentas tipo revenue)",
     "currency", "higher_better", ("cost_center_id",), drilldown="/contabilidad/estado-resultados")
def _revenue(db, c, s, e, f):
    if not _has_gl(db, c, s, e):
        return Result(None, notes=["Sin asientos contables en el periodo"])
    return Result(_gl(db, c, s, e, ("revenue",), f))


@kpi("revenue_growth", "finance", "Crecimiento de ingresos", "Variación de ingresos frente al periodo anterior de "
     "igual duración.", "(Ingresos periodo − Ingresos periodo anterior) / Ingresos periodo anterior × 100",
     "journal_lines", "pct", "higher_better", ("cost_center_id",), drilldown="/contabilidad/estado-resultados")
def _revenue_growth(db, c, s, e, f):
    days = (e - s).days + 1
    ps, pe = s - timedelta(days=days), s - timedelta(days=1)
    if not _has_gl(db, c, ps, pe):
        return Result(None, notes=["No hay datos del periodo anterior para comparar"])
    cur, prev = _gl(db, c, s, e, ("revenue",), f), _gl(db, c, ps, pe, ("revenue",), f)
    return Result(_pct(cur - prev, prev), cur - prev, prev)


@kpi("gross_margin", "finance", "Margen bruto", "Porcentaje de los ingresos que queda después del costo de ventas.",
     "(Ingresos − Costo de ventas) / Ingresos × 100", "journal_lines (revenue, cost)", "pct", "higher_better",
     ("cost_center_id",), drilldown="/contabilidad/estado-resultados")
def _gross_margin(db, c, s, e, f):
    rev = _gl(db, c, s, e, ("revenue",), f)
    cost = _gl(db, c, s, e, ("cost",), f, "debit")
    return Result(_pct(rev - cost, rev), rev - cost, rev, notes=[] if rev else ["Sin ingresos en el periodo"])


@kpi("net_margin", "finance", "Rentabilidad neta", "Utilidad neta sobre ingresos.",
     "(Ingresos − Costos − Gastos) / Ingresos × 100", "journal_lines", "pct", "higher_better", ("cost_center_id",),
     drilldown="/contabilidad/estado-resultados")
def _net_margin(db, c, s, e, f):
    rev = _gl(db, c, s, e, ("revenue",), f)
    out = _gl(db, c, s, e, ("cost", "expense"), f, "debit")
    return Result(_pct(rev - out, rev), rev - out, rev)


@kpi("operating_expenses", "finance", "Gastos operativos", "Gastos contabilizados en el periodo.",
     "Σ(débitos − créditos) de cuentas de gasto", "journal_lines (expense)", "currency", "lower_better",
     ("cost_center_id",), drilldown="/contabilidad/estado-resultados")
def _opex(db, c, s, e, f):
    if not _has_gl(db, c, s, e):
        return Result(None, notes=["Sin asientos contables en el periodo"])
    return Result(_gl(db, c, s, e, ("expense",), f, "debit"))


def _budget(db, c, s, e, category, f):
    cc = "and cost_center_id = :cc" if f.cost_center_id else ""
    site = "and site_id = :site" if f.site_id else ""
    return _scalar(db, f"""select sum(amount) from budget_lines where company_id = :c and category = :cat
        and make_date(cast(year as int), cast(month as int), 1)
            between date_trunc('month', cast(:s as date)) and :e {cc} {site}""",
                   c=c, cat=category, s=s, e=e, cc=f.cost_center_id, site=f.site_id)


@kpi("budget_compliance_expenses", "finance", "Cumplimiento presupuestal de gastos",
     "Gasto real frente al presupuesto aprobado.", "Gasto real / Presupuesto de gastos × 100",
     "journal_lines + budget_lines(category=expenses)", "pct", "lower_better", ("cost_center_id", "site_id"),
     drilldown="/gerencia/presupuestos")
def _budget_exp(db, c, s, e, f):
    b = _budget(db, c, s, e, "expenses", f)
    if not b:
        return Result(None, notes=["No hay presupuesto de gastos cargado para el periodo"])
    real = _gl(db, c, s, e, ("expense",), f, "debit")
    return Result(_pct(real, b), real, Decimal(b))


@kpi("revenue_vs_budget", "finance", "Ingresos frente a meta presupuestal", "Ingresos reales frente a lo "
     "presupuestado.", "Ingresos reales / Presupuesto de ingresos × 100", "journal_lines + budget_lines(revenue)",
     "pct", "higher_better", ("cost_center_id", "site_id"), drilldown="/gerencia/presupuestos")
def _rev_budget(db, c, s, e, f):
    b = _budget(db, c, s, e, "revenue", f)
    if not b:
        return Result(None, notes=["No hay presupuesto de ingresos cargado para el periodo"])
    real = _gl(db, c, s, e, ("revenue",), f)
    return Result(_pct(real, b), real, Decimal(b))


def _open_items(db, c, kind, as_of, overdue=False, f: Filters | None = None):
    od = "and due_date < :d" if overdue else ""
    party = "and party_id = :p" if f and (f.customer_id or f.supplier_id) else ""
    pid = (f.customer_id if kind == "receivable" else f.supplier_id) if f else None
    return Decimal(_scalar(db, f"""select coalesce(sum(open_amount * exchange_rate), 0) from open_items
        where company_id = :c and kind = :k and status in ('open','partial') and issue_date <= :d {od} {party}""",
                           c=c, k=kind, d=as_of, p=pid))


def _has_items(db, c, kind) -> bool:
    return bool(_scalar(db, "select exists(select 1 from open_items where company_id = :c and kind = :k)", c=c, k=kind))


@kpi("ar_balance", "finance", "Cuentas por cobrar", "Saldo abierto de cartera de clientes a la fecha de corte.",
     "Σ saldo abierto × tasa de las partidas por cobrar", "open_items(kind=receivable)", "currency", "lower_better",
     ("customer_id",), drilldown="/contabilidad/cuentas-por-cobrar")
def _ar(db, c, s, e, f):
    if not _has_items(db, c, "receivable"):
        return Result(None, notes=["No hay cartera registrada (facturas o saldos iniciales)"])
    return Result(_open_items(db, c, "receivable", e, f=f))


@kpi("ar_overdue_pct", "finance", "Cartera vencida", "Porcentaje de la cartera con fecha de vencimiento superada.",
     "Cartera vencida / Cartera total × 100", "open_items", "pct", "lower_better", ("customer_id",),
     drilldown="/contabilidad/cuentas-por-cobrar")
def _ar_over(db, c, s, e, f):
    total = _open_items(db, c, "receivable", e, f=f)
    return Result(_pct(_open_items(db, c, "receivable", e, True, f), total), None, total,
                  notes=[] if total else ["Sin cartera abierta"])


@kpi("ap_balance", "finance", "Cuentas por pagar", "Saldo abierto con proveedores a la fecha de corte.",
     "Σ saldo abierto × tasa de las partidas por pagar", "open_items(kind=payable)", "currency", "neutral",
     ("supplier_id",), drilldown="/contabilidad/cuentas-por-pagar")
def _ap(db, c, s, e, f):
    if not _has_items(db, c, "payable"):
        return Result(None, notes=["No hay cuentas por pagar registradas"])
    return Result(_open_items(db, c, "payable", e, f=f))


@kpi("dso", "finance", "Días de cartera (DSO)", "Días promedio de cobro.",
     "Cartera al corte / Ingresos del periodo × días del periodo", "open_items + journal_lines", "days",
     "lower_better", drilldown="/contabilidad/cuentas-por-cobrar")
def _dso(db, c, s, e, f):
    rev = _gl(db, c, s, e, ("revenue",), Filters())
    if not rev:
        return Result(None, notes=["Sin ingresos en el periodo"])
    ar = _open_items(db, c, "receivable", e)
    return Result((ar / rev * ((e - s).days + 1)).quantize(Decimal("0.1")), ar, rev)


def _cash(db, c, until):
    return Decimal(_scalar(db, """select coalesce(sum(l.debit - l.credit), 0) from journal_lines l
        join journal_entries e on e.id = l.entry_id join accounts a on a.id = l.account_id
        where e.company_id = :c and e.status in ('posted','reversed') and a.is_cash and e.entry_date <= :d""",
                           c=c, d=until))


@kpi("cash_balance", "finance", "Efectivo disponible", "Saldo contable de caja y bancos al corte.",
     "Σ(débitos − créditos) de cuentas marcadas como caja/bancos hasta la fecha de corte", "journal_lines",
     "currency", "higher_better", drilldown="/contabilidad/flujo-efectivo")
def _cash_balance(db, c, s, e, f):
    if not _scalar(db, "select exists(select 1 from accounts where company_id = :c and is_cash)", c=c):
        return Result(None, notes=["No hay cuentas de caja/bancos configuradas"])
    if not _scalar(db, """select exists(select 1 from journal_lines l join accounts a on a.id = l.account_id
                         where l.company_id = :c and a.is_cash)""", c=c):
        return Result(None, notes=["Sin movimientos de caja o bancos registrados"])
    return Result(_cash(db, c, e))


@kpi("net_cash_flow", "finance", "Flujo de caja neto", "Variación del efectivo en el periodo.",
     "Efectivo al cierre − Efectivo al inicio", "journal_lines (cuentas de caja)", "currency", "higher_better",
     drilldown="/contabilidad/flujo-efectivo")
def _ncf(db, c, s, e, f):
    if not _has_gl(db, c, s, e):
        return Result(None, notes=["Sin movimientos contables en el periodo"])
    return Result(_cash(db, c, e) - _cash(db, c, s - timedelta(days=1)))


@kpi("strategic_goals", "management", "Cumplimiento de metas estratégicas", "Promedio ponderado del avance de las "
     "metas estratégicas vigentes (valor real del KPI asociado frente a su meta, tope 100%).",
     "Σ(min(real/meta,1) × peso) / Σ peso × 100", "strategic_goals + KPIs asociados", "pct", "higher_better",
     drilldown="/gerencia/metas")
def _goals(db, c, s, e, f):
    goals = db.execute(text("""select kpi_code, target_value, weight from strategic_goals where company_id = :c
        and period_start <= :e and period_end >= :s"""), {"c": c, "s": s, "e": e}).all()
    if not goals:
        return Result(None, notes=["No hay metas estratégicas registradas para el periodo"])
    num = den = ZERO
    details, missing = [], []
    for g in goals:
        d = REGISTRY.get(g.kpi_code)
        if d is None or d.code == "strategic_goals":
            missing.append(g.kpi_code)
            continue
        r = d.fn(db, c, s, e, f)
        if r.value is None or not g.target_value:
            missing.append(g.kpi_code)
            continue
        ratio = r.value / g.target_value if d.direction != "lower_better" else (
            g.target_value / r.value if r.value else Decimal("1"))
        ratio = max(ZERO, min(Decimal("1"), ratio))
        num += ratio * g.weight
        den += g.weight
        details.append({"kpi": g.kpi_code, "actual": r.value, "target": g.target_value, "achievement": ratio * 100})
    notes = [f"Metas sin datos: {', '.join(missing)}"] if missing else []
    return Result(_pct(num, den), num, den, len(details), notes, details)


# ================================================================ COMPRAS
def _site(f, alias):
    return f"and {alias}.site_id = :site" if f.site_id else ""


def _supp(f, alias):
    return f"and {alias}.supplier_id = :supp" if f.supplier_id else ""


@kpi("purchase_cycle_days", "purchasing", "Ciclo de compra", "Días promedio desde la creación de la solicitud hasta "
     "la primera recepción de la orden asociada.", "Promedio(fecha primera recepción − fecha solicitud)",
     "purchase_requisitions + purchase_orders + goods_receipts", "days", "lower_better", ("site_id", "supplier_id"),
     drilldown="/compras/solicitudes")
def _pcycle(db, c, s, e, f):
    r = _one(db, f"""select avg(x.d), count(*) from (
        select min(gr.receipt_date) - cast(r.created_at as date) d from purchase_requisitions r
          join purchase_orders po on po.requisition_id = r.id join goods_receipts gr on gr.purchase_order_id = po.id
         where r.company_id = :c {_site(f, 'r')} {_supp(f, 'po')} group by r.id
        having min(gr.receipt_date) between :s and :e) x""", c=c, s=s, e=e, site=f.site_id, supp=f.supplier_id)
    return Result(Decimal(r[0]).quantize(Decimal("0.1")) if r[0] is not None else None, observations=r[1],
                  notes=[] if r[1] else ["No hay compras recibidas con solicitud en el periodo"])


@kpi("purchase_price_variance", "purchasing", "Variación de precios de compra", "Variación porcentual promedio del "
     "precio unitario frente a la compra anterior del mismo artículo.",
     "Promedio((precio actual − precio anterior) / precio anterior × 100)", "purchase_order_lines", "pct",
     "lower_better", ("supplier_id", "item_id"), drilldown="/compras/historial-precios")
def _ppv(db, c, s, e, f):
    item = "and l.item_id = :item" if f.item_id else ""
    r = _one(db, f"""select avg(v), count(*) from (
        select (l.unit_price - lag(l.unit_price) over (partition by l.item_id order by po.order_date, po.id))
               / nullif(lag(l.unit_price) over (partition by l.item_id order by po.order_date, po.id), 0) * 100 v,
               po.order_date d, po.supplier_id
          from purchase_order_lines l join purchase_orders po on po.id = l.purchase_order_id
         where po.company_id = :c and po.status not in ('draft','rejected','cancelled') {item}) x
         where v is not null and d between :s and :e {"and supplier_id = :supp" if f.supplier_id else ""}""",
             c=c, s=s, e=e, item=f.item_id, supp=f.supplier_id)
    return Result(Decimal(r[0]).quantize(Decimal("0.01")) if r[0] is not None else None, observations=r[1],
                  notes=[] if r[1] else ["No hay compras repetidas para comparar precios"])


@kpi("supplier_otd", "purchasing", "Cumplimiento de entregas del proveedor", "Recepciones realizadas en o antes de "
     "la fecha esperada de la orden.", "Recepciones a tiempo / Recepciones × 100", "goods_receipts + purchase_orders",
     "pct", "higher_better", ("supplier_id", "site_id"), drilldown="/compras/recepciones")
def _otd(db, c, s, e, f):
    r = _one(db, f"""select count(*) filter (where po.expected_date is null or gr.receipt_date <= po.expected_date),
        count(*) from goods_receipts gr join purchase_orders po on po.id = gr.purchase_order_id
        where gr.company_id = :c and gr.receipt_date between :s and :e {_supp(f, 'gr')} {_site(f, 'po')}""",
             c=c, s=s, e=e, supp=f.supplier_id, site=f.site_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1], [] if r[1] else ["Sin recepciones en el periodo"])


@kpi("receipts_conformity", "purchasing", "Recepciones conformes", "Cantidad aceptada en inspección de recepción "
     "sobre la cantidad inspeccionada.", "Σ aceptado / Σ inspeccionado × 100 (inspecciones de recepción cerradas)",
     "inspections(stage=receiving)", "pct", "higher_better", ("supplier_id", "item_id"),
     drilldown="/calidad/inspecciones")
def _rconf(db, c, s, e, f):
    item = "and item_id = :item" if f.item_id else ""
    r = _one(db, f"""select coalesce(sum(qty_accepted), 0), coalesce(sum(quantity), 0), count(*) from inspections
        where company_id = :c and stage = 'receiving' and status in ('accepted','rejected','partial')
        and cast(inspected_at as date) between :s and :e {_supp(f, 'inspections')} {item}""",
             c=c, s=s, e=e, supp=f.supplier_id, item=f.item_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[2], [] if r[2] else ["Sin inspecciones de recepción cerradas"])


@kpi("purchases_vs_budget", "purchasing", "Compras frente al presupuesto", "Valor de órdenes aprobadas frente al "
     "presupuesto de compras.", "Σ subtotal OC aprobadas (moneda funcional) / Presupuesto de compras × 100",
     "purchase_orders + budget_lines(purchases)", "pct", "lower_better", ("site_id", "cost_center_id"),
     drilldown="/compras/ordenes")
def _pbudget(db, c, s, e, f):
    b = _budget(db, c, s, e, "purchases", f)
    if not b:
        return Result(None, notes=["No hay presupuesto de compras cargado para el periodo"])
    cc = "and cost_center_id = :cc" if f.cost_center_id else ""
    real = Decimal(_scalar(db, f"""select coalesce(sum(subtotal * exchange_rate), 0) from purchase_orders
        where company_id = :c and status in ('approved','partially_received','received','closed')
        and order_date between :s and :e {cc} {_site(f, 'purchase_orders')}""",
                           c=c, s=s, e=e, cc=f.cost_center_id, site=f.site_id))
    return Result(_pct(real, b), real, Decimal(b))


@kpi("po_open", "purchasing", "Órdenes de compra pendientes", "Órdenes aprobadas no recibidas totalmente.",
     "Conteo de OC en estado aprobada o recibida parcialmente", "purchase_orders", "count", "neutral",
     ("site_id", "supplier_id"), drilldown="/compras/ordenes?status=approved")
def _po_open(db, c, s, e, f):
    n = _scalar(db, f"""select count(*) from purchase_orders where company_id = :c
        and status in ('approved','partially_received') {_site(f, 'purchase_orders')} {_supp(f, 'purchase_orders')}""",
                c=c, site=f.site_id, supp=f.supplier_id)
    return Result(Decimal(n))


@kpi("po_overdue", "purchasing", "Órdenes de compra vencidas", "Órdenes pendientes cuya fecha esperada ya pasó.",
     "Conteo de OC pendientes con fecha esperada < fecha de corte", "purchase_orders", "count", "lower_better",
     ("site_id", "supplier_id"), drilldown="/compras/ordenes?overdue=1")
def _po_over(db, c, s, e, f):
    n = _scalar(db, f"""select count(*) from purchase_orders where company_id = :c and expected_date < :e
        and status in ('approved','partially_received') {_site(f, 'purchase_orders')} {_supp(f, 'purchase_orders')}""",
                c=c, e=e, site=f.site_id, supp=f.supplier_id)
    return Result(Decimal(n))


# ================================================================ OPERACIONES
def _wo(f):
    return "and site_id = :site" if f.site_id else ""


@kpi("wo_plan_compliance", "operations", "Cumplimiento del plan operativo", "Órdenes con fin planificado en el "
     "periodo terminadas a tiempo.", "OT terminadas con fin real ≤ fin planificado / OT con fin planificado en el "
     "periodo × 100", "work_orders", "pct", "higher_better", ("site_id",), drilldown="/operaciones/ordenes")
def _wo_plan(db, c, s, e, f):
    r = _one(db, f"""select count(*) filter (where status in ('completed','closed')
        and cast(actual_end as date) <= planned_end), count(*) from work_orders where company_id = :c
        and status <> 'cancelled' and planned_end between :s and :e {_wo(f)}""", c=c, s=s, e=e, site=f.site_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1], [] if r[1] else ["No hay órdenes planificadas en el periodo"])


@kpi("productivity", "operations", "Productividad", "Unidades buenas producidas por hora registrada.",
     "Σ cantidad producida / Σ horas registradas", "work_orders + work_order_time_logs", "qty_per_hour",
     "higher_better", ("site_id",), drilldown="/operaciones/ordenes")
def _prod(db, c, s, e, f):
    hours = Decimal(_scalar(db, f"""select coalesce(sum(t.hours), 0) from work_order_time_logs t
        join work_orders w on w.id = t.work_order_id where w.company_id = :c and t.log_date between :s and :e
        and w.wo_type = 'production' {_wo(f).replace('site_id', 'w.site_id')}""", c=c, s=s, e=e, site=f.site_id))
    qty = Decimal(_scalar(db, f"""select coalesce(sum(m.quantity), 0) from stock_moves m join work_orders w
        on w.id = m.source_id where m.source_type = 'work_order' and m.move_type = 'production_output'
        and w.company_id = :c and cast(m.move_date as date) between :s and :e
        {_wo(f).replace('site_id', 'w.site_id')}""", c=c, s=s, e=e, site=f.site_id))
    if not hours:
        return Result(None, notes=["No hay horas registradas en órdenes de producción"])
    return Result((qty / hours).quantize(Decimal("0.01")), qty, hours)


@kpi("wo_cycle_time", "operations", "Tiempo de ciclo", "Días promedio entre inicio y fin real de las órdenes "
     "terminadas en el periodo.", "Promedio(fin real − inicio real) en días", "work_orders", "days", "lower_better",
     ("site_id",), drilldown="/operaciones/ordenes")
def _wo_cycle(db, c, s, e, f):
    r = _one(db, f"""select avg(extract(epoch from actual_end - actual_start) / 86400), count(*) from work_orders
        where company_id = :c and actual_end is not null and actual_start is not null
        and cast(actual_end as date) between :s and :e {_wo(f)}""", c=c, s=s, e=e, site=f.site_id)
    return Result(Decimal(r[0]).quantize(Decimal("0.1")) if r[0] is not None else None, observations=r[1],
                  notes=[] if r[1] else ["No hay órdenes terminadas en el periodo"])


def _wo_costs(db, c, s, e, f):
    return db.execute(text(f"""select w.id, w.estimated_cost,
        coalesce((select sum(issued_cost) from work_order_materials where work_order_id = w.id), 0) +
        coalesce((select sum(hours * cost_per_hour) from work_order_time_logs where work_order_id = w.id), 0) actual
        from work_orders w where w.company_id = :c and w.status in ('completed','closed')
        and cast(w.actual_end as date) between :s and :e {_wo(f)}"""), {"c": c, "s": s, "e": e, "site": f.site_id}).all()


@kpi("wo_cost_variance", "operations", "Costo real frente a presupuestado", "Desviación del costo real de las "
     "órdenes terminadas frente a su costo estimado.", "(Σ costo real − Σ costo estimado) / Σ costo estimado × 100",
     "work_orders + materiales + tiempos", "pct", "lower_better", ("site_id",), drilldown="/operaciones/ordenes")
def _wo_var(db, c, s, e, f):
    rows = _wo_costs(db, c, s, e, f)
    est = sum((Decimal(r.estimated_cost) for r in rows), ZERO)
    act = sum((Decimal(r.actual) for r in rows), ZERO)
    return Result(_pct(act - est, est), act - est, est, len(rows),
                  [] if est else ["No hay órdenes terminadas con costo estimado"])


@kpi("operating_cost", "operations", "Costo de operación", "Costo real (materiales + mano de obra) de las órdenes "
     "terminadas en el periodo.", "Σ costo de materiales entregados + Σ horas × costo hora", "work_orders",
     "currency", "lower_better", ("site_id",), drilldown="/operaciones/ordenes")
def _opcost(db, c, s, e, f):
    rows = _wo_costs(db, c, s, e, f)
    if not rows:
        return Result(None, notes=["No hay órdenes terminadas en el periodo"])
    return Result(sum((Decimal(r.actual) for r in rows), ZERO), observations=len(rows))


def _wo_qty(db, c, s, e, f):
    return _one(db, f"""select coalesce(sum(produced_qty), 0), coalesce(sum(scrap_qty), 0),
        coalesce(sum(rework_qty), 0) from work_orders where company_id = :c and wo_type = 'production'
        and status in ('in_progress','completed','closed') and coalesce(cast(actual_end as date), :e) between :s and :e
        {_wo(f)}""", c=c, s=s, e=e, site=f.site_id)


@kpi("rework_rate", "operations", "Porcentaje de reproceso", "Unidades reprocesadas sobre unidades procesadas.",
     "Σ reproceso / Σ(producidas + desperdicio + reproceso) × 100", "work_orders", "pct", "lower_better", ("site_id",),
     drilldown="/operaciones/ordenes")
def _rework(db, c, s, e, f):
    p_, sc, rw = _wo_qty(db, c, s, e, f)
    return Result(_pct(rw, p_ + sc + rw), rw, p_ + sc + rw)


@kpi("scrap_rate", "operations", "Desperdicio", "Unidades desperdiciadas sobre unidades procesadas.",
     "Σ desperdicio / Σ(producidas + desperdicio + reproceso) × 100", "work_orders", "pct", "lower_better",
     ("site_id",), drilldown="/operaciones/ordenes")
def _scrap(db, c, s, e, f):
    p_, sc, rw = _wo_qty(db, c, s, e, f)
    return Result(_pct(sc, p_ + sc + rw), sc, p_ + sc + rw)


@kpi("wo_late", "operations", "Órdenes atrasadas", "Órdenes abiertas cuya fecha fin planificada ya pasó.",
     "Conteo de OT liberadas/en proceso con fin planificado < fecha de corte", "work_orders", "count", "lower_better",
     ("site_id",), drilldown="/operaciones/ordenes?late=1")
def _wo_late(db, c, s, e, f):
    return Result(Decimal(_scalar(db, f"""select count(*) from work_orders where company_id = :c
        and status in ('released','in_progress') and planned_end < :e {_wo(f)}""", c=c, e=e, site=f.site_id)))


@kpi("resource_utilization", "operations", "Utilización de recursos", "Horas registradas frente a horas "
     "planificadas en órdenes activas o terminadas en el periodo.", "Σ horas registradas / Σ horas planificadas × 100",
     "work_orders + work_order_time_logs", "pct", "higher_better", ("site_id",), drilldown="/operaciones/ordenes")
def _util(db, c, s, e, f):
    r = _one(db, f"""select coalesce(sum(t.hours), 0),
        (select coalesce(sum(planned_hours), 0) from work_orders where company_id = :c and planned_hours > 0
           and planned_start <= :e and coalesce(planned_end, :e) >= :s {_wo(f)})
        from work_order_time_logs t join work_orders w on w.id = t.work_order_id
        where w.company_id = :c and t.log_date between :s and :e""", c=c, s=s, e=e, site=f.site_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], notes=[] if r[1] else ["No hay horas planificadas"])


# ================================================================ CALIDAD
@kpi("nc_rate", "quality", "Tasa de no conformidad", "Cantidad rechazada sobre cantidad inspeccionada (todas las "
     "etapas).", "Σ rechazado / Σ inspeccionado × 100", "inspections", "pct", "lower_better",
     ("supplier_id", "item_id"), drilldown="/calidad/no-conformidades")
def _nc_rate(db, c, s, e, f):
    item = "and item_id = :item" if f.item_id else ""
    r = _one(db, f"""select coalesce(sum(qty_rejected), 0), coalesce(sum(quantity), 0), count(*) from inspections
        where company_id = :c and status in ('accepted','rejected','partial')
        and cast(inspected_at as date) between :s and :e {_supp(f, 'inspections')} {item}""",
             c=c, s=s, e=e, supp=f.supplier_id, item=f.item_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[2], [] if r[2] else ["Sin inspecciones cerradas"])


@kpi("lots_rejected_pct", "quality", "Lotes rechazados", "Inspecciones con rechazo total o parcial sobre "
     "inspecciones cerradas.", "Inspecciones rechazadas o parciales / Inspecciones cerradas × 100", "inspections",
     "pct", "lower_better", ("supplier_id", "item_id"), drilldown="/calidad/inspecciones")
def _lots_rej(db, c, s, e, f):
    item = "and item_id = :item" if f.item_id else ""
    r = _one(db, f"""select count(*) filter (where status in ('rejected','partial')), count(*) from inspections
        where company_id = :c and status in ('accepted','rejected','partial')
        and cast(inspected_at as date) between :s and :e {_supp(f, 'inspections')} {item}""",
             c=c, s=s, e=e, supp=f.supplier_id, item=f.item_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1])


@kpi("nc_resolution_days", "quality", "Tiempo de resolución de no conformidades", "Días promedio entre la "
     "detección y el cierre de las NC cerradas en el periodo.", "Promedio(fecha cierre − fecha detección)",
     "nonconformities", "days", "lower_better", ("supplier_id",), drilldown="/calidad/no-conformidades")
def _nc_days(db, c, s, e, f):
    r = _one(db, f"""select avg(extract(epoch from closed_at - detected_at) / 86400), count(*) from nonconformities
        where company_id = :c and status = 'closed' and cast(closed_at as date) between :s and :e
        {_supp(f, 'nonconformities')}""", c=c, s=s, e=e, supp=f.supplier_id)
    return Result(Decimal(r[0]).quantize(Decimal("0.1")) if r[0] is not None else None, observations=r[1],
                  notes=[] if r[1] else ["No hay no conformidades cerradas en el periodo"])


@kpi("quality_cost", "quality", "Costo de reprocesos y desperdicios", "Impacto económico registrado en no "
     "conformidades más el valor de bajas por desperdicio.", "Σ costo NC + Σ valor movimientos de baja (scrap)",
     "nonconformities + stock_moves(scrap)", "currency", "lower_better", ("supplier_id", "item_id"),
     drilldown="/calidad/no-conformidades")
def _qcost(db, c, s, e, f):
    item_nc = "and item_id = :item" if f.item_id else ""
    nc = Decimal(_scalar(db, f"""select coalesce(sum(cost_impact), 0) from nonconformities where company_id = :c
        and cast(detected_at as date) between :s and :e {_supp(f, 'nonconformities')} {item_nc}""",
                         c=c, s=s, e=e, supp=f.supplier_id, item=f.item_id))
    scrap = Decimal(_scalar(db, f"""select coalesce(sum(total_cost), 0) from stock_moves where company_id = :c
        and move_type = 'scrap' and cast(move_date as date) between :s and :e {item_nc}""",
                            c=c, s=s, e=e, item=f.item_id))
    return Result(nc + scrap, details=[{"no_conformidades": nc, "bajas": scrap}])


@kpi("inspection_compliance", "quality", "Cumplimiento de inspecciones", "Inspecciones con vencimiento en el periodo "
     "realizadas a tiempo.", "Inspecciones cerradas ≤ fecha límite / Inspecciones con fecha límite en el periodo × 100",
     "inspections", "pct", "higher_better", ("supplier_id",), drilldown="/calidad/inspecciones")
def _insp_comp(db, c, s, e, f):
    r = _one(db, f"""select count(*) filter (where inspected_at is not null and cast(inspected_at as date) <= due_date),
        count(*) from inspections where company_id = :c and due_date between :s and :e and status <> 'cancelled'
        {_supp(f, 'inspections')}""", c=c, s=s, e=e, supp=f.supplier_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1], [] if r[1] else ["No hay inspecciones con vencimiento"])


@kpi("nc_recurrent", "quality", "No conformidades recurrentes", "Categorías/artículos con dos o más NC en el periodo.",
     "Conteo de pares (categoría, artículo) con ≥ 2 NC", "nonconformities", "count", "lower_better", ("supplier_id",),
     drilldown="/calidad/no-conformidades")
def _nc_rec(db, c, s, e, f):
    rows = db.execute(text(f"""select coalesce(category, 'sin_categoria') cat, item_id, count(*) n
        from nonconformities where company_id = :c and cast(detected_at as date) between :s and :e
        {_supp(f, 'nonconformities')} group by 1, 2 having count(*) >= 2"""),
                      {"c": c, "s": s, "e": e, "supp": f.supplier_id}).all()
    return Result(Decimal(len(rows)), details=[dict(r._mapping) for r in rows])


@kpi("supplier_quality", "quality", "Desempeño de calidad por proveedor", "Porcentaje aceptado por proveedor; el "
     "valor principal es el del proveedor con peor desempeño.", "Por proveedor: Σ aceptado / Σ inspeccionado × 100",
     "inspections", "pct", "higher_better", ("supplier_id",), drilldown="/compras/proveedores")
def _sup_q(db, c, s, e, f):
    rows = db.execute(text(f"""select i.supplier_id, p.legal_name, sum(i.qty_accepted) acc, sum(i.quantity) tot
        from inspections i join parties p on p.id = i.supplier_id where i.company_id = :c
        and i.status in ('accepted','rejected','partial') and cast(i.inspected_at as date) between :s and :e
        {_supp(f, 'i')} group by i.supplier_id, p.legal_name"""), {"c": c, "s": s, "e": e, "supp": f.supplier_id}).all()
    details = [{"supplier_id": r.supplier_id, "supplier": r.legal_name, "acceptance_pct": _pct(r.acc, r.tot)}
               for r in rows]
    vals = [d["acceptance_pct"] for d in details if d["acceptance_pct"] is not None]
    return Result(min(vals) if vals else None, observations=len(details), details=details,
                  notes=[] if vals else ["Sin inspecciones de proveedores en el periodo"])


# ================================================================ INVENTARIO
def _inv_value_at(db, c, until: date, item_id=None) -> Decimal:
    item = "and item_id = :item" if item_id else ""
    return Decimal(_scalar(db, f"""select coalesce(sum(case when to_location_id is not null and from_location_id is null
        then total_cost when from_location_id is not null and to_location_id is null then -total_cost else 0 end), 0)
        from stock_moves where company_id = :c and cast(move_date as date) <= :d {item}""", c=c, d=until, item=item_id))


@kpi("inventory_value", "inventory", "Valoración del inventario", "Valor del inventario al corte calculado desde el "
     "libro de movimientos (costo promedio).", "Σ entradas valorizadas − Σ salidas valorizadas hasta la fecha de corte",
     "stock_moves", "currency", "neutral", ("item_id",), drilldown="/inventario/existencias")
def _inv_val(db, c, s, e, f):
    if not _scalar(db, "select exists(select 1 from stock_moves where company_id = :c)", c=c):
        return Result(None, notes=["No hay movimientos de inventario"])
    return Result(_inv_value_at(db, c, e, f.item_id))


def _cogs_moves(db, c, s, e, item_id=None) -> Decimal:
    item = "and item_id = :item" if item_id else ""
    return Decimal(_scalar(db, f"""select coalesce(sum(total_cost), 0) from stock_moves where company_id = :c
        and move_type in ('dispatch','consumption','production_issue') and cast(move_date as date) between :s and :e
        {item}""", c=c, s=s, e=e, item=item_id))


@kpi("inventory_turnover", "inventory", "Rotación de inventario", "Veces que el inventario promedio se consume en el "
     "periodo.", "Costo de salidas (despachos, consumos) / Inventario promedio((inicial + final)/2)", "stock_moves",
     "ratio", "higher_better", ("item_id",), drilldown="/inventario/kardex")
def _turn(db, c, s, e, f):
    avg = (_inv_value_at(db, c, s - timedelta(days=1), f.item_id) + _inv_value_at(db, c, e, f.item_id)) / 2
    out = _cogs_moves(db, c, s, e, f.item_id)
    if not avg:
        return Result(None, notes=["Inventario promedio en cero"])
    return Result((out / avg).quantize(Decimal("0.01")), out, avg)


@kpi("days_inventory", "inventory", "Días de inventario", "Días que alcanzaría el inventario promedio al ritmo de "
     "consumo del periodo.", "Días del periodo / Rotación", "stock_moves", "days", "lower_better", ("item_id",),
     drilldown="/inventario/kardex")
def _dio(db, c, s, e, f):
    t = _turn(db, c, s, e, f)
    if not t.value:
        return Result(None, notes=["Sin rotación calculable"])
    return Result((Decimal((e - s).days + 1) / t.value).quantize(Decimal("0.1")))


@kpi("items_below_min", "inventory", "Productos por debajo del mínimo", "Artículos inventariables cuyo disponible "
     "liberado es inferior a la existencia mínima configurada.", "Conteo de artículos con disponible < mínimo",
     "stock_balances + items", "count", "lower_better", drilldown="/inventario/reabastecimiento")
def _below(db, c, s, e, f):
    from app.modules.inventory.service import replenishment_alerts

    rows = replenishment_alerts(db, c)
    return Result(Decimal(len(rows)), details=rows[:50])


@kpi("lots_expiring", "inventory", "Materiales próximos a vencer", "Lotes con existencia que vencen en los próximos "
     "30 días o ya vencidos.", "Conteo de lotes con existencia y vencimiento ≤ fecha de corte + 30 días",
     "lots + stock_balances", "count", "lower_better", drilldown="/inventario/vencimientos")
def _expiring(db, c, s, e, f):
    from app.modules.inventory.service import expiring_lots

    rows = expiring_lots(db, c, 30, e)
    return Result(Decimal(len(rows)), details=rows[:50])


@kpi("count_differences", "inventory", "Diferencias de inventario físico", "Valor absoluto de los ajustes generados "
     "por conteos físicos aprobados en el periodo.", "Σ |valor de movimientos count_in/count_out|", "stock_moves",
     "currency", "lower_better", ("item_id",), drilldown="/inventario/conteos")
def _count_diff(db, c, s, e, f):
    item = "and item_id = :item" if f.item_id else ""
    r = _one(db, f"""select coalesce(sum(total_cost), 0), count(*) from stock_moves where company_id = :c
        and move_type in ('count_in','count_out') and cast(move_date as date) between :s and :e {item}""",
             c=c, s=s, e=e, item=f.item_id)
    counts = _scalar(db, """select count(*) from physical_counts where company_id = :c and status = 'posted'
        and count_date between :s and :e""", c=c, s=s, e=e)
    if not counts:
        return Result(None, notes=["No hay conteos físicos aprobados en el periodo"])
    return Result(Decimal(r[0]), observations=r[1])


@kpi("inventory_accuracy", "inventory", "Exactitud del inventario", "Líneas de conteo cuya cantidad física coincide "
     "con el sistema.", "Líneas sin diferencia / Líneas contadas × 100 (conteos aprobados en el periodo)",
     "physical_count_lines", "pct", "higher_better", ("item_id",), drilldown="/inventario/conteos")
def _accuracy(db, c, s, e, f):
    item = "and l.item_id = :item" if f.item_id else ""
    r = _one(db, f"""select count(*) filter (where l.counted_qty = l.system_qty), count(*) from physical_count_lines l
        join physical_counts pc on pc.id = l.count_id where pc.company_id = :c and pc.status = 'posted'
        and pc.count_date between :s and :e {item}""", c=c, s=s, e=e, item=f.item_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1], [] if r[1] else ["No hay conteos físicos aprobados"])


@kpi("stagnant_stock", "inventory", "Materiales inmovilizados", "Valor de artículos con existencia sin salidas en "
     "los últimos 90 días.", "Σ existencia × costo promedio de artículos sin salidas en 90 días",
     "stock_balances + stock_moves", "currency", "lower_better", drilldown="/inventario/existencias")
def _stagnant(db, c, s, e, f):
    rows = db.execute(text("""select i.id, i.sku, sum(b.qty_on_hand) qty, max(coalesce(ic.avg_cost, 0)) cost
        from stock_balances b join items i on i.id = b.item_id
        left join item_costs ic on ic.item_id = i.id and ic.company_id = b.company_id
        where b.company_id = :c and b.qty_on_hand > 0 and not exists (select 1 from stock_moves m
          where m.item_id = i.id and m.company_id = :c and m.from_location_id is not null and m.to_location_id is null
          and cast(m.move_date as date) > cast(:e as date) - 90)
        and exists (select 1 from stock_moves m where m.item_id = i.id and cast(m.move_date as date) <= cast(:e as date) - 90)
        group by i.id, i.sku"""), {"c": c, "e": e}).all()
    total = sum((Decimal(r.qty) * Decimal(r.cost) for r in rows), ZERO).quantize(Decimal("0.01"))
    return Result(total, observations=len(rows), details=[{"item_id": r.id, "sku": r.sku, "qty": r.qty} for r in rows][:50])


# ================================================================ LOGÍSTICA
def _disp(f):
    return " ".join(x for x in ("and d.customer_id = :cust" if f.customer_id else "",
                                "and so.site_id = :site" if f.site_id else "") if x)


@kpi("otif", "logistics", "Entregas a tiempo y completas (OTIF)", "Despachos entregados completos en o antes de la "
     "fecha prometida.", "Despachos entregados completos y a tiempo / Despachos entregados × 100",
     "dispatch_orders + dispatch_lines", "pct", "higher_better", ("customer_id", "site_id"),
     drilldown="/logistica/despachos")
def _otif(db, c, s, e, f):
    r = _one(db, f"""select count(*) filter (where d.status = 'delivered' and (d.promised_date is null
            or cast(d.delivered_at as date) <= d.promised_date)
            and not exists (select 1 from dispatch_lines dl where dl.dispatch_id = d.id
                            and dl.qty_delivered < dl.qty_requested)), count(*)
        from dispatch_orders d join sales_orders so on so.id = d.sales_order_id
        where d.company_id = :c and d.status in ('delivered','partially_delivered')
        and cast(d.delivered_at as date) between :s and :e {_disp(f)}""",
             c=c, s=s, e=e, cust=f.customer_id, site=f.site_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1], [] if r[1] else ["Sin entregas en el periodo"])


@kpi("order_to_ship_days", "logistics", "Tiempo entre pedido y despacho", "Días promedio entre la fecha del pedido y "
     "el envío.", "Promedio(fecha envío − fecha pedido)", "dispatch_orders + sales_orders", "days", "lower_better",
     ("customer_id", "site_id"), drilldown="/logistica/despachos")
def _o2s(db, c, s, e, f):
    r = _one(db, f"""select avg(cast(d.shipped_at as date) - so.order_date), count(*) from dispatch_orders d
        join sales_orders so on so.id = d.sales_order_id where d.company_id = :c and d.shipped_at is not null
        and cast(d.shipped_at as date) between :s and :e {_disp(f)}""", c=c, s=s, e=e, cust=f.customer_id,
             site=f.site_id)
    return Result(Decimal(r[0]).quantize(Decimal("0.1")) if r[0] is not None else None, observations=r[1],
                  notes=[] if r[1] else ["Sin despachos enviados en el periodo"])


@kpi("delivery_lead_days", "logistics", "Tiempo total de entrega", "Días promedio entre la fecha del pedido y la "
     "entrega al cliente.", "Promedio(fecha entrega − fecha pedido)", "dispatch_orders + sales_orders", "days",
     "lower_better", ("customer_id", "site_id"), drilldown="/logistica/despachos")
def _lead(db, c, s, e, f):
    r = _one(db, f"""select avg(cast(d.delivered_at as date) - so.order_date), count(*) from dispatch_orders d
        join sales_orders so on so.id = d.sales_order_id where d.company_id = :c and d.delivered_at is not null
        and cast(d.delivered_at as date) between :s and :e {_disp(f)}""", c=c, s=s, e=e, cust=f.customer_id,
             site=f.site_id)
    return Result(Decimal(r[0]).quantize(Decimal("0.1")) if r[0] is not None else None, observations=r[1],
                  notes=[] if r[1] else ["Sin entregas en el periodo"])


@kpi("pending_orders", "logistics", "Pedidos pendientes", "Pedidos confirmados con cantidades por despachar.",
     "Conteo de pedidos en estado confirmado o despachado parcialmente", "sales_orders", "count", "lower_better",
     ("customer_id", "site_id"), drilldown="/ventas/pedidos?status=confirmed")
def _pending(db, c, s, e, f):
    cust = "and customer_id = :cust" if f.customer_id else ""
    site = "and site_id = :site" if f.site_id else ""
    return Result(Decimal(_scalar(db, f"""select count(*) from sales_orders where company_id = :c
        and status in ('confirmed','partially_dispatched') {cust} {site}""", c=c, cust=f.customer_id, site=f.site_id)))


@kpi("logistics_cost_per_order", "logistics", "Costo logístico por pedido", "Flete promedio por despacho enviado.",
     "Σ costo de flete / Despachos enviados", "dispatch_orders", "currency", "lower_better", ("customer_id", "site_id"),
     drilldown="/logistica/despachos")
def _lcost(db, c, s, e, f):
    r = _one(db, f"""select coalesce(sum(d.freight_cost), 0), count(*) from dispatch_orders d
        join sales_orders so on so.id = d.sales_order_id where d.company_id = :c and d.shipped_at is not null
        and cast(d.shipped_at as date) between :s and :e {_disp(f)}""", c=c, s=s, e=e, cust=f.customer_id,
             site=f.site_id)
    if not r[1]:
        return Result(None, notes=["Sin despachos enviados en el periodo"])
    return Result((Decimal(r[0]) / r[1]).quantize(Decimal("0.01")), r[0], r[1], r[1])


@kpi("delivery_incidents", "logistics", "Incidencias de entrega", "Incidencias registradas en despachos en el periodo.",
     "Conteo de incidencias", "delivery_incidents", "count", "lower_better", drilldown="/logistica/incidencias")
def _incidents(db, c, s, e, f):
    return Result(Decimal(_scalar(db, """select count(*) from delivery_incidents where company_id = :c
        and cast(created_at as date) between :s and :e""", c=c, s=s, e=e)))


@kpi("returns_pct", "logistics", "Porcentaje de devoluciones", "Unidades devueltas sobre unidades despachadas.",
     "Σ devuelto / Σ enviado × 100 (despachos enviados en el periodo)", "dispatch_lines", "pct", "lower_better",
     ("customer_id", "site_id"), drilldown="/logistica/devoluciones")
def _returns(db, c, s, e, f):
    r = _one(db, f"""select coalesce(sum(dl.qty_returned), 0), coalesce(sum(dl.qty_shipped), 0) from dispatch_lines dl
        join dispatch_orders d on d.id = dl.dispatch_id join sales_orders so on so.id = d.sales_order_id
        where d.company_id = :c and cast(d.shipped_at as date) between :s and :e {_disp(f)}""",
             c=c, s=s, e=e, cust=f.customer_id, site=f.site_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], notes=[] if r[1] else ["Sin despachos enviados"])


@kpi("promise_compliance", "logistics", "Cumplimiento de la promesa de entrega", "Entregas realizadas en o antes de "
     "la fecha prometida (sin considerar completitud).", "Entregas con fecha ≤ fecha prometida / Entregas con promesa × 100",
     "dispatch_orders", "pct", "higher_better", ("customer_id", "site_id"), drilldown="/logistica/despachos")
def _promise(db, c, s, e, f):
    r = _one(db, f"""select count(*) filter (where cast(d.delivered_at as date) <= d.promised_date), count(*)
        from dispatch_orders d join sales_orders so on so.id = d.sales_order_id where d.company_id = :c
        and d.delivered_at is not null and d.promised_date is not null
        and cast(d.delivered_at as date) between :s and :e {_disp(f)}""", c=c, s=s, e=e, cust=f.customer_id,
             site=f.site_id)
    return Result(_pct(r[0], r[1]), r[0], r[1], r[1], [] if r[1] else ["Sin entregas con fecha prometida"])


# ================================================================ evaluación
def status_for(value: Decimal | None, direction: str, target, critical) -> str:
    """ok: cumple la meta; critical: cruza el umbral crítico; warning: entre la meta y el umbral crítico."""
    if value is None:
        return "no_data"
    if target is None:
        return "no_target"
    if direction == "lower_better":
        if value <= target:
            return "ok"
        return "critical" if critical is not None and value >= critical else "warning"
    if value >= target:
        return "ok"
    return "critical" if critical is not None and value <= critical else "warning"


def confidence_for(res: Result) -> str:
    if res.value is None:
        return "no_data"
    if res.observations is not None and res.observations < 5:
        return "low"
    if res.notes:
        return "medium"
    return "high"

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Modal, Page } from "../components/ui";
import { download, Json, qs } from "../lib/api";
import { fmtDate, fmtNumber } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const MODULES: [string, string][] = [
  ["", "General"], ["finance", "Finanzas"], ["management", "Gerencia"], ["purchasing", "Compras"],
  ["inventory", "Inventario"], ["quality", "Calidad"], ["logistics", "Logística"], ["operations", "Operaciones"],
];

function firstOfMonth() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

function KpiValue({ k }: { k: Json }) {
  if (k.value === null || k.value === undefined) return <span className="kpi-value muted">Pendiente de datos</span>;
  const unit = k.unit === "pct" ? " %" : k.unit === "currency" ? ` ${k.unit_label}` : ` ${k.unit_label}`;
  return <span className="kpi-value">{fmtNumber(k.value)}<small>{unit}</small></span>;
}

export function Dashboard() {
  const { company, can } = useSession();
  const nav = useNavigate();
  const [module, setModule] = useState("");
  const [start, setStart] = useState(firstOfMonth());
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [siteId, setSiteId] = useState("");
  const [costCenter, setCostCenter] = useState("");
  const [detail, setDetail] = useState<Json | null>(null);
  const sites = useOptions(can("admin.company.read") ? "/sites" : null, (x) => x.name);
  const ccs = useOptions(can("masters.config.read") ? "/cost-centers" : null, (x) => `${x.code} ${x.name}`);
  const params = { start, end, module, site_id: siteId, cost_center_id: costCenter };
  const { data, error, loading } = useFetch<Json>(`/kpi/dashboard${qs(params)}`);
  const trend = useFetch<Json[]>(detail ? `/kpi/kpis/${detail.code}/trend${qs({ months: 6, end, site_id: siteId })}` : null);

  return (
    <Page title="Dashboard ejecutivo" subtitle={`${company?.name} · indicadores calculados desde transacciones registradas`}
          actions={can("kpi.dashboard.export") && (
            <button className="secondary" onClick={() => download(`/kpi/dashboard.csv${qs(params)}`, `indicadores_${start}_${end}.csv`)}>
              Exportar</button>)}>
      <div className="filters">
        <label>Vista<select value={module} onChange={(e) => setModule(e.target.value)}>
          {MODULES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label>Desde<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>Hasta<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        {sites.length > 0 && <label>Sede<select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
          <option value="">Todas</option>{sites.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select></label>}
        {ccs.length > 0 && <label>Centro de costo<select value={costCenter} onChange={(e) => setCostCenter(e.target.value)}>
          <option value="">Todos</option>{ccs.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select></label>}
      </div>
      <Alert>{error}</Alert>
      {data && (
        <p className="summary">
          {(["ok", "warning", "critical", "no_target", "no_data"] as const).map((s) =>
            <span key={s}><Badge value={s} /> {data.summary[s]}</span>)}
          <span className="muted">Actualizado {fmtDate(data.generated_at)}</span>
        </p>
      )}
      {loading && !data && <p className="muted">Calculando indicadores…</p>}
      <div className="kpi-grid">
        {data?.kpis.map((k: Json) => (
          <button key={k.code} className={`kpi-card status-${k.status}`} onClick={() => setDetail(k)}>
            <span className="kpi-name">{k.name}</span>
            <KpiValue k={k} />
            <span className="kpi-meta">
              <Badge value={k.status} />
              {k.target != null && <span>Meta {fmtNumber(k.target)}</span>}
              {k.confidence === "low" && <span className="warn-text">Pocos datos</span>}
            </span>
          </button>
        ))}
      </div>
      {detail && (
        <Modal title={detail.name} onClose={() => setDetail(null)}>
          <p>{detail.description}</p>
          <dl className="kv">
            <div><dt>Valor</dt><dd><KpiValue k={detail} /></dd></div>
            <div><dt>Fórmula</dt><dd>{detail.formula}</dd></div>
            <div><dt>Fuente de datos</dt><dd><code>{detail.source}</code></dd></div>
            <div><dt>Periodo</dt><dd>{detail.period.start} a {detail.period.end}</dd></div>
            <div><dt>Unidad</dt><dd>{detail.unit_label}</dd></div>
            <div><dt>Frecuencia</dt><dd>{detail.frequency}</dd></div>
            <div><dt>Meta / umbral crítico</dt><dd>{detail.target ?? "Sin meta configurada"} / {detail.critical_threshold ?? "—"}</dd></div>
            <div><dt>Responsable</dt><dd>{detail.owner_id ?? "Sin asignar"}</dd></div>
            <div><dt>Confianza</dt><dd>{detail.confidence}{detail.observations != null && ` (${detail.observations} observaciones)`}</dd></div>
            <div><dt>Numerador / denominador</dt><dd>{fmtNumber(detail.numerator)} / {fmtNumber(detail.denominator)}</dd></div>
            <div><dt>Última actualización</dt><dd>{fmtDate(detail.last_updated)}</dd></div>
          </dl>
          {detail.notes?.length > 0 && <Alert kind="warning">{detail.notes.join(" · ")}</Alert>}
          <h3>Tendencia (6 meses)</h3>
          <div style={{ height: 220 }}>
            <ResponsiveContainer>
              <LineChart data={(trend.data ?? []).map((p) => ({ ...p, value: p.value === null ? null : Number(p.value) }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="period" stroke="var(--muted)" />
                <YAxis stroke="var(--muted)" />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          {detail.details && <pre className="details">{JSON.stringify(detail.details, null, 2)}</pre>}
          {detail.drilldown && <button onClick={() => nav(detail.drilldown)}>Ver transacciones de origen</button>}
        </Modal>
      )}
    </Page>
  );
}

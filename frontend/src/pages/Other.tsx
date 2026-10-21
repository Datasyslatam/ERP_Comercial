import { useState } from "react";
import { ActionButton, Alert, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { api, download, Json, post } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

// ------------------------------------------------------------------ operaciones
export function WorkOrdersPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/operations/work-orders");
  const sites = useOptions("/sites", (x) => x.name);
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const boms = useFetch<Json[]>("/operations/boms");
  const locs = useOptions("/locations?limit=500", (x) => `${x.code} ${x.name}`);
  const [creating, setCreating] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const detail = useFetch<Json>(current ? `/operations/work-orders/${current}` : null);
  const itemName = useItemNames();
  const act = async (path: string, body?: Json) => { await post(`/operations/work-orders/${current}/${path}`, body); detail.reload(); reload(); };
  return (
    <Page title="Órdenes de trabajo" subtitle="Producción, servicios y proyectos"
          actions={can("operations.work_order.create") && <button onClick={() => setCreating(true)}>Nueva orden</button>}>
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "number", title: "Número" }, { key: "wo_type", title: "Tipo" },
        { key: "project_name", title: "Proyecto" }, { key: "planned_end", title: "Fin plan" }, { key: "progress_pct", title: "Avance %", align: "right", render: (r) => fmtNumber(r.progress_pct) },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {creating && <Modal title="Nueva orden de trabajo" onClose={() => setCreating(false)}>
        <Form initial={{ wo_type: "production", planned_start: today() }} fields={[
          { name: "wo_type", label: "Tipo", type: "select", required: true, options: [["production", "Producción"], ["service", "Servicio / proyecto"], ["maintenance", "Mantenimiento"]].map(([v, l]) => ({ value: v, label: l })) },
          { name: "site_id", label: "Sede", type: "select", required: true, options: sites },
          { name: "item_id", label: "Producto a fabricar", type: "select", options: items },
          { name: "bom_id", label: "Lista de materiales", type: "select", options: (boms.data ?? []).map((b) => ({ value: b.id, label: b.code })) },
          { name: "planned_qty", label: "Cantidad planificada", type: "number" }, { name: "planned_hours", label: "Horas planificadas", type: "number" },
          { name: "production_location_id", label: "Ubicación de proceso", type: "select", options: locs },
          { name: "output_location_id", label: "Ubicación producto terminado", type: "select", options: locs },
          { name: "project_name", label: "Proyecto" }, { name: "deliverables", label: "Entregables", type: "textarea" },
          { name: "planned_start", label: "Inicio plan", type: "date" }, { name: "planned_end", label: "Fin plan", type: "date" }]}
          onSubmit={async (d) => { await post("/operations/work-orders", d); setCreating(false); reload(); }} />
      </Modal>}
      {detail.data && current && <Modal title={`Orden ${detail.data.number}`} onClose={() => setCurrent(null)}>
        <p><Badge value={detail.data.status} /> Costo estimado {fmtMoney(detail.data.summary.estimated_cost)} · real {fmtMoney(detail.data.summary.actual_cost)}
          · variación {fmtMoney(detail.data.summary.cost_variance)} · horas {fmtNumber(detail.data.summary.actual_hours)}/{fmtNumber(detail.data.summary.planned_hours)}</p>
        <DataTable rows={detail.data.materials} empty="Sin materiales" columns={[{ key: "item_id", title: "Material", render: (r) => itemName(r.item_id) },
          { key: "planned_qty", title: "Plan", align: "right", render: (r) => fmtNumber(r.planned_qty) },
          { key: "issued_qty", title: "Entregado", align: "right", render: (r) => fmtNumber(r.issued_qty) },
          { key: "issued_cost", title: "Costo", align: "right", render: (r) => fmtMoney(r.issued_cost) }]} />
        <div className="row">
          {detail.data.status === "draft" && can("operations.work_order.approve") && <ActionButton onClick={() => act("release")}>Liberar</ActionButton>}
          {detail.data.status === "completed" && can("operations.work_order.approve") && <ActionButton onClick={() => act("close")}>Cerrar con variación</ActionButton>}
          {["released", "in_progress"].includes(detail.data.status) && can("operations.work_order.approve") &&
            <ActionButton onClick={() => act("complete", {})}>Terminar</ActionButton>}
        </div>
        {["released", "in_progress"].includes(detail.data.status) && <>
          <h3>Registrar horas</h3>
          <Form initial={{ log_date: today() }} fields={[{ name: "log_date", label: "Fecha", type: "date", required: true },
            { name: "resource_name", label: "Recurso", required: true }, { name: "activity", label: "Actividad", required: true },
            { name: "hours", label: "Horas", type: "number", required: true }, { name: "cost_per_hour", label: "Costo hora", type: "number" }]}
            submitLabel="Registrar" onSubmit={(d) => act("time-logs", d)} />
          {detail.data.wo_type === "production" && <>
            <h3>Entrega de materiales</h3>
            <Form fields={[{ name: "item_id", label: "Material", type: "select", required: true, options: detail.data.materials.map((m: Json) => ({ value: m.item_id, label: itemName(m.item_id) })) },
              { name: "location_id", label: "Ubicación origen", type: "select", required: true, options: locs }, { name: "quantity", label: "Cantidad", type: "number", required: true }]}
              submitLabel="Entregar" onSubmit={(d) => act("issues", { issues: [d] })} />
            <h3>Reporte de producción</h3>
            <Form fields={[{ name: "good_qty", label: "Unidades buenas", type: "number", required: true }, { name: "scrap_qty", label: "Desperdicio", type: "number" },
              { name: "rework_qty", label: "Reproceso", type: "number" }, { name: "lot_number", label: "Lote" }, { name: "expiry_date", label: "Vencimiento", type: "date" },
              { name: "complete", label: "Terminar la orden", type: "checkbox" }]} submitLabel="Reportar" onSubmit={(d) => act("output", d)} />
          </>}
        </>}
      </Modal>}
    </Page>
  );
}

// ------------------------------------------------------------------ importaciones
export function ImportsPage() {
  const { can } = useSession();
  const entities = useFetch<Json>("/imports/entities");
  const jobs = useFetch<Json[]>("/imports/jobs");
  const batches = useFetch<Json[]>(can("imports.opening.read") ? "/imports/opening-batches" : null);
  const [entity, setEntity] = useState("parties");
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState("");
  const [batchId, setBatchId] = useState("");
  const [current, setCurrent] = useState<number | null>(null);
  const rows = useFetch<Json[]>(current ? `/imports/jobs/${current}/rows?status=invalid` : null);
  const [error, setError] = useState<string | null>(null);

  async function upload() {
    if (!file) return;
    setError(null);
    const fd = new FormData();
    fd.append("entity", entity);
    fd.append("file", file);
    if (mapping) fd.append("mapping", mapping);
    if (batchId) fd.append("opening_batch_id", batchId);
    try {
      const job = await api("POST", "/imports/jobs", fd);
      setCurrent(job.id);
      jobs.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Page title="Importación de datos reales" subtitle="Plantilla → carga → validación previa → corrección → importación → conciliación">
      <div className="filters">
        <label>Entidad<select value={entity} onChange={(e) => setEntity(e.target.value)}>
          {Object.keys(entities.data ?? {}).map((k) => <option key={k} value={k}>{k}</option>)}</select></label>
        <button className="secondary" onClick={() => download(`/imports/templates/${entity}`, `plantilla_${entity}.xlsx`)}>Descargar plantilla</button>
        <label>Archivo (.csv, .xlsx)<input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <label>Mapeo de columnas (JSON opcional)<input placeholder='{"NIT":"tax_id"}' value={mapping} onChange={(e) => setMapping(e.target.value)} /></label>
        {entity.startsWith("opening_") && <label>Lote de saldos iniciales<select value={batchId} onChange={(e) => setBatchId(e.target.value)}>
          <option value="">—</option>{(batches.data ?? []).filter((b) => b.status === "draft").map((b) => <option key={b.id} value={b.id}>#{b.id} {b.kind} al {b.cutoff_date}</option>)}</select></label>}
        {can("imports.job.create") && <button onClick={upload} disabled={!file}>Cargar y validar</button>}
      </div>
      <Alert>{error}</Alert>
      <DataTable rows={jobs.data} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "id", title: "#" }, { key: "entity", title: "Entidad" },
        { key: "filename", title: "Archivo" }, { key: "created_at", title: "Fecha", render: (r) => fmtDate(r.created_at) },
        { key: "counts", title: "Filas (válidas / inválidas / importadas)", render: (r) => `${r.total_rows} (${r.valid_rows} / ${r.invalid_rows} / ${r.imported_rows})` },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "a", title: "", render: (r) => can("imports.job.post") && !["imported", "cancelled"].includes(r.status) &&
          <ActionButton onClick={async () => { await post(`/imports/jobs/${r.id}/commit`); jobs.reload(); rows.reload(); }}>Importar filas válidas</ActionButton> }]} />
      {current && <>
        <h3>Filas con errores del lote #{current}</h3>
        <DataTable rows={rows.data} empty="Sin errores" columns={[{ key: "row_number", title: "Fila" },
          { key: "errors", title: "Errores", render: (r) => r.errors.join("; ") },
          { key: "data", title: "Datos (editar y revalidar)", render: (r) => <RowEditor row={r} onSaved={() => { rows.reload(); jobs.reload(); }} /> }]} />
      </>}
      {can("imports.opening.create") && <>
        <h3>Lotes de saldos iniciales</h3>
        <Form fields={[{ name: "kind", label: "Tipo", type: "select", required: true, options: [["stock", "Inventario"], ["receivables", "Cuentas por cobrar"], ["payables", "Cuentas por pagar"]].map(([v, l]) => ({ value: v, label: l })) },
          { name: "cutoff_date", label: "Fecha de corte", type: "date", required: true },
          { name: "source_description", label: "Origen documentado (sistema, informe, responsable)", type: "textarea", required: true }]}
          submitLabel="Crear lote" onSubmit={async (d) => { await post("/imports/opening-batches", d); batches.reload(); }} />
        <DataTable rows={batches.data} columns={[{ key: "id", title: "#" }, { key: "kind", title: "Tipo" }, { key: "cutoff_date", title: "Corte" },
          { key: "source_description", title: "Origen" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
          { key: "a", title: "", render: (r) => <span className="row">
            {r.status === "draft" && can("imports.opening.approve") && <ActionButton onClick={async () => { await post(`/imports/opening-batches/${r.id}/approve`); batches.reload(); }}>Aprobar</ActionButton>}
            {r.status === "approved" && can("imports.opening.post") && <ActionButton onClick={async () => { await post(`/imports/opening-batches/${r.id}/post`); batches.reload(); }}>Contabilizar</ActionButton>}
          </span> }]} />
      </>}
    </Page>
  );
}

function RowEditor({ row, onSaved }: { row: Json; onSaved: () => void }) {
  const [text, setText] = useState(JSON.stringify(row.data));
  const [err, setErr] = useState<string | null>(null);
  return <span className="row">
    <input aria-label="Datos de la fila" value={text} onChange={(e) => setText(e.target.value)} style={{ minWidth: 280 }} />
    <button className="secondary" onClick={async () => {
      try { await api("PATCH", `/imports/rows/${row.id}`, { data: JSON.parse(text) }); onSaved(); } catch (e) { setErr((e as Error).message); }
    }}>Guardar</button>{err && <span className="error-inline">{err}</span>}
  </span>;
}

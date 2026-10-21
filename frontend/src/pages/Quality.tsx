import { useState } from "react";
import { ActionButton, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber, label } from "../lib/format";
import { useFetch, useItemNames, useLookup, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

export function InspectionsPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("pending");
  const { data, reload } = useFetch<Json>(`/quality/inspections${qs({ status })}`);
  const [current, setCurrent] = useState<number | null>(null);
  const detail = useFetch<Json>(current ? `/quality/inspections/${current}` : null);
  const itemName = useItemNames();
  const lotName = useLookup("/inventory/lots?limit=500", (x) => x.lot_number);
  return (
    <Page title="Inspecciones de calidad" actions={<select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
      <option value="">Todas</option>{["pending", "accepted", "partial", "rejected"].map((s) => <option key={s} value={s}>{s}</option>)}</select>}>
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "number", title: "Número" },
        { key: "stage", title: "Etapa" }, { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
        { key: "lot_id", title: "Lote", render: (r) => lotName(r.lot_id) },
        { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
        { key: "due_date", title: "Fecha límite" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {detail.data && current && (
        <Modal title={`Inspección ${detail.data.number}`} onClose={() => setCurrent(null)}>
          <p>Cantidad a inspeccionar: <strong>{fmtNumber(detail.data.quantity)}</strong> · Plan: {detail.data.plan?.name ?? "sin plan asociado"}</p>
          {detail.data.status === "pending" && can("quality.inspection.approve") ? (
            <Form fields={[
              ...(detail.data.plan?.characteristics ?? []).map((c: Json) => c.kind === "boolean"
                ? { name: `c_${c.id}`, label: `${c.name}${c.is_critical ? " (crítica)" : ""} — conforme`, type: "checkbox" as const }
                : { name: `c_${c.id}`, label: `${c.name} [${c.lower_limit ?? "−∞"} … ${c.upper_limit ?? "∞"}] ${c.unit ?? ""}${c.is_critical ? " (crítica)" : ""}`,
                    type: "number" as const, required: true }),
              { name: "qty_accepted", label: "Cantidad aceptada", type: "number", required: true },
              { name: "qty_rejected", label: "Cantidad rechazada", type: "number", required: true },
              { name: "notes", label: "Observaciones / evidencias", type: "textarea" },
              { name: "nc_description", label: "Descripción de la no conformidad (si hay rechazo)", type: "textarea" }]}
              onSubmit={async (d) => {
                const results = (detail.data.plan?.characteristics ?? []).map((c: Json) => c.kind === "boolean"
                  ? { characteristic_id: c.id, bool_value: !!d[`c_${c.id}`] } : { characteristic_id: c.id, numeric_value: d[`c_${c.id}`] });
                await post(`/quality/inspections/${current}/result`, { qty_accepted: d.qty_accepted, qty_rejected: d.qty_rejected,
                  notes: d.notes, nc_description: d.nc_description, results });
                setCurrent(null); reload();
              }} />
          ) : (
            <DataTable rows={detail.data.results} columns={[{ key: "name", title: "Característica" },
              { key: "v", title: "Resultado", render: (r) => r.numeric_value ?? (r.bool_value === null ? r.text_value : r.bool_value ? "Sí" : "No") },
              { key: "is_conforming", title: "Conforme", render: (r) => <Badge value={r.is_conforming ? "ok" : "critical"} /> }]} />
          )}
        </Modal>
      )}
    </Page>
  );
}

const NEXT: Record<string, string> = { open: "analysis", analysis: "action", action: "verification", verification: "closed" };

export function NonConformitiesPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/quality/nonconformities");
  const [current, setCurrent] = useState<Json | null>(null);
  const [creating, setCreating] = useState(false);
  return (
    <Page title="No conformidades y CAPA" actions={can("quality.nonconformity.create") && <button onClick={() => setCreating(true)}>Registrar NC</button>}>
      <DataTable rows={data?.items} onRowClick={setCurrent} columns={[{ key: "number", title: "Número" }, { key: "source", title: "Origen" },
        { key: "severity", title: "Severidad" }, { key: "description", title: "Descripción" },
        { key: "cost_impact", title: "Costo", align: "right", render: (r) => fmtMoney(r.cost_impact) },
        { key: "detected_at", title: "Detectada", render: (r) => fmtDate(r.detected_at) }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {creating && <Modal title="Nueva no conformidad" onClose={() => setCreating(false)}>
        <Form fields={[{ name: "source", label: "Origen", type: "select", required: true, options: ["customer", "internal", "supplier", "delivery", "production"].map((v) => ({ value: v, label: v })) },
          { name: "severity", label: "Severidad", type: "select", options: ["minor", "major", "critical"].map((v) => ({ value: v, label: v })) },
          { name: "category", label: "Categoría (para recurrencia)" }, { name: "description", label: "Descripción", type: "textarea", required: true },
          { name: "quantity_affected", label: "Cantidad afectada", type: "number" }, { name: "cost_impact", label: "Costo estimado", type: "number" }]}
          onSubmit={async (d) => { await post("/quality/nonconformities", d); setCreating(false); reload(); }} />
      </Modal>}
      {current && (
        <Modal title={`No conformidad ${current.number}`} onClose={() => setCurrent(null)}>
          <p>{current.description}</p>
          <p>Causa raíz: {current.root_cause ?? "pendiente"}</p>
          <DataTable rows={current.actions} empty="Sin acciones" columns={[{ key: "action_type", title: "Tipo" }, { key: "description", title: "Acción" },
            { key: "due_date", title: "Vence" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
            { key: "a", title: "", render: (r) => r.status === "open" && <ActionButton onClick={async () => {
              await post(`/quality/actions/${r.id}/status`, { status: "done" }); setCurrent(null); reload(); }}>Marcar ejecutada</ActionButton> }]} />
          {current.status !== "closed" && can("quality.nonconformity.approve") && <>
            {current.status === "analysis" && <Form fields={[{ name: "root_cause", label: "Análisis de causa raíz", type: "textarea", required: true },
              { name: "root_cause_method", label: "Método (5 porqués, Ishikawa)" }]} submitLabel="Registrar causa y pasar a acciones"
              onSubmit={async (d) => { await post(`/quality/nonconformities/${current.id}/advance`, { to_status: "action", ...d }); setCurrent(null); reload(); }} />}
            {current.status !== "analysis" && <ActionButton onClick={async () => {
              await post(`/quality/nonconformities/${current.id}/advance`, { to_status: NEXT[current.status] }); setCurrent(null); reload(); }}>
              Avanzar a {NEXT[current.status]}</ActionButton>}
            {["action", "analysis"].includes(current.status) && <Form fields={[{ name: "action_type", label: "Tipo", type: "select", required: true,
              options: ["containment", "corrective", "preventive"].map((v) => ({ value: v, label: v })) },
              { name: "description", label: "Acción", required: true }, { name: "due_date", label: "Fecha compromiso", type: "date" }]} submitLabel="Agregar acción"
              onSubmit={async (d) => { await post(`/quality/nonconformities/${current.id}/actions`, d); setCurrent(null); reload(); }} />}
          </>}
        </Modal>
      )}
    </Page>
  );
}

// ------------------------------------------------------------------ planes de inspección
const STAGES: Record<string, string> = { receiving: "Recepción", in_process: "En proceso", final: "Producto terminado", dispatch: "Despacho" };
const KINDS: Record<string, string> = { numeric: "Numérica (con tolerancia)", boolean: "Cumple / no cumple", text: "Observación" };

interface Char { name: string; kind: string; target: string; lower_limit: string; upper_limit: string; unit: string; is_critical: boolean }
const emptyChar = (): Char => ({ name: "", kind: "boolean", target: "", lower_limit: "", upper_limit: "", unit: "", is_critical: false });

export function InspectionPlansPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json[]>("/quality/plans");
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const itemName = useItemNames();
  const [creating, setCreating] = useState(false);
  const [chars, setChars] = useState<Char[]>([emptyChar()]);
  const [current, setCurrent] = useState<Json | null>(null);
  const setC = (i: number, k: keyof Char, v: string | boolean) => setChars(chars.map((c, j) => (j === i ? { ...c, [k]: v } : c)));
  return (
    <Page title="Planes de inspección" subtitle="Características, tolerancias y criterios de aceptación por artículo o categoría"
          actions={can("quality.plan.admin") && <button onClick={() => setCreating(true)}>Nuevo plan</button>}>
      <DataTable rows={data} onRowClick={setCurrent} empty="Sin planes de inspección" columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" },
        { key: "stage", title: "Etapa", render: (r) => STAGES[r.stage] ?? r.stage },
        { key: "item_id", title: "Artículo", render: (r) => r.item_id ? itemName(r.item_id) : "Por categoría" },
        { key: "characteristics", title: "Características", align: "right", render: (r) => r.characteristics.length },
        { key: "sampling_rule", title: "Muestreo", render: (r) => r.sampling_rule ?? "—" }]} />
      {current && <Modal title={`Plan ${current.code} · ${current.name}`} onClose={() => setCurrent(null)}>
        <DataTable rows={current.characteristics} columns={[{ key: "name", title: "Característica" }, { key: "kind", title: "Tipo", render: (r) => KINDS[r.kind] },
          { key: "range", title: "Tolerancia", render: (r) => r.kind === "numeric" ? `${r.lower_limit ?? "—"} a ${r.upper_limit ?? "—"} ${r.unit ?? ""}` : r.acceptance_criteria ?? "—" },
          { key: "is_critical", title: "Crítica", render: (r) => r.is_critical ? <Badge value="critical" /> : "" }]} />
      </Modal>}
      {creating && <Modal title="Nuevo plan de inspección" onClose={() => setCreating(false)}>
        <div className="lines"><table><thead><tr><th>Característica</th><th>Tipo</th><th>Mín.</th><th>Objetivo</th><th>Máx.</th><th>Unidad</th><th>Crítica</th><th /></tr></thead>
          <tbody>{chars.map((c, i) => <tr key={i}>
            <td><input aria-label="Característica" value={c.name} onChange={(e) => setC(i, "name", e.target.value)} /></td>
            <td><select aria-label="Tipo de característica" value={c.kind} onChange={(e) => setC(i, "kind", e.target.value)}>
              {Object.entries(KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></td>
            {(["lower_limit", "target", "upper_limit"] as const).map((k) => <td key={k}><input type="number" step="any" aria-label={k} style={{ width: 90 }}
              disabled={c.kind !== "numeric"} value={c[k]} onChange={(e) => setC(i, k, e.target.value)} /></td>)}
            <td><input aria-label="Unidad" style={{ width: 70 }} value={c.unit} onChange={(e) => setC(i, "unit", e.target.value)} /></td>
            <td><input type="checkbox" aria-label="Crítica" checked={c.is_critical} onChange={(e) => setC(i, "is_critical", e.target.checked)} /></td>
            <td>{chars.length > 1 && <button type="button" className="secondary" onClick={() => setChars(chars.filter((_, j) => j !== i))}>Quitar</button>}</td>
          </tr>)}</tbody></table>
          <button type="button" className="secondary" onClick={() => setChars([...chars, emptyChar()])}>+ Característica</button></div>
        <Form fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
          { name: "stage", label: "Etapa", type: "select", required: true, options: Object.entries(STAGES).map(([v, l]) => ({ value: v, label: l })) },
          { name: "item_id", label: "Artículo (vacío = por categoría)", type: "select", options: items },
          { name: "sampling_rule", label: "Regla de muestreo (p. ej. 10 % del lote, mín. 5 unidades)" }]}
          onSubmit={async (d) => {
            const characteristics = chars.filter((c) => c.name.trim()).map((c) => ({ name: c.name, kind: c.kind, unit: c.unit || null, is_critical: c.is_critical,
              target: c.target || null, lower_limit: c.lower_limit || null, upper_limit: c.upper_limit || null }));
            await post("/quality/plans", { ...d, characteristics });
            setCreating(false); setChars([emptyChar()]); reload();
          }} />
      </Modal>}
    </Page>
  );
}

// ------------------------------------------------------------------ lotes e historial de calidad
export function LotsQualityPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("");
  const [itemId, setItemId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const suppliers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const itemName = useItemNames();
  const lots = useFetch<Json>(`/inventory/lots${qs({ status, item_id: itemId, limit: 300 })}`);
  const [lot, setLot] = useState<Json | null>(null);
  const historyPath = lot ? `/quality/history?lot_id=${lot.id}` : itemId || supplierId ? `/quality/history${qs({ item_id: itemId, supplier_id: supplierId })}` : null;
  const history = useFetch<Json>(historyPath);
  const [changing, setChanging] = useState(false);
  return (
    <Page title="Lotes y trazabilidad de calidad" subtitle="Estado de liberación de lotes e historial de inspecciones y no conformidades">
      <div className="filters">
        <label>Artículo<select value={itemId} onChange={(e) => { setItemId(e.target.value); setLot(null); }}><option value="">Todos</option>
          {items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
        <label>Proveedor (historial)<select value={supplierId} onChange={(e) => { setSupplierId(e.target.value); setLot(null); }}><option value="">—</option>
          {suppliers.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
        <label>Estado del lote<select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Todos</option>
          {["released", "quarantine", "blocked"].map((s) => <option key={s} value={s}>{label(s)}</option>)}</select></label>
      </div>
      <DataTable rows={lots.data?.items} onRowClick={setLot} empty="Sin lotes" columns={[{ key: "lot_number", title: "Lote" },
        { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) }, { key: "expiry_date", title: "Vence", render: (r) => r.expiry_date ?? "—" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {lot && <div className="row"><h3>Lote {lot.lot_number}</h3><Badge value={lot.status} />
        {can("quality.inspection.approve") && <button className="secondary" onClick={() => setChanging(true)}>Cambiar estado</button>}
        <button className="secondary" onClick={() => setLot(null)}>Ver historial del filtro</button></div>}
      {history.data && <>
        <h3>Inspecciones</h3>
        <DataTable rows={history.data.inspections} empty="Sin inspecciones" columns={[{ key: "number", title: "Número" }, { key: "stage", title: "Etapa", render: (r) => STAGES[r.stage] ?? r.stage },
          { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) }, { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
          { key: "qty_accepted", title: "Aceptado", align: "right", render: (r) => fmtNumber(r.qty_accepted) },
          { key: "qty_rejected", title: "Rechazado", align: "right", render: (r) => fmtNumber(r.qty_rejected) },
          { key: "status", title: "Resultado", render: (r) => <Badge value={r.status} /> }]} />
        <h3>No conformidades</h3>
        <DataTable rows={history.data.nonconformities} empty="Sin no conformidades" columns={[{ key: "number", title: "Número" }, { key: "source", title: "Origen" },
          { key: "description", title: "Descripción" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
          { key: "actions", title: "Acciones CAPA", align: "right", render: (r) => r.actions?.length ?? 0 }]} />
      </>}
      {!historyPath && <p className="muted">Seleccione un lote, un artículo o un proveedor para ver su historial de calidad.</p>}
      {changing && lot && <Modal title={`Estado del lote ${lot.lot_number}`} onClose={() => setChanging(false)}>
        <p className="muted">Un lote en cuarentena o bloqueado no se reserva ni se despacha.</p>
        <Form initial={{ status: lot.status }} fields={[{ name: "status", label: "Nuevo estado", type: "select", required: true,
          options: ["released", "quarantine", "blocked"].map((s) => ({ value: s, label: label(s) })) },
          { name: "reason", label: "Motivo", type: "textarea", required: true }]}
          onSubmit={async (d) => { const r = await post(`/quality/lots/${lot.id}/status`, d); setChanging(false); setLot(r); lots.reload(); }} />
      </Modal>}
    </Page>
  );
}

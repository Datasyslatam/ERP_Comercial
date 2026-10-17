import { useState } from "react";
import { ActionButton, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useLookup } from "../lib/hooks";
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

import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ResourcePage } from "../components/ResourcePage";
import { ActionButton, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { Json, patch, post, qs } from "../lib/api";
import { fmtDate, fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useLookup, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

export const INCIDENT_TYPES: Record<string, string> = {
  damaged: "Mercancía averiada", missing: "Faltante", late: "Entrega tardía", rejected: "Rechazada por el cliente",
  address: "Dirección errada", other: "Otra",
};

export function DispatchDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can } = useSession();
  const { data: d, reload } = useFetch<Json>(`/logistics/dispatches/${id}`);
  const carriers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const routes = useOptions(can("logistics.route.read") ? "/routes" : null, (x) => `${x.code} ${x.name}`);
  const locations = useOptions("/locations?limit=500", (x) => `${x.code} ${x.name}`);
  const itemName = useItemNames();
  const [step, setStep] = useState<string | null>(null);
  if (!d) return <p className="muted">Cargando…</p>;
  const call = async (path: string, body?: Json) => { await post(`/logistics/dispatches/${d.id}/${path}`, body); setStep(null); reload(); };
  const canPost = can("logistics.dispatch.post");
  const shipped = ["shipped", "delivered", "partially_delivered"].includes(d.status);
  const returnable: Json[] = d.lines.filter((l: Json) => Number(l.qty_shipped) - Number(l.qty_returned) > 0);
  return (
    <Page title={`Despacho ${d.number}`} actions={<>
      <Badge value={d.status} />
      {["draft", "picking", "picked", "packed"].includes(d.status) && can("logistics.dispatch.create") &&
        <button className="secondary" onClick={() => setStep("plan")}>Planificar</button>}
      {d.status === "draft" && <ActionButton onClick={() => call("start-picking")}>Iniciar picking</ActionButton>}
      {d.status === "picking" && <button onClick={() => setStep("pick")}>Confirmar picking</button>}
      {d.status === "picked" && <button onClick={() => setStep("pack")}>Empacar</button>}
      {d.status === "packed" && canPost && <button onClick={() => setStep("ship")}>Enviar</button>}
      {d.status === "shipped" && canPost && <button onClick={() => setStep("deliver")}>Registrar entrega</button>}
      {d.status !== "cancelled" && can("logistics.dispatch.create") &&
        <button className="secondary" onClick={() => setStep("incident")}>Reportar incidencia</button>}
      {shipped && returnable.length > 0 && can("logistics.return.post") &&
        <button className="secondary" onClick={() => setStep("return")}>Registrar devolución</button>}
      {shipped && can("einvoicing.invoice.create") &&
        <ActionButton onClick={async () => { const inv = await post("/einvoicing/invoices/from-dispatch", { dispatch_id: d.id }); nav(`/facturacion?focus=${inv.id}`); }}>Facturar</ActionButton>}
    </>}>
      <KeyValues data={d} keys={[["delivery_address", "Dirección"], ["promised_date", "Fecha prometida"], ["planned_ship_date", "Envío planificado"],
        ["vehicle_plate", "Placa"], ["driver_name", "Conductor"], ["tracking_number", "Guía"], ["packages_count", "Bultos"],
        ["pod_received_by", "Recibió"], ["delivered_at", "Entregado", fmtDate]]} />
      <DataTable rows={d.lines} columns={[{ key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
        ...["qty_requested", "qty_picked", "qty_shipped", "qty_delivered", "qty_returned", "qty_invoiced"].map((k) => ({
          key: k, title: { qty_requested: "Solicitado", qty_picked: "Preparado", qty_shipped: "Enviado", qty_delivered: "Entregado",
            qty_returned: "Devuelto", qty_invoiced: "Facturado" }[k] as string, align: "right" as const, render: (r: Json) => fmtNumber(r[k]) }))]} />

      <h3>Seguimiento</h3>
      <DataTable rows={d.events} columns={[{ key: "event_time", title: "Fecha", render: (r) => fmtDate(r.event_time) },
        { key: "status", title: "Evento" }, { key: "location_text", title: "Lugar" }, { key: "notes", title: "Notas" }]} />
      {["shipped", "partially_delivered"].includes(d.status) && can("logistics.dispatch.create") &&
        <Form fields={[{ name: "status", label: "Nuevo evento de seguimiento", required: true, placeholder: "en tránsito, en reparto…" },
          { name: "location_text", label: "Lugar" }, { name: "notes", label: "Notas" }]} submitLabel="Agregar evento"
          onSubmit={(v) => call("events", v)} />}

      <h3>Incidencias</h3>
      <DataTable rows={d.incidents} empty="Sin incidencias" columns={[
        { key: "incident_type", title: "Tipo", render: (r) => INCIDENT_TYPES[r.incident_type] ?? r.incident_type },
        { key: "description", title: "Descripción" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status === "resolved" ? "closed" : "open"} /> },
        { key: "resolution", title: "Solución" },
        { key: "a", title: "", render: (r) => r.status === "open" && can("logistics.dispatch.create") && <ActionButton onClick={async () => {
          const resolution = window.prompt("Solución aplicada");
          if (resolution) { await post(`/logistics/incidents/${r.id}/resolve`, { resolution }); reload(); }
        }}>Resolver</ActionButton> }]} />

      <h3>Devoluciones</h3>
      <DataTable rows={d.returns} empty="Sin devoluciones" columns={[{ key: "number", title: "Número" }, { key: "return_date", title: "Fecha" },
        { key: "reason", title: "Motivo" },
        { key: "lines", title: "Artículos", render: (r) => r.lines.map((l: Json) =>
          `${itemName(l.item_id)} × ${fmtNumber(l.quantity)} (${l.condition === "damaged" ? "dañado" : "revendible"})`).join("; ") }]} />

      {step === "pick" && <Modal title="Verificación de picking" onClose={() => setStep(null)}>
        <Form fields={d.lines.map((l: Json) => ({ name: `p_${l.id}`, label: `${itemName(l.item_id)} (solicitado ${fmtNumber(l.qty_requested)})`, type: "number" as const, required: true }))}
          initial={Object.fromEntries(d.lines.map((l: Json) => [`p_${l.id}`, l.qty_requested]))}
          onSubmit={(v) => call("picking", { picks: d.lines.map((l: Json) => ({ dispatch_line_id: l.id, qty_picked: v[`p_${l.id}`] })) })} />
      </Modal>}
      {step === "pack" && <Modal title="Empaque" onClose={() => setStep(null)}>
        <Form fields={[{ name: "packages_count", label: "Bultos", type: "number", required: true }, { name: "gross_weight_kg", label: "Peso bruto (kg)", type: "number" }]}
          onSubmit={(v) => call("pack", { ...v, packages_count: Number(v.packages_count) })} />
      </Modal>}
      {step === "ship" && <Modal title="Envío" onClose={() => setStep(null)}>
        <Form initial={{ carrier_id: d.carrier_id, route_id: d.route_id }} fields={[
          { name: "carrier_id", label: "Transportista", type: "select", options: carriers },
          { name: "route_id", label: "Ruta", type: "select", options: routes }, { name: "vehicle_plate", label: "Placa" },
          { name: "driver_name", label: "Conductor" }, { name: "tracking_number", label: "Guía" },
          { name: "freight_cost", label: "Costo del flete", type: "number" }]}
          onSubmit={(v) => call("ship", v)} />
      </Modal>}
      {step === "deliver" && <Modal title="Evidencia de entrega" onClose={() => setStep(null)}>
        <Form fields={[{ name: "received_by", label: "Recibido por", required: true }, { name: "notes", label: "Observaciones", type: "textarea" },
          ...d.lines.map((l: Json) => ({ name: `d_${l.id}`, label: `Entregado: ${itemName(l.item_id)}`, type: "number" as const }))]}
          initial={Object.fromEntries(d.lines.map((l: Json) => [`d_${l.id}`, l.qty_shipped]))}
          onSubmit={(v) => call("deliver", { received_by: v.received_by, notes: v.notes,
            lines: d.lines.map((l: Json) => ({ dispatch_line_id: l.id, qty_delivered: v[`d_${l.id}`] ?? l.qty_shipped })) })} />
        <p className="muted">El soporte firmado puede adjuntarse en Adjuntos (entidad dispatch_orders).</p>
      </Modal>}
      {step === "plan" && <Modal title="Planificación del despacho" onClose={() => setStep(null)}>
        <Form initial={{ route_id: d.route_id, carrier_id: d.carrier_id, planned_ship_date: d.planned_ship_date, delivery_address: d.delivery_address }}
          fields={[{ name: "route_id", label: "Ruta", type: "select", options: routes },
            { name: "carrier_id", label: "Transportista", type: "select", options: carriers },
            { name: "planned_ship_date", label: "Fecha de envío planificada", type: "date" },
            { name: "delivery_address", label: "Dirección de entrega" }]}
          onSubmit={async (v) => { await patch(`/logistics/dispatches/${d.id}/plan`, v); setStep(null); reload(); }} />
      </Modal>}
      {step === "incident" && <Modal title="Incidencia de entrega" onClose={() => setStep(null)}>
        <Form fields={[{ name: "incident_type", label: "Tipo", type: "select", required: true,
          options: Object.entries(INCIDENT_TYPES).map(([value, label]) => ({ value, label })) },
          { name: "description", label: "Descripción", type: "textarea", required: true }]}
          onSubmit={(v) => call("incidents", v)} />
      </Modal>}
      {step === "return" && <ReturnModal dispatch={d} lines={returnable} locations={locations} itemName={itemName}
        onClose={() => setStep(null)} onDone={() => { setStep(null); reload(); }} />}
    </Page>
  );
}

/** Devolución de cliente: reingresa al costo original del despacho; lo dañado genera una no conformidad. */
export function ReturnModal({ dispatch, lines, locations, itemName, onClose, onDone }: {
  dispatch: Json; lines: Json[]; locations: { value: number; label: string }[]; itemName: (id: unknown) => string;
  onClose: () => void; onDone: () => void;
}) {
  return (
    <Modal title={`Devolución del despacho ${dispatch.number}`} onClose={onClose}>
      <Form initial={{ return_date: today() }} fields={[
        { name: "location_id", label: "Ubicación de reingreso", type: "select", required: true, options: locations },
        { name: "return_date", label: "Fecha", type: "date", required: true },
        { name: "reason", label: "Motivo", required: true },
        ...lines.flatMap((l) => [
          { name: `q_${l.id}`, label: `${itemName(l.item_id)}: cantidad (máx. ${fmtNumber(Number(l.qty_shipped) - Number(l.qty_returned))})`,
            type: "number" as const },
          { name: `c_${l.id}`, label: `${itemName(l.item_id)}: estado`, type: "select" as const,
            options: [{ value: "resellable", label: "Revendible" }, { value: "damaged", label: "Dañado" }] }])]}
        submitLabel="Registrar devolución"
        onSubmit={async (v) => {
          const out = lines.filter((l) => Number(v[`q_${l.id}`]) > 0).map((l) => ({
            dispatch_line_id: l.id, quantity: v[`q_${l.id}`], condition: v[`c_${l.id}`] ?? "resellable" }));
          if (!out.length) throw new Error("Indique al menos una cantidad a devolver");
          await post(`/logistics/dispatches/${dispatch.id}/returns`, {
            location_id: v.location_id, return_date: v.return_date, reason: v.reason, lines: out });
          onDone();
        }} />
      <p className="muted">Lo marcado como dañado genera una no conformidad. Para reconocer el valor al cliente emita una nota crédito desde Facturación.</p>
    </Modal>
  );
}

/** Rutas de entrega (maestro) y plan de entregas del día agrupado por ruta. */
export function RoutesPlanPage() {
  const { can } = useSession();
  const [on, setOn] = useState(today());
  const plan = useFetch<Json[]>(`/logistics/delivery-plan${qs({ on })}`);
  const routeName = useLookup(can("logistics.route.read") ? "/routes" : null, (x) => `${x.code} · ${x.name}`);
  const sites = useOptions("/sites", (x) => x.name);
  const nav = useNavigate();
  return (
    <>
      <Page title="Planificación de entregas" subtitle="Despachos preparados, empacados o enviados programados para la fecha, agrupados por ruta"
            actions={<input type="date" aria-label="Fecha del plan" value={on} onChange={(e) => setOn(e.target.value)} />}>
        {(plan.data ?? []).length === 0 && <p className="muted">No hay despachos con envío planificado para esta fecha.</p>}
        {(plan.data ?? []).map((g) => (
          <div key={g.route_id ?? "sin-ruta"}>
            <h3>{g.route_id ? routeName(g.route_id) : "Sin ruta asignada"} · {g.count} despachos</h3>
            <DataTable rows={g.dispatches} onRowClick={(r) => nav(`/logistica/despachos/${r.id}`)} columns={[
              { key: "number", title: "Despacho" }, { key: "delivery_address", title: "Dirección" },
              { key: "promised_date", title: "Prometido" }, { key: "packages_count", title: "Bultos", align: "right" },
              { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
          </div>
        ))}
      </Page>
      <ResourcePage title="Rutas de entrega" path="/routes" writePerm="logistics.route.admin"
        fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
          { name: "site_id", label: "Sede de salida", type: "select", options: sites },
          { name: "standard_lead_days", label: "Días estándar de entrega", type: "number" },
          { name: "description", label: "Zonas / descripción", type: "textarea" }]}
        columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" },
          { key: "standard_lead_days", title: "Días", align: "right" }, { key: "description", title: "Zonas" }]} />
    </>
  );
}

/** Listado de incidencias de entrega de la empresa (abiertas por defecto). */
export function IncidentsPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("open");
  const { data, reload } = useFetch<Json>(`/logistics/incidents${qs({ status })}`);
  const nav = useNavigate();
  return (
    <Page title="Incidencias de entrega" actions={<select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
      <option value="open">Abiertas</option><option value="resolved">Resueltas</option><option value="">Todas</option></select>}>
      <DataTable rows={data?.items} empty="Sin incidencias" columns={[
        { key: "created_at", title: "Fecha", render: (r) => fmtDate(r.created_at) },
        { key: "incident_type", title: "Tipo", render: (r) => INCIDENT_TYPES[r.incident_type] ?? r.incident_type },
        { key: "description", title: "Descripción" }, { key: "resolution", title: "Solución" },
        { key: "a", title: "", render: (r) => <span className="row">
          <button className="secondary" onClick={() => nav(`/logistica/despachos/${r.dispatch_id}`)}>Ver despacho</button>
          {r.status === "open" && can("logistics.dispatch.create") && <ActionButton onClick={async () => {
            const resolution = window.prompt("Solución aplicada");
            if (resolution) { await post(`/logistics/incidents/${r.id}/resolve`, { resolution }); reload(); }
          }}>Resolver</ActionButton>}</span> }]} />
    </Page>
  );
}

/** Devoluciones de clientes registradas. */
export function ReturnsPage() {
  const { data } = useFetch<Json>("/logistics/returns");
  const itemName = useItemNames();
  const nav = useNavigate();
  return (
    <Page title="Devoluciones de clientes" subtitle="Se registran desde el detalle del despacho">
      <DataTable rows={data?.items} empty="Sin devoluciones" onRowClick={(r) => nav(`/logistica/despachos/${r.dispatch_id}`)} columns={[
        { key: "number", title: "Número" }, { key: "return_date", title: "Fecha" }, { key: "reason", title: "Motivo" },
        { key: "lines", title: "Artículos", render: (r) => r.lines.map((l: Json) => `${itemName(l.item_id)} × ${fmtNumber(l.quantity)}`).join("; ") },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status === "received" ? "received" : r.status} /> }]} />
      <p className="muted">El valor reconocido al cliente se refleja emitiendo una nota crédito desde Facturación.</p>
    </Page>
  );
}

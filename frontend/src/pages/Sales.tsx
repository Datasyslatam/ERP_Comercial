import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Line, LinesEditor, linesPayload } from "../components/LinesEditor";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { download, Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

export function SalesOrdersPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ item_id: "", quantity: "1", unit_price: "" }]);
  const customers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const sites = useOptions("/sites", (x) => x.name);
  const whs = useOptions("/warehouses", (x) => x.name);
  const { data, reload } = useFetch<Json>(`/sales/orders${qs({ status })}`);
  return (
    <Page title="Pedidos de venta" actions={<>
      <select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Todos</option>{["draft", "confirmed", "partially_dispatched", "dispatched", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      {can("sales.order.create") && <button onClick={() => setCreating(true)}>Nuevo pedido</button>}
    </>}>
      <DataTable rows={data?.items} columns={[{ key: "number", title: "Número" }, { key: "order_date", title: "Fecha" },
        { key: "promised_date", title: "Prometido" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total, r.currency) },
        { key: "a", title: "", render: (r) => <span className="row">
          {r.status === "draft" && can("sales.order.approve") &&
            <ActionButton onClick={async () => { await post(`/sales/orders/${r.id}/confirm`); reload(); }}>Confirmar y reservar</ActionButton>}
          {["confirmed", "partially_dispatched"].includes(r.status) && can("logistics.dispatch.create") &&
            <ActionButton onClick={async () => { await post("/logistics/dispatches", { sales_order_id: r.id }); reload(); }}>Generar despacho</ActionButton>}
        </span> }]} />
      {creating && (
        <Modal title="Nuevo pedido de venta" onClose={() => setCreating(false)}>
          <LinesEditor lines={lines} onChange={setLines} withDiscount priceRequired={false} />
          <p className="muted">Si no indica precio se usa el precio de lista del artículo.</p>
          <Form initial={{ order_date: today(), currency: "COP" }} fields={[
            { name: "customer_id", label: "Cliente", type: "select", required: true, options: customers },
            { name: "site_id", label: "Sede", type: "select", required: true, options: sites },
            { name: "warehouse_id", label: "Bodega", type: "select", required: true, options: whs },
            { name: "order_date", label: "Fecha", type: "date", required: true }, { name: "promised_date", label: "Fecha prometida", type: "date" },
            { name: "currency", label: "Moneda", required: true }, { name: "delivery_address", label: "Dirección de entrega" }]}
            onSubmit={async (d) => { await post("/sales/orders", { ...d, lines: linesPayload(lines) }); setCreating(false); reload(); }} />
        </Modal>
      )}
    </Page>
  );
}

export function DispatchesPage() {
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const { data } = useFetch<Json>(`/logistics/dispatches${qs({ status })}`);
  return (
    <Page title="Despachos" actions={<select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
      <option value="">Todos</option>{["draft", "picking", "picked", "packed", "shipped", "delivered", "partially_delivered"].map((s) => <option key={s} value={s}>{s}</option>)}</select>}>
      <DataTable rows={data?.items} onRowClick={(r) => nav(`/logistica/despachos/${r.id}`)} columns={[{ key: "number", title: "Número" },
        { key: "promised_date", title: "Prometido" }, { key: "tracking_number", title: "Guía" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "freight_cost", title: "Flete", align: "right", render: (r) => fmtMoney(r.freight_cost) }]} />
    </Page>
  );
}

export function DispatchDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can } = useSession();
  const { data: d, reload } = useFetch<Json>(`/logistics/dispatches/${id}`);
  const carriers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const [step, setStep] = useState<string | null>(null);
  if (!d) return <p className="muted">Cargando…</p>;
  const call = async (path: string, body?: Json) => { await post(`/logistics/dispatches/${d.id}/${path}`, body); setStep(null); reload(); };
  const canPost = can("logistics.dispatch.post");
  return (
    <Page title={`Despacho ${d.number}`} actions={<>
      <Badge value={d.status} />
      {d.status === "draft" && <ActionButton onClick={() => call("start-picking")}>Iniciar picking</ActionButton>}
      {d.status === "picking" && <button onClick={() => setStep("pick")}>Confirmar picking</button>}
      {d.status === "picked" && <button onClick={() => setStep("pack")}>Empacar</button>}
      {d.status === "packed" && canPost && <button onClick={() => setStep("ship")}>Enviar</button>}
      {d.status === "shipped" && canPost && <button onClick={() => setStep("deliver")}>Registrar entrega</button>}
      {["shipped", "delivered", "partially_delivered"].includes(d.status) && can("einvoicing.invoice.create") &&
        <ActionButton onClick={async () => { const inv = await post("/einvoicing/invoices/from-dispatch", { dispatch_id: d.id }); nav(`/facturacion?focus=${inv.id}`); }}>Facturar</ActionButton>}
    </>}>
      <KeyValues data={d} keys={[["delivery_address", "Dirección"], ["promised_date", "Fecha prometida"], ["vehicle_plate", "Placa"],
        ["driver_name", "Conductor"], ["tracking_number", "Guía"], ["packages_count", "Bultos"], ["pod_received_by", "Recibió"],
        ["delivered_at", "Entregado", fmtDate]]} />
      <DataTable rows={d.lines} columns={[{ key: "item_id", title: "Artículo" },
        ...["qty_requested", "qty_picked", "qty_shipped", "qty_delivered", "qty_returned", "qty_invoiced"].map((k) => ({
          key: k, title: { qty_requested: "Solicitado", qty_picked: "Preparado", qty_shipped: "Enviado", qty_delivered: "Entregado",
            qty_returned: "Devuelto", qty_invoiced: "Facturado" }[k] as string, align: "right" as const, render: (r: Json) => fmtNumber(r[k]) }))]} />
      <h3>Seguimiento</h3>
      <DataTable rows={d.events} columns={[{ key: "event_time", title: "Fecha", render: (r) => fmtDate(r.event_time) },
        { key: "status", title: "Evento" }, { key: "notes", title: "Notas" }]} />
      {d.incidents?.length > 0 && <><h3>Incidencias</h3><DataTable rows={d.incidents} columns={[{ key: "incident_type", title: "Tipo" },
        { key: "description", title: "Descripción" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} /></>}
      {step === "pick" && <Modal title="Verificación de picking" onClose={() => setStep(null)}>
        <Form fields={d.lines.map((l: Json) => ({ name: `p_${l.id}`, label: `Artículo ${l.item_id} (solicitado ${fmtNumber(l.qty_requested)})`, type: "number" as const, required: true }))}
          initial={Object.fromEntries(d.lines.map((l: Json) => [`p_${l.id}`, l.qty_requested]))}
          onSubmit={(v) => call("picking", { picks: d.lines.map((l: Json) => ({ dispatch_line_id: l.id, qty_picked: v[`p_${l.id}`] })) })} />
      </Modal>}
      {step === "pack" && <Modal title="Empaque" onClose={() => setStep(null)}>
        <Form fields={[{ name: "packages_count", label: "Bultos", type: "number", required: true }, { name: "gross_weight_kg", label: "Peso bruto (kg)", type: "number" }]}
          onSubmit={(v) => call("pack", { ...v, packages_count: Number(v.packages_count) })} />
      </Modal>}
      {step === "ship" && <Modal title="Envío" onClose={() => setStep(null)}>
        <Form fields={[{ name: "carrier_id", label: "Transportista", type: "select", options: carriers }, { name: "vehicle_plate", label: "Placa" },
          { name: "driver_name", label: "Conductor" }, { name: "tracking_number", label: "Guía" }, { name: "freight_cost", label: "Costo del flete", type: "number" }]}
          onSubmit={(v) => call("ship", v)} />
      </Modal>}
      {step === "deliver" && <Modal title="Evidencia de entrega" onClose={() => setStep(null)}>
        <Form fields={[{ name: "received_by", label: "Recibido por", required: true }, { name: "notes", label: "Observaciones", type: "textarea" },
          ...d.lines.map((l: Json) => ({ name: `d_${l.id}`, label: `Entregado artículo ${l.item_id}`, type: "number" as const }))]}
          initial={Object.fromEntries(d.lines.map((l: Json) => [`d_${l.id}`, l.qty_shipped]))}
          onSubmit={(v) => call("deliver", { received_by: v.received_by, notes: v.notes,
            lines: d.lines.map((l: Json) => ({ dispatch_line_id: l.id, qty_delivered: v[`d_${l.id}`] ?? l.qty_shipped })) })} />
        <p className="muted">El soporte firmado puede adjuntarse en Adjuntos (entidad dispatch_orders).</p>
      </Modal>}
    </Page>
  );
}

export function InvoicingPage() {
  const { can } = useSession();
  const [edoc, setEdoc] = useState("");
  const { data, reload } = useFetch<Json>(`/einvoicing/invoices${qs({ edoc_status: edoc })}`);
  const [current, setCurrent] = useState<number | null>(null);
  const detail = useFetch<Json>(current ? `/einvoicing/invoices/${current}` : null);
  return (
    <Page title="Facturación electrónica" actions={<select aria-label="Estado electrónico" value={edoc} onChange={(e) => setEdoc(e.target.value)}>
      <option value="">Todos</option>{["draft", "pending", "sent", "accepted", "rejected", "error"].map((s) => <option key={s} value={s}>{s}</option>)}</select>}>
      <Alert kind="warning">Proveedor tecnológico no definido: los documentos se procesan con el adaptador SANDBOX y NO tienen validez fiscal.</Alert>
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "full_number", title: "Número", render: (r) => r.full_number ?? "(borrador)" },
        { key: "doc_type", title: "Tipo" }, { key: "issue_date", title: "Fecha" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "edoc_status", title: "Documento electrónico", render: (r) => <Badge value={r.edoc_status} /> },
        { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total, r.currency) },
        { key: "a", title: "", render: (r) => <span className="row" onClick={(e) => e.stopPropagation()}>
          {r.status === "draft" && can("einvoicing.invoice.post") && <ActionButton confirm="Se asignará número autorizado y se contabilizará. ¿Emitir?"
            onClick={async () => { await post(`/einvoicing/invoices/${r.id}/issue`); reload(); }}>Emitir</ActionButton>}
          {["rejected", "error"].includes(r.edoc_status) && can("einvoicing.invoice.post") &&
            <ActionButton onClick={async () => { await post(`/einvoicing/invoices/${r.id}/resend`); reload(); }}>Reenviar</ActionButton>}
        </span> }]} />
      {detail.data && current && (
        <Modal title={`Documento ${detail.data.full_number ?? "borrador"}`} onClose={() => setCurrent(null)}>
          {detail.data.fiscal_notice && <Alert kind="warning">{detail.data.fiscal_notice}</Alert>}
          <KeyValues data={detail.data} keys={[["edoc_status", "Estado electrónico", (v) => <Badge value={v} />], ["edoc_environment", "Ambiente"],
            ["fiscal_uid", "CUFE / identificador"], ["control_number", "Número de control"], ["edoc_message", "Mensaje"],
            ["subtotal", "Subtotal", fmtMoney], ["tax_total", "Impuestos", fmtMoney], ["total", "Total", fmtMoney], ["journal_entry_id", "Asiento contable"]]} />
          <h3>Intentos de envío</h3>
          <DataTable rows={detail.data.submissions} empty="Sin envíos" columns={[{ key: "attempt_no", title: "#" },
            { key: "created_at", title: "Fecha", render: (r) => fmtDate(r.created_at) }, { key: "adapter", title: "Adaptador" },
            { key: "result_status", title: "Resultado", render: (r) => <Badge value={r.result_status} /> }, { key: "provider_message", title: "Mensaje" }]} />
          {detail.data.submissions?.some((s: Json) => s.document_attachment_id) &&
            <button className="secondary" onClick={() => download(`/einvoicing/invoices/${current}/document`, `${detail.data.full_number}.xml`)}>Descargar documento</button>}
        </Modal>
      )}
    </Page>
  );
}

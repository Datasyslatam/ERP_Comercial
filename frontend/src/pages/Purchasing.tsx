import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Line, LinesEditor, linesPayload } from "../components/LinesEditor";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

export function RequisitionsPage() {
  const { can } = useSession();
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ item_id: "", quantity: "1", unit_price: "" }]);
  const sites = useOptions("/sites", (x) => x.name);
  const ccs = useOptions("/cost-centers", (x) => `${x.code} ${x.name}`);
  const { data, reload } = useFetch<Json>(`/purchasing/requisitions${qs({ status })}`);
  const [rfqFor, setRfqFor] = useState<Json | null>(null);

  return (
    <Page title="Solicitudes de compra" actions={<>
      <select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Todas</option>{["draft", "submitted", "approved", "rejected", "ordered"].map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      {can("purchasing.requisition.create") && <button onClick={() => setCreating(true)}>Nueva solicitud</button>}
    </>}>
      <DataTable rows={data?.items} columns={[
        { key: "number", title: "Número" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "needed_by", title: "Requerida" }, { key: "total_estimated", title: "Estimado", align: "right", render: (r) => fmtMoney(r.total_estimated) },
        { key: "actions", title: "", render: (r) => <span className="row">
          {r.status === "draft" && <ActionButton onClick={async () => { await post(`/purchasing/requisitions/${r.id}/submit`); reload(); }}>Enviar</ActionButton>}
          {r.status === "submitted" && can("purchasing.requisition.approve") && <>
            <ActionButton onClick={async () => { await post(`/purchasing/requisitions/${r.id}/decision`, { approve: true }); reload(); }}>Aprobar</ActionButton>
            <ActionButton className="danger" onClick={async () => {
              const reason = window.prompt("Motivo del rechazo");
              if (reason) { await post(`/purchasing/requisitions/${r.id}/decision`, { approve: false, reason }); reload(); }
            }}>Rechazar</ActionButton></>}
          {r.status === "approved" && can("purchasing.rfq.create") && <button onClick={() => setRfqFor(r)}>Cotizar</button>}
        </span> },
      ]} />
      {creating && (
        <Modal title="Nueva solicitud de compra" onClose={() => setCreating(false)}>
          <LinesEditor lines={lines} onChange={setLines} priceRequired={false} />
          <Form fields={[{ name: "site_id", label: "Sede", type: "select", required: true, options: sites },
            { name: "cost_center_id", label: "Centro de costo", type: "select", options: ccs },
            { name: "needed_by", label: "Fecha requerida", type: "date" }, { name: "justification", label: "Justificación", type: "textarea" }]}
            onSubmit={async (d) => {
              await post("/purchasing/requisitions", { ...d, lines: linesPayload(lines).map((l) => ({
                item_id: l.item_id, quantity: l.quantity, estimated_unit_price: l.unit_price ?? "0" })) });
              setCreating(false); reload();
            }} />
        </Modal>
      )}
      {rfqFor && <RfqModal requisition={rfqFor} onClose={() => { setRfqFor(null); reload(); }} />}
    </Page>
  );
}

function RfqModal({ requisition, onClose }: { requisition: Json; onClose: () => void }) {
  const nav = useNavigate();
  const [rfq, setRfq] = useState<Json | null>(null);
  const [cmp, setCmp] = useState<Json | null>(null);
  const suppliers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const whs = useOptions("/warehouses", (x) => x.name);
  const [error, setError] = useState<string | null>(null);
  const loadCmp = async (id: number) => setCmp(await (await import("../lib/api")).get(`/purchasing/rfqs/${id}/comparison`));
  return (
    <Modal title={`Cotizaciones · ${requisition.number}`} onClose={onClose}>
      <Alert>{error}</Alert>
      {!rfq ? <ActionButton onClick={async () => { const r = await post("/purchasing/rfqs", { requisition_id: requisition.id }); setRfq(r); await loadCmp(r.id); }}>
        Abrir solicitud de cotización</ActionButton> : <>
        <h3>Registrar cotización</h3>
        <Form fields={[{ name: "supplier_id", label: "Proveedor", type: "select", required: true, options: suppliers },
          { name: "quote_date", label: "Fecha", type: "date", required: true }, { name: "currency", label: "Moneda", required: true },
          { name: "delivery_days", label: "Días de entrega", type: "number" },
          ...requisition.lines.map((l: Json) => ({ name: `price_${l.id}`, label: `Precio unitario línea ${l.id} (cant. ${fmtNumber(l.quantity)})`, type: "number" as const, required: true }))]}
          initial={{ quote_date: today(), currency: "COP" }} submitLabel="Agregar cotización"
          onSubmit={async (d) => {
            await post(`/purchasing/rfqs/${rfq.id}/quotes`, { supplier_id: d.supplier_id, quote_date: d.quote_date, currency: d.currency,
              delivery_days: Number(d.delivery_days ?? 0), lines: requisition.lines.map((l: Json) => ({
                requisition_line_id: l.id, quantity: l.quantity, unit_price: d[`price_${l.id}`] })) });
            await loadCmp(rfq.id);
          }} />
        {cmp && <>
          <h3>Comparativo</h3>
          <DataTable rows={cmp.suppliers} columns={[{ key: "supplier_id", title: "Proveedor" },
            { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total) }, { key: "delivery_days", title: "Días" },
            { key: "rec", title: "", render: (r) => r.quote_id === cmp.recommended_quote_id ? <Badge value="ok" /> : null },
            { key: "award", title: "", render: (r) => whs[0] ? <ActionButton onClick={async () => {
              try { const po = await post(`/purchasing/rfqs/${rfq.id}/award`, { quote_id: r.quote_id, warehouse_id: whs[0].value }); nav(`/compras/ordenes/${po.id}`); }
              catch (e) { setError((e as Error).message); throw e; } }}>Adjudicar</ActionButton> : null }]} />
        </>}
      </>}
    </Modal>
  );
}

export function OrdersPage() {
  const nav = useNavigate();
  const { can } = useSession();
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ item_id: "", quantity: "1", unit_price: "" }]);
  const sites = useOptions("/sites", (x) => x.name);
  const whs = useOptions("/warehouses", (x) => x.name);
  const suppliers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const params = new URLSearchParams(window.location.search);
  const { data } = useFetch<Json>(`/purchasing/orders${qs({ status, overdue: params.get("overdue") ? 1 : undefined })}`);
  return (
    <Page title="Órdenes de compra" actions={<>
      <select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Todas</option>{["draft", "submitted", "approved", "partially_received", "received", "closed", "cancelled"].map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      {can("purchasing.order.create") && <button onClick={() => setCreating(true)}>Nueva orden</button>}
    </>}>
      <DataTable rows={data?.items} onRowClick={(r) => nav(`/compras/ordenes/${r.id}`)} columns={[
        { key: "number", title: "Número" }, { key: "order_date", title: "Fecha" }, { key: "expected_date", title: "Entrega esperada" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total, r.currency) }]} />
      {creating && (
        <Modal title="Nueva orden de compra" onClose={() => setCreating(false)}>
          <LinesEditor lines={lines} onChange={setLines} />
          <Form initial={{ order_date: today(), currency: "COP" }} fields={[
            { name: "supplier_id", label: "Proveedor", type: "select", required: true, options: suppliers },
            { name: "site_id", label: "Sede", type: "select", required: true, options: sites },
            { name: "warehouse_id", label: "Bodega destino", type: "select", required: true, options: whs },
            { name: "order_date", label: "Fecha", type: "date", required: true }, { name: "expected_date", label: "Entrega esperada", type: "date" },
            { name: "currency", label: "Moneda", required: true }, { name: "exchange_rate", label: "Tasa (si es divisa)", type: "number" },
            { name: "notes", label: "Notas", type: "textarea" }]}
            onSubmit={async (d) => { const po = await post("/purchasing/orders", { ...d, lines: linesPayload(lines) }); nav(`/compras/ordenes/${po.id}`); }} />
        </Modal>
      )}
    </Page>
  );
}

export function OrderDetailPage() {
  const { id } = useParams();
  const { can } = useSession();
  const { data: po, reload } = useFetch<Json>(`/purchasing/orders/${id}`);
  const [receiving, setReceiving] = useState(false);
  if (!po) return <p className="muted">Cargando…</p>;
  const act = (path: string, body?: Json) => async () => { await post(`/purchasing/orders/${po.id}/${path}`, body); reload(); };
  return (
    <Page title={`Orden de compra ${po.number}`} actions={<>
      <Badge value={po.status} />
      {po.status === "draft" && <ActionButton onClick={act("submit")}>Enviar a aprobación</ActionButton>}
      {po.status === "submitted" && can("purchasing.order.approve") && <ActionButton onClick={act("decision", { approve: true })}>Aprobar</ActionButton>}
      {["approved", "partially_received"].includes(po.status) && can("purchasing.receipt.post") &&
        <button onClick={() => setReceiving(true)}>Registrar recepción</button>}
    </>}>
      <KeyValues data={po} keys={[["order_date", "Fecha"], ["expected_date", "Entrega esperada"], ["currency", "Moneda"],
        ["exchange_rate", "Tasa"], ["subtotal", "Subtotal", fmtMoney], ["tax_total", "Impuestos", fmtMoney], ["total", "Total", fmtMoney]]} />
      <h3>Líneas</h3>
      <DataTable rows={po.lines} columns={[{ key: "line_no", title: "#" }, { key: "item_id", title: "Artículo" },
        { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
        { key: "unit_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.unit_price) },
        { key: "qty_received", title: "Recibido", align: "right", render: (r) => fmtNumber(r.qty_received) },
        { key: "qty_rejected", title: "Rechazado", align: "right", render: (r) => fmtNumber(r.qty_rejected) },
        { key: "qty_invoiced", title: "Facturado", align: "right", render: (r) => fmtNumber(r.qty_invoiced) }]} />
      <h3>Trazabilidad</h3>
      <DataTable rows={po.receipts} empty="Sin recepciones" columns={[{ key: "number", title: "Recepción" }, { key: "receipt_date", title: "Fecha" },
        { key: "lines", title: "Líneas", render: (r) => r.lines.map((l: Json) => `${fmtNumber(l.quantity)} (${l.inspection_status})`).join(", ") }]} />
      <DataTable rows={po.invoices} empty="Sin facturas de proveedor" columns={[{ key: "supplier_invoice_number", title: "Factura proveedor" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }, { key: "journal_entry_id", title: "Asiento" },
        { key: "payable_total", title: "Por pagar", align: "right", render: (r) => fmtMoney(r.payable_total) }]} />
      {receiving && (
        <Modal title="Recepción de mercancía" onClose={() => setReceiving(false)}>
          <Form initial={{ receipt_date: today() }} fields={[{ name: "receipt_date", label: "Fecha", type: "date", required: true },
            { name: "supplier_delivery_note", label: "Remisión del proveedor" },
            ...po.lines.flatMap((l: Json) => [
              { name: `q_${l.id}`, label: `Cantidad línea ${l.line_no} (pendiente ${fmtNumber(Number(l.quantity) - Number(l.qty_received) + Number(l.qty_rejected))})`, type: "number" as const },
              { name: `lot_${l.id}`, label: `Lote línea ${l.line_no}` }, { name: `exp_${l.id}`, label: `Vencimiento línea ${l.line_no}`, type: "date" as const }])]}
            onSubmit={async (d) => {
              const lines = po.lines.filter((l: Json) => Number(d[`q_${l.id}`]) > 0).map((l: Json) => ({ po_line_id: l.id, quantity: d[`q_${l.id}`],
                ...(d[`lot_${l.id}`] ? { lot_number: d[`lot_${l.id}`] } : {}), ...(d[`exp_${l.id}`] ? { expiry_date: d[`exp_${l.id}`] } : {}) }));
              await post(`/purchasing/orders/${po.id}/receipts`, { receipt_date: d.receipt_date, supplier_delivery_note: d.supplier_delivery_note, lines });
              setReceiving(false); reload();
            }} />
        </Modal>
      )}
      <p className="muted">Creada {fmtDate(po.created_at)}</p>
    </Page>
  );
}

export function SupplierInvoicesPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/purchasing/invoices");
  const receipts = useFetch<Json>("/purchasing/receipts?limit=100");
  const suppliers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const [creating, setCreating] = useState(false);
  const pending: Json[] = (receipts.data?.items ?? []).flatMap((g: Json) => g.lines.filter((l: Json) => Number(l.qty_accepted) > Number(l.qty_invoiced))
    .map((l: Json) => ({ ...l, receipt_number: g.number, supplier_id: g.supplier_id })));
  const [selected, setSelected] = useState<Record<number, string>>({});
  return (
    <Page title="Facturas de proveedor" subtitle="Cruce a tres vías: orden de compra, recepción aceptada y factura"
          actions={can("purchasing.invoice.create") && <button onClick={() => setCreating(true)}>Registrar factura</button>}>
      <DataTable rows={data?.items} columns={[{ key: "number", title: "Interno" }, { key: "supplier_invoice_number", title: "Nº proveedor" },
        { key: "invoice_date", title: "Fecha" }, { key: "match_status", title: "Cruce" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "withholding_total", title: "Retenciones", align: "right", render: (r) => fmtMoney(r.withholding_total) },
        { key: "payable_total", title: "Por pagar", align: "right", render: (r) => fmtMoney(r.payable_total, r.currency) },
        { key: "a", title: "", render: (r) => r.status === "draft" && can("purchasing.invoice.post") &&
          <ActionButton onClick={async () => { await post(`/purchasing/invoices/${r.id}/post`); reload(); }}>Contabilizar</ActionButton> }]} />
      {creating && (
        <Modal title="Registrar factura de proveedor" onClose={() => setCreating(false)}>
          <h3>Recepciones aceptadas pendientes de facturar</h3>
          <DataTable rows={pending} empty="No hay recepciones pendientes" columns={[{ key: "receipt_number", title: "Recepción" },
            { key: "item_id", title: "Artículo" }, { key: "qty", title: "Pendiente", align: "right", render: (r) => fmtNumber(Number(r.qty_accepted) - Number(r.qty_invoiced)) },
            { key: "price", title: "Precio facturado", render: (r) => <input type="number" step="any" aria-label="Precio facturado"
              value={selected[r.id] ?? ""} onChange={(e) => setSelected({ ...selected, [r.id]: e.target.value })} /> }]} />
          <Form initial={{ invoice_date: today(), currency: "COP" }} fields={[
            { name: "supplier_id", label: "Proveedor", type: "select", required: true, options: suppliers },
            { name: "supplier_invoice_number", label: "Número de factura", required: true }, { name: "supplier_cufe", label: "CUFE del proveedor" },
            { name: "invoice_date", label: "Fecha", type: "date", required: true }, { name: "currency", label: "Moneda", required: true }]}
            onSubmit={async (d) => {
              const lines = pending.filter((l: Json) => selected[l.id]).map((l: Json) => ({ receipt_line_id: l.id, description: `Recepción ${l.receipt_number}`,
                quantity: String(Number(l.qty_accepted) - Number(l.qty_invoiced)), unit_price: selected[l.id] }));
              await post("/purchasing/invoices", { ...d, lines });
              setCreating(false); reload(); receipts.reload();
            }} />
        </Modal>
      )}
    </Page>
  );
}

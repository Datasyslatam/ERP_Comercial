import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { TracePanel } from "../components/TracePanel";
import { DocumentActions } from "../components/DocumentActions";
import { Line, LinesEditor, linesPayload } from "../components/LinesEditor";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber, label } from "../lib/format";
import { useFetch, useItemNames, useLookup, useOptions } from "../lib/hooks";
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
        <option value="">Todas</option>{["draft", "submitted", "approved", "rejected", "ordered"].map((s) => <option key={s} value={s}>{label(s)}</option>)}
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
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
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
          <DataTable rows={cmp.suppliers} columns={[{ key: "supplier_id", title: "Proveedor", render: (r) => partyName(r.supplier_id) },
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
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const params = new URLSearchParams(window.location.search);
  const { data } = useFetch<Json>(`/purchasing/orders${qs({ status, overdue: params.get("overdue") ? 1 : undefined })}`);
  return (
    <Page title="Órdenes de compra" actions={<>
      <select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Todas</option>{["draft", "submitted", "approved", "partially_received", "received", "closed", "cancelled"].map((s) => <option key={s} value={s}>{label(s)}</option>)}
      </select>
      {can("purchasing.order.create") && <button onClick={() => setCreating(true)}>Nueva orden</button>}
    </>}>
      <DataTable rows={data?.items} onRowClick={(r) => nav(`/compras/ordenes/${r.id}`)} columns={[
        { key: "number", title: "Número" }, { key: "supplier_id", title: "Proveedor", render: (r) => partyName(r.supplier_id) },
        { key: "order_date", title: "Fecha" }, { key: "expected_date", title: "Entrega esperada" },
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
  const itemName = useItemNames();
  const [receiving, setReceiving] = useState(false);
  const [closing, setClosing] = useState<"reject" | "cancel" | null>(null);
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  if (!po) return <p className="muted">Cargando…</p>;
  const act = (path: string, body?: Json) => async () => { await post(`/purchasing/orders/${po.id}/${path}`, body); reload(); };
  return (
    <Page title={`Orden de compra ${po.number}`} subtitle={partyName(po.supplier_id)} actions={<>
      <Badge value={po.status} />
      <DocumentActions type="purchase_order" id={po.id} number={po.number}
        canSend={can("purchasing.order.create") && ["approved", "partially_received", "received", "closed"].includes(po.status)}
        sendHint={["draft", "submitted"].includes(po.status) ? "Se envía al proveedor una vez aprobada" : undefined} />
      {po.status === "draft" && <ActionButton onClick={act("submit")}>Enviar a aprobación</ActionButton>}
      {po.status === "submitted" && can("purchasing.order.approve") && <>
        <ActionButton onClick={act("decision", { approve: true })}>Aprobar</ActionButton>
        <button className="secondary" onClick={() => setClosing("reject")}>Rechazar</button></>}
      {["draft", "submitted", "approved"].includes(po.status) && can("purchasing.order.void") &&
        <button className="danger" onClick={() => setClosing("cancel")}>Anular</button>}
      {["approved", "partially_received"].includes(po.status) && can("purchasing.receipt.post") &&
        <button onClick={() => setReceiving(true)}>Registrar recepción</button>}
    </>}>
      <KeyValues data={po} keys={[["order_date", "Fecha"], ["expected_date", "Entrega esperada"], ["currency", "Moneda"],
        ["exchange_rate", "Tasa"], ["subtotal", "Subtotal", fmtMoney], ["tax_total", "Impuestos", fmtMoney], ["total", "Total", fmtMoney]]} />
      <h3>Líneas</h3>
      <DataTable rows={po.lines} columns={[{ key: "line_no", title: "#" }, { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
        { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
        { key: "unit_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.unit_price) },
        { key: "qty_received", title: "Recibido", align: "right", render: (r) => fmtNumber(r.qty_received) },
        { key: "qty_rejected", title: "Rechazado", align: "right", render: (r) => fmtNumber(r.qty_rejected) },
        { key: "qty_invoiced", title: "Facturado", align: "right", render: (r) => fmtNumber(r.qty_invoiced) }]} />
      <h3>Recepciones y facturas</h3>
      <DataTable rows={po.receipts} empty="Sin recepciones" columns={[{ key: "number", title: "Recepción" }, { key: "receipt_date", title: "Fecha" },
        { key: "lines", title: "Líneas", render: (r) => r.lines.map((l: Json) => `${fmtNumber(l.quantity)} (${l.inspection_status})`).join(", ") }]} />
      <DataTable rows={po.invoices} empty="Sin facturas de proveedor" columns={[{ key: "supplier_invoice_number", title: "Factura proveedor" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }, { key: "journal_entry_id", title: "Asiento" },
        { key: "payable_total", title: "Por pagar", align: "right", render: (r) => fmtMoney(r.payable_total) }]} />
      <h3>Trazabilidad</h3>
      <TracePanel type="purchase_order" id={po.id} />
      {closing && <Modal title={closing === "reject" ? "Rechazar orden de compra" : "Anular orden de compra"} onClose={() => setClosing(null)}>
        <Form submitLabel={closing === "reject" ? "Rechazar" : "Anular"} fields={[{ name: "reason", label: "Motivo", type: "textarea", required: true }]}
          onSubmit={async (d) => {
            if (closing === "reject") await post(`/purchasing/orders/${po.id}/decision`, { approve: false, reason: d.reason });
            else await post(`/purchasing/orders/${po.id}/cancel`, d);
            setClosing(null); reload();
          }} />
      </Modal>}
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
  const itemName = useItemNames();
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
            { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) }, { key: "qty", title: "Pendiente", align: "right", render: (r) => fmtNumber(Number(r.qty_accepted) - Number(r.qty_invoiced)) },
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

// ------------------------------------------------------------------ recepciones
export function ReceiptsPage() {
  const nav = useNavigate();
  const [start, setStart] = useState(today().slice(0, 8) + "01");
  const [end, setEnd] = useState(today());
  const [supplier, setSupplier] = useState("");
  const [current, setCurrent] = useState<Json | null>(null);
  const suppliers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const itemName = useItemNames();
  const { data } = useFetch<Json>(`/purchasing/receipts${qs({ start, end, supplier_id: supplier, limit: 200 })}`);
  return (
    <Page title="Recepciones de mercancía" subtitle="Entradas por orden de compra, con lote, vencimiento e inspección de calidad">
      <div className="filters">
        <label>Desde<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>Hasta<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <label>Proveedor<select value={supplier} onChange={(e) => setSupplier(e.target.value)}><option value="">Todos</option>
          {suppliers.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
      </div>
      <DataTable rows={data?.items} onRowClick={setCurrent} empty="Sin recepciones en el periodo" columns={[
        { key: "number", title: "Número" }, { key: "receipt_date", title: "Fecha" },
        { key: "supplier_id", title: "Proveedor", render: (r) => partyName(r.supplier_id) },
        { key: "supplier_delivery_note", title: "Remisión", render: (r) => r.supplier_delivery_note ?? "—" },
        { key: "lines", title: "Líneas", align: "right", render: (r) => r.lines.length },
        { key: "inspection", title: "Calidad", render: (r) => r.lines.some((l: Json) => l.inspection_status === "pending")
          ? <Badge value="pending" /> : <Badge value="ok" /> },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {current && <Modal title={`Recepción ${current.number}`} onClose={() => setCurrent(null)}>
        <KeyValues data={current} keys={[["receipt_date", "Fecha"], ["supplier_id", "Proveedor", (v) => partyName(v)],
          ["supplier_delivery_note", "Remisión"], ["status", "Estado", (v) => <Badge value={v} />]]} />
        <DataTable rows={current.lines} columns={[{ key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
          { key: "quantity", title: "Recibido", align: "right", render: (r) => fmtNumber(r.quantity) },
          { key: "qty_accepted", title: "Aceptado", align: "right", render: (r) => fmtNumber(r.qty_accepted) },
          { key: "qty_rejected", title: "Rechazado", align: "right", render: (r) => fmtNumber(r.qty_rejected) },
          { key: "qty_invoiced", title: "Facturado", align: "right", render: (r) => fmtNumber(r.qty_invoiced) },
          { key: "lot_number", title: "Lote", render: (r) => r.lot_number ?? "—" }, { key: "expiry_date", title: "Vence", render: (r) => r.expiry_date ?? "—" },
          { key: "inspection_status", title: "Inspección", render: (r) => <Badge value={r.inspection_status} /> }]} />
        <p><button className="secondary" onClick={() => nav(`/compras/ordenes/${current.purchase_order_id}`)}>Ver orden de compra</button></p>
        <h3>Trazabilidad</h3>
        <TracePanel type="goods_receipt" id={current.id} />
      </Modal>}
    </Page>
  );
}

// ------------------------------------------------------------------ historial de precios
export function PriceHistoryPage() {
  const [itemId, setItemId] = useState("");
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const { data } = useFetch<Json[]>(itemId ? `/purchasing/price-history/${itemId}` : null);
  const prices = (data ?? []).map((r) => Number(r.unit_price));
  const last = prices[prices.length - 1];
  const prev = prices[prices.length - 2];
  const change = last !== undefined && prev ? ((last - prev) / prev) * 100 : null;
  return (
    <Page title="Historial de precios de compra" subtitle="Precios pactados en órdenes de compra aprobadas, por artículo y proveedor">
      <div className="filters"><label>Artículo<select value={itemId} onChange={(e) => setItemId(e.target.value)}>
        <option value="">Seleccione…</option>{items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label></div>
      {data && data.length > 0 && <div className="summary">
        <span>Último precio <strong>{fmtMoney(last)}</strong></span>
        <span>Mínimo <strong>{fmtMoney(Math.min(...prices))}</strong></span><span>Máximo <strong>{fmtMoney(Math.max(...prices))}</strong></span>
        {change !== null && <span className={change > 0 ? "warn-text" : ""}>Variación frente a la compra anterior <strong>{fmtNumber(change)} %</strong></span>}
      </div>}
      {itemId && <DataTable rows={data ? [...data].reverse() : null} empty="El artículo no tiene compras registradas" columns={[
        { key: "order_date", title: "Fecha" }, { key: "number", title: "Orden" }, { key: "supplier_id", title: "Proveedor", render: (r) => partyName(r.supplier_id) },
        { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
        { key: "unit_price", title: "Precio unitario", align: "right", render: (r) => fmtMoney(r.unit_price, r.currency) }]} />}
    </Page>
  );
}

// ------------------------------------------------------------------ evaluación de proveedores y presupuesto
export function SupplierEvaluationPage() {
  const [start, setStart] = useState(`${new Date().getFullYear()}-01-01`);
  const [end, setEnd] = useState(today());
  const { data } = useFetch<Json[]>(`/purchasing/suppliers/evaluation${qs({ start, end })}`);
  return (
    <Page title="Evaluación de proveedores" subtitle="Cumplimiento de entrega y aceptación de calidad sobre las recepciones del periodo">
      <div className="filters">
        <label>Desde<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>Hasta<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
      </div>
      <DataTable rows={data} empty="Sin recepciones en el periodo" columns={[
        { key: "supplier_name", title: "Proveedor" }, { key: "receipts", title: "Recepciones", align: "right" },
        { key: "on_time_pct", title: "Entrega a tiempo %", align: "right", render: (r) => fmtNumber(r.on_time_pct) },
        { key: "quality_acceptance_pct", title: "Aceptación calidad %", align: "right", render: (r) => fmtNumber(r.quality_acceptance_pct) },
        { key: "score", title: "Puntaje", align: "right", render: (r) => <strong>{fmtNumber(r.score)}</strong> },
        { key: "rating", title: "Calificación", render: (r) => r.score == null ? "—"
          : <Badge value={r.score >= 90 ? "ok" : r.score >= 75 ? "warning" : "critical"} /> }]} />
      <p className="muted">Puntaje de 90 o más: proveedor confiable · 75 a 89: requiere seguimiento · menos de 75: plan de mejora o sustitución.</p>
    </Page>
  );
}

export function PurchaseBudgetPage() {
  const [on, setOn] = useState(today());
  const [cc, setCc] = useState("");
  const ccs = useOptions("/cost-centers", (x) => `${x.code} ${x.name}`);
  const { data } = useFetch<Json>(`/purchasing/budget-status${qs({ on, cost_center_id: cc })}`);
  const pct = data?.budget ? (Number(data.committed) / Number(data.budget)) * 100 : null;
  return (
    <Page title="Presupuesto de compras" subtitle="Comprometido en órdenes aprobadas frente al presupuesto mensual">
      <div className="filters">
        <label>Mes<input type="date" value={on} onChange={(e) => setOn(e.target.value)} /></label>
        <label>Centro de costo<select value={cc} onChange={(e) => setCc(e.target.value)}><option value="">Sin centro de costo</option>
          {ccs.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
      </div>
      {data && (data.budget == null
        ? <Alert kind="info">No hay presupuesto de compras para ese mes y centro de costo. Regístrelo en Gerencia → Metas y presupuestos.</Alert>
        : <>
          <KeyValues data={data} keys={[["budget", "Presupuesto", fmtMoney], ["committed", "Comprometido", fmtMoney]]} />
          <div className="meter" role="meter" aria-valuenow={pct ?? 0} aria-valuemin={0} aria-valuemax={100} aria-label="Ejecución del presupuesto">
            <span style={{ width: `${Math.min(pct ?? 0, 100)}%` }} className={pct && pct > 100 ? "over" : pct && pct > 85 ? "near" : ""} /></div>
          <p>{fmtNumber(pct)} % ejecutado · disponible {fmtMoney(Number(data.budget) - Number(data.committed))}</p>
          {data.exceeded && <Alert kind="warning">El comprometido supera el presupuesto del mes.</Alert>}
        </>)}
    </Page>
  );
}

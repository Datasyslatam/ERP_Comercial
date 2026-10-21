import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { DocumentActions } from "../components/DocumentActions";
import { Line, LinesEditor, linesPayload } from "../components/LinesEditor";
import { TracePanel } from "../components/TracePanel";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useLookup, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);
const plusDays = (n: number) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);
const SO_STATUSES = ["draft", "confirmed", "partially_dispatched", "dispatched", "closed", "cancelled"];
const QUOTE_STATUSES = ["draft", "sent", "accepted", "rejected", "expired"];

/** Cupo de crédito del cliente: se muestra al vender para anticipar el bloqueo al confirmar. */
function CreditInfo({ customerId, amount }: { customerId: unknown; amount?: number }) {
  const { data } = useFetch<Json>(customerId ? `/sales/customers/${customerId}/credit` : null);
  if (!data || !data.credit_limit || Number(data.credit_limit) <= 0) return null;
  const available = Number(data.available);
  const short = amount !== undefined && amount > available;
  return <Alert kind={short || available <= 0 ? "warning" : "info"}>
    Cupo de crédito {fmtMoney(data.credit_limit)} · comprometido {fmtMoney(data.exposure)} · disponible {fmtMoney(data.available)}
    {short && " — el valor supera el cupo disponible: el pedido no podrá confirmarse."}
  </Alert>;
}

// ------------------------------------------------------------------ cotizaciones
export function QuotesPage() {
  const { can } = useSession();
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const [lines, setLines] = useState<Line[]>([{ item_id: "", quantity: "1", unit_price: "" }]);
  const customers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const customerName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const sites = useOptions("/sites", (x) => x.name);
  const { data, reload } = useFetch<Json>(`/sales/quotes${qs({ status })}`);
  return (
    <Page title="Cotizaciones" subtitle="Ofertas a clientes: vigencia, seguimiento y conversión en pedido" actions={<>
      <select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Todas</option>{QUOTE_STATUSES.map((s) => <option key={s} value={s}>{STATUS[s]}</option>)}
      </select>
      {can("sales.quote.create") && <button onClick={() => setCreating(true)}>Nueva cotización</button>}
    </>}>
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} empty="Sin cotizaciones" columns={[
        { key: "number", title: "Número" }, { key: "customer_id", title: "Cliente", render: (r) => customerName(r.customer_id) },
        { key: "quote_date", title: "Fecha" }, { key: "valid_until", title: "Vigente hasta" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total, r.currency) }]} />
      {creating && (
        <Modal title="Nueva cotización" onClose={() => setCreating(false)}>
          <LinesEditor lines={lines} onChange={setLines} withDiscount priceRequired={false} />
          <p className="muted">Si no indica precio se usa el precio de lista del artículo.</p>
          <Form initial={{ quote_date: today(), valid_until: plusDays(15), currency: "COP" }} fields={[
            { name: "customer_id", label: "Cliente", type: "select", required: true, options: customers },
            { name: "site_id", label: "Sede", type: "select", required: true, options: sites },
            { name: "quote_date", label: "Fecha", type: "date", required: true },
            { name: "valid_until", label: "Vigente hasta", type: "date", required: true },
            { name: "currency", label: "Moneda", required: true }, { name: "contact_name", label: "Contacto del cliente" },
            { name: "notes", label: "Condiciones y observaciones", type: "textarea" }]}
            onSubmit={async (d) => {
              const q = await post("/sales/quotes", { ...d, lines: linesPayload(lines) });
              setCreating(false); setLines([{ item_id: "", quantity: "1", unit_price: "" }]); reload(); setCurrent(q.id);
            }} />
        </Modal>
      )}
      {current && <QuoteModal id={current} onClose={() => setCurrent(null)} onChanged={reload} onOrder={(soId) => nav(`/ventas/pedidos/${soId}`)} />}
    </Page>
  );
}

const STATUS: Record<string, string> = {
  draft: "Borrador", sent: "Enviada", accepted: "Aceptada", rejected: "Perdida", expired: "Vencida", cancelled: "Anulada",
  confirmed: "Confirmado", partially_dispatched: "Despachado parcial", dispatched: "Despachado", closed: "Cerrado",
};

function QuoteModal({ id, onClose, onChanged, onOrder }: { id: number; onClose: () => void; onChanged: () => void; onOrder: (soId: number) => void }) {
  const { can } = useSession();
  const { data: q, reload } = useFetch<Json>(`/sales/quotes/${id}`);
  const itemName = useItemNames();
  const whs = useOptions("/warehouses", (x) => x.name);
  const [converting, setConverting] = useState(false);
  const [losing, setLosing] = useState(false);
  if (!q) return <Modal title="Cotización" onClose={onClose}><p className="muted">Cargando…</p></Modal>;
  const open = ["draft", "sent"].includes(q.status);
  const refresh = () => { reload(); onChanged(); };
  return (
    <Modal title={`Cotización ${q.number}`} onClose={onClose}>
      <div className="row between">
        <span className="row"><Badge value={q.status} />
          <DocumentActions type="sales_quote" id={q.id} number={q.number}
            canSend={can("sales.quote.create") && ["draft", "sent", "accepted"].includes(q.status)} /></span>
        {can("sales.quote.create") && <span className="row">
          {q.status === "draft" && <ActionButton className="secondary" onClick={async () => { await post(`/sales/quotes/${id}/send`); refresh(); }}>Marcar como enviada</ActionButton>}
          {open && can("sales.order.create") && <button onClick={() => setConverting(true)}>Convertir en pedido</button>}
          {open && <button className="secondary" onClick={() => setLosing(true)}>Registrar como perdida</button>}
        </span>}
      </div>
      {q.status === "expired" && <Alert kind="warning">La vigencia terminó el {q.valid_until}. Emita una nueva cotización con precios actualizados.</Alert>}
      <KeyValues data={q} keys={[["quote_date", "Fecha"], ["valid_until", "Vigente hasta"], ["contact_name", "Contacto"], ["currency", "Moneda"],
        ["subtotal", "Subtotal", fmtMoney], ["tax_total", "Impuestos", fmtMoney], ["total", "Total", fmtMoney], ["lost_reason", "Motivo de pérdida"]]} />
      {q.notes && <p className="muted">{q.notes}</p>}
      <DataTable rows={q.lines} columns={[{ key: "line_no", title: "#" }, { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
        { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
        { key: "unit_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.unit_price) },
        { key: "discount_pct", title: "Desc. %", align: "right", render: (r) => fmtNumber(r.discount_pct) }]} />
      {q.sales_order_id && <p><button className="secondary" onClick={() => onOrder(q.sales_order_id)}>Ver pedido generado</button></p>}
      <h3>Trazabilidad</h3>
      <TracePanel type="sales_quote" id={id} />
      {converting && <Modal title="Convertir en pedido" onClose={() => setConverting(false)}>
        <CreditInfo customerId={q.customer_id} amount={Number(q.total)} />
        <Form initial={{ order_date: today() }} fields={[{ name: "warehouse_id", label: "Bodega de despacho", type: "select", required: true, options: whs },
          { name: "order_date", label: "Fecha del pedido", type: "date", required: true }, { name: "promised_date", label: "Fecha prometida", type: "date" },
          { name: "delivery_address", label: "Dirección de entrega (si difiere)" }]}
          onSubmit={async (d) => { const so = await post(`/sales/quotes/${id}/convert`, d); onChanged(); onOrder(so.id); }} />
      </Modal>}
      {losing && <Modal title="Cotización perdida" onClose={() => setLosing(false)}>
        <Form submitLabel="Registrar" fields={[{ name: "reason", label: "Motivo (precio, plazo, competencia…)", type: "textarea", required: true }]}
          onSubmit={async (d) => { await post(`/sales/quotes/${id}/reject`, d); setLosing(false); refresh(); }} />
      </Modal>}
    </Modal>
  );
}

// ------------------------------------------------------------------ pedidos
export function SalesOrdersPage() {
  const { can } = useSession();
  const nav = useNavigate();
  const [status, setStatus] = useState("");
  const [creating, setCreating] = useState(false);
  const [lines, setLines] = useState<Line[]>([{ item_id: "", quantity: "1", unit_price: "" }]);
  const customers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const customerName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const sites = useOptions("/sites", (x) => x.name);
  const whs = useOptions("/warehouses", (x) => x.name);
  const { data, reload } = useFetch<Json>(`/sales/orders${qs({ status })}`);
  return (
    <Page title="Pedidos de venta" actions={<>
      <select aria-label="Estado" value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">Todos</option>{SO_STATUSES.map((s) => <option key={s} value={s}>{STATUS[s]}</option>)}
      </select>
      {can("sales.order.create") && <button onClick={() => setCreating(true)}>Nuevo pedido</button>}
    </>}>
      <DataTable rows={data?.items} onRowClick={(r) => nav(`/ventas/pedidos/${r.id}`)} columns={[{ key: "number", title: "Número" },
        { key: "customer_id", title: "Cliente", render: (r) => customerName(r.customer_id) }, { key: "order_date", title: "Fecha" },
        { key: "promised_date", title: "Prometido" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total, r.currency) }]} />
      {creating && (
        <Modal title="Nuevo pedido de venta" onClose={() => setCreating(false)}>
          <LinesEditor lines={lines} onChange={setLines} withDiscount priceRequired={false} />
          <p className="muted">Si no indica precio se usa el precio de lista. Para respetar condiciones ofrecidas, conviértalo desde la cotización.
            El cupo de crédito se valida al confirmar.</p>
          <Form initial={{ order_date: today(), currency: "COP" }} fields={[
            { name: "customer_id", label: "Cliente", type: "select", required: true, options: customers },
            { name: "site_id", label: "Sede", type: "select", required: true, options: sites },
            { name: "warehouse_id", label: "Bodega", type: "select", required: true, options: whs },
            { name: "order_date", label: "Fecha", type: "date", required: true }, { name: "promised_date", label: "Fecha prometida", type: "date" },
            { name: "currency", label: "Moneda", required: true }, { name: "delivery_address", label: "Dirección de entrega" }]}
            onSubmit={async (d) => {
              const so = await post("/sales/orders", { ...d, lines: linesPayload(lines) });
              setCreating(false); reload(); nav(`/ventas/pedidos/${so.id}`);
            }} />
        </Modal>
      )}
    </Page>
  );
}

export function SalesOrderDetailPage() {
  const { id } = useParams();
  const { can } = useSession();
  const nav = useNavigate();
  const { data: so, reload, error } = useFetch<Json>(`/sales/orders/${id}`);
  const itemName = useItemNames();
  const customerName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const [closing, setClosing] = useState<"close" | "cancel" | null>(null);
  if (error) return <Alert>{error}</Alert>;
  if (!so) return <p className="muted">Cargando…</p>;
  const act = (path: string, body?: Json) => async () => { await post(`/sales/orders/${so.id}/${path}`, body); reload(); };
  const open = ["confirmed", "partially_dispatched"].includes(so.status);
  return (
    <Page title={`Pedido ${so.number}`} subtitle={customerName(so.customer_id)} actions={<>
      <Badge value={so.status} />
      <DocumentActions type="sales_order" id={so.id} number={so.number}
        canSend={can("sales.order.create") && ["confirmed", "partially_dispatched", "dispatched", "closed"].includes(so.status)}
        sendHint={so.status === "draft" ? "Se envía al cliente una vez confirmado" : undefined} />
      {so.status === "draft" && can("sales.order.approve") && <ActionButton onClick={act("confirm")}>Confirmar y reservar</ActionButton>}
      {open && can("logistics.dispatch.create") &&
        <ActionButton onClick={async () => { const d = await post("/logistics/dispatches", { sales_order_id: so.id }); nav(`/logistica/despachos/${d.id}`); }}>Generar despacho</ActionButton>}
      {open && can("sales.order.approve") && <button className="secondary" onClick={() => setClosing("close")}>Cerrar saldo</button>}
      {["draft", "confirmed"].includes(so.status) && can("sales.order.void") && <button className="danger" onClick={() => setClosing("cancel")}>Anular</button>}
    </>}>
      {so.status === "draft" && <CreditInfo customerId={so.customer_id} amount={Number(so.total) * Number(so.exchange_rate)} />}
      <KeyValues data={so} keys={[["order_date", "Fecha"], ["promised_date", "Prometido"], ["delivery_address", "Entrega"], ["currency", "Moneda"],
        ["subtotal", "Subtotal", fmtMoney], ["tax_total", "Impuestos", fmtMoney], ["total", "Total", fmtMoney], ["notes", "Notas"]]} />
      <h3>Líneas y cumplimiento</h3>
      <DataTable rows={so.lines} columns={[{ key: "line_no", title: "#" }, { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
        { key: "quantity", title: "Pedido", align: "right", render: (r) => fmtNumber(r.quantity) },
        { key: "unit_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.unit_price) },
        { key: "discount_pct", title: "Desc. %", align: "right", render: (r) => fmtNumber(r.discount_pct) },
        { key: "qty_reserved", title: "Reserva vigente", align: "right", render: (r) => fmtNumber(Math.max(Number(r.qty_reserved) - Number(r.qty_dispatched), 0)) },
        { key: "qty_dispatched", title: "Despachado", align: "right", render: (r) => fmtNumber(r.qty_dispatched) },
        { key: "qty_invoiced", title: "Facturado", align: "right", render: (r) => fmtNumber(r.qty_invoiced) },
        { key: "qty_returned", title: "Devuelto", align: "right", render: (r) => fmtNumber(r.qty_returned) },
        { key: "pending", title: "Pendiente", align: "right", render: (r) => fmtNumber(Number(r.quantity) - Number(r.qty_dispatched)) }]} />
      <h3>Trazabilidad</h3>
      <TracePanel type="sales_order" id={so.id} />
      <p className="muted">Creado {fmtDate(so.created_at)}</p>
      {closing && <Modal title={closing === "close" ? "Cerrar saldo del pedido" : "Anular pedido"} onClose={() => setClosing(null)}>
        <p className="muted">{closing === "close"
          ? "El saldo no despachado se da por terminado y se liberan sus reservas de inventario. Lo ya despachado y facturado se conserva."
          : "Se anula el pedido completo y se liberan sus reservas. Solo es posible si no tiene despachos."}</p>
        <Form submitLabel={closing === "close" ? "Cerrar saldo" : "Anular"} fields={[{ name: "reason", label: "Motivo", type: "textarea", required: true }]}
          onSubmit={async (d) => { await post(`/sales/orders/${so.id}/${closing}`, d); setClosing(null); reload(); }} />
      </Modal>}
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

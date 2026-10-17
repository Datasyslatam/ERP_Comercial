import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Line, LinesEditor, linesPayload } from "../components/LinesEditor";
import { ActionButton, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtMoney } from "../lib/format";
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

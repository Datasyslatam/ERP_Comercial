import { useState } from "react";
import { ActionButton, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

export function StockPage() {
  const [itemId, setItemId] = useState("");
  const [belowMin, setBelowMin] = useState(false);
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const { data } = useFetch<Json[]>(`/inventory/stock${qs({ item_id: itemId, below_min: belowMin || undefined })}`);
  const consistency = useFetch<Json>("/inventory/consistency");
  const expiring = useFetch<Json[]>("/inventory/expiring?days=30");
  const replen = useFetch<Json[]>("/inventory/replenishment");
  const start = today().slice(0, 8) + "01";
  const kardex = useFetch<Json>(itemId ? `/inventory/kardex/${itemId}?start=${start}&end=${today()}` : null);
  const total = (data ?? []).reduce((s, r) => s + Number(r.value), 0);
  return (
    <Page title="Existencias y kardex" subtitle="Calculado desde el libro de movimientos de inventario" actions={<>
      <select aria-label="Artículo" value={itemId} onChange={(e) => setItemId(e.target.value)}>
        <option value="">Todos los artículos</option>{items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <label className="check"><input type="checkbox" checked={belowMin} onChange={(e) => setBelowMin(e.target.checked)} />Bajo mínimo</label>
    </>}>
      {consistency.data && <p className={consistency.data.consistent ? "alert alert-ok" : "alert alert-error"}>
        {consistency.data.consistent ? "Saldos consistentes con el historial de movimientos"
          : `Inconsistencias detectadas: ${consistency.data.differences.length}`}</p>}
      <p><strong>Valor del inventario listado: {fmtMoney(total)}</strong></p>
      <DataTable rows={data} columns={[{ key: "sku", title: "SKU" }, { key: "name", title: "Artículo" },
        { key: "location_code", title: "Ubicación" }, { key: "lot_number", title: "Lote" }, { key: "expiry_date", title: "Vence" },
        { key: "lot_status", title: "Estado lote", render: (r) => r.lot_status ? <Badge value={r.lot_status} /> : "—" },
        { key: "qty_on_hand", title: "Existencia", align: "right", render: (r) => fmtNumber(r.qty_on_hand) },
        { key: "qty_reserved", title: "Reservado", align: "right", render: (r) => fmtNumber(r.qty_reserved) },
        { key: "qty_available", title: "Disponible", align: "right", render: (r) => fmtNumber(r.qty_available) },
        { key: "value", title: "Valor", align: "right", render: (r) => fmtMoney(r.value) }]} />
      {kardex.data && <>
        <h3>Kardex del mes</h3>
        <p className="muted">Saldo inicial {fmtNumber(kardex.data.opening_qty)} · {fmtMoney(kardex.data.opening_value)}</p>
        <DataTable rows={kardex.data.moves} columns={[{ key: "date", title: "Fecha", render: (r) => fmtDate(r.date) },
          { key: "type", title: "Tipo" }, { key: "reference", title: "Documento" }, { key: "reason", title: "Motivo" },
          { key: "in", title: "Entrada", align: "right", render: (r) => fmtNumber(r.in) }, { key: "out", title: "Salida", align: "right", render: (r) => fmtNumber(r.out) },
          { key: "unit_cost", title: "Costo unit.", align: "right", render: (r) => fmtMoney(r.unit_cost) },
          { key: "balance_qty", title: "Saldo", align: "right", render: (r) => fmtNumber(r.balance_qty) },
          { key: "balance_value", title: "Saldo valor", align: "right", render: (r) => fmtMoney(r.balance_value) }]} />
      </>}
      <h3>Reabastecimiento sugerido</h3>
      <DataTable rows={replen.data} empty="Ningún artículo bajo el mínimo" columns={[{ key: "sku", title: "SKU" }, { key: "name", title: "Artículo" },
        { key: "available", title: "Disponible", align: "right", render: (r) => fmtNumber(r.available) },
        { key: "min_stock", title: "Mínimo", align: "right", render: (r) => fmtNumber(r.min_stock) },
        { key: "suggested_order", title: "Sugerido", align: "right", render: (r) => fmtNumber(r.suggested_order) }]} />
      <h3>Lotes próximos a vencer (30 días)</h3>
      <DataTable rows={expiring.data} empty="Sin lotes próximos a vencer" columns={[{ key: "sku", title: "SKU" }, { key: "lot_number", title: "Lote" },
        { key: "expiry_date", title: "Vence" }, { key: "days_left", title: "Días" }, { key: "qty", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.qty) }]} />
    </Page>
  );
}

export function InventoryDocumentsPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/inventory/documents");
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const locs = useOptions("/locations?limit=500", (x) => `${x.code} ${x.name}`);
  const ccs = useOptions("/cost-centers", (x) => `${x.code} ${x.name}`);
  const [creating, setCreating] = useState(false);
  return (
    <Page title="Movimientos y ajustes" subtitle="Transferencias, ajustes (con aprobación), consumos internos y bajas"
          actions={can("inventory.document.create") && <button onClick={() => setCreating(true)}>Nuevo documento</button>}>
      <DataTable rows={data?.items} columns={[{ key: "number", title: "Número" }, { key: "doc_type", title: "Tipo" },
        { key: "doc_date", title: "Fecha" }, { key: "reason", title: "Motivo" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "a", title: "", render: (r) => <span className="row">
          {r.status === "draft" && ["adjustment", "scrap"].includes(r.doc_type) && can("inventory.document.approve") &&
            <ActionButton onClick={async () => { await post(`/inventory/documents/${r.id}/approve`); reload(); }}>Aprobar</ActionButton>}
          {(r.status === "approved" || (r.status === "draft" && ["transfer", "consumption"].includes(r.doc_type))) && can("inventory.document.post") &&
            <ActionButton onClick={async () => { await post(`/inventory/documents/${r.id}/post`); reload(); }}>Aplicar</ActionButton>}
        </span> }]} />
      {creating && (
        <Modal title="Documento de inventario" onClose={() => setCreating(false)}>
          <Form initial={{ doc_date: today(), doc_type: "transfer" }} fields={[
            { name: "doc_type", label: "Tipo", type: "select", required: true, options: [["transfer", "Transferencia"], ["adjustment", "Ajuste (+ entrada / − salida)"],
              ["consumption", "Consumo interno"], ["scrap", "Baja / merma"]].map(([v, l]) => ({ value: v, label: l })) },
            { name: "doc_date", label: "Fecha", type: "date", required: true }, { name: "reason", label: "Motivo", required: true },
            { name: "cost_center_id", label: "Centro de costo (consumos)", type: "select", options: ccs },
            { name: "item_id", label: "Artículo", type: "select", required: true, options: items },
            { name: "quantity", label: "Cantidad", type: "number", required: true },
            { name: "from_location_id", label: "Ubicación origen", type: "select", options: locs },
            { name: "to_location_id", label: "Ubicación destino", type: "select", options: locs },
            { name: "unit_cost", label: "Costo unitario (solo ajustes de entrada)", type: "number" }]}
            onSubmit={async (d) => {
              const { item_id, quantity, from_location_id, to_location_id, unit_cost, ...head } = d;
              await post("/inventory/documents", { ...head, lines: [{ item_id, quantity, from_location_id, to_location_id, unit_cost }] });
              setCreating(false); reload();
            }} />
        </Modal>
      )}
    </Page>
  );
}

export function CountsPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/inventory/counts");
  const whs = useOptions("/warehouses", (x) => x.name);
  const [current, setCurrent] = useState<number | null>(null);
  const detail = useFetch<Json>(current ? `/inventory/counts/${current}` : null);
  const [counted, setCounted] = useState<Record<number, string>>({});
  return (
    <Page title="Conteos físicos" subtitle="Conteo ciego: quien cuenta no ve la existencia del sistema; aprueba un usuario distinto">
      {can("inventory.count.create") && <Form fields={[{ name: "warehouse_id", label: "Bodega", type: "select", required: true, options: whs },
        { name: "count_date", label: "Fecha", type: "date", required: true }]} initial={{ count_date: today() }} submitLabel="Abrir conteo"
        onSubmit={async (d) => { const c = await post("/inventory/counts", d); setCurrent(c.id); reload(); }} />}
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "number", title: "Número" },
        { key: "count_date", title: "Fecha" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {detail.data && current && (
        <Modal title={`Conteo ${detail.data.number}`} onClose={() => setCurrent(null)}>
          <DataTable rows={detail.data.lines} columns={[{ key: "item_id", title: "Artículo" }, { key: "location_id", title: "Ubicación" },
            { key: "lot_id", title: "Lote" },
            ...(detail.data.lines[0] && "system_qty" in detail.data.lines[0] ? [{ key: "system_qty", title: "Sistema", align: "right" as const, render: (r: Json) => fmtNumber(r.system_qty) }] : []),
            { key: "counted_qty", title: "Contado", align: "right", render: (r) => detail.data.status === "open"
              ? <input type="number" step="any" aria-label="Cantidad contada" defaultValue={r.counted_qty ?? ""}
                       onChange={(e) => setCounted({ ...counted, [r.id]: e.target.value })} /> : fmtNumber(r.counted_qty) }]} />
          {detail.data.status === "open" && <div className="row">
            <ActionButton onClick={async () => {
              const entries = detail.data.lines.filter((l: Json) => counted[l.id] !== undefined).map((l: Json) => ({
                item_id: l.item_id, location_id: l.location_id, lot_id: l.lot_id, counted_qty: counted[l.id] }));
              await post(`/inventory/counts/${current}/entries`, { entries }); detail.reload();
            }}>Guardar conteo</ActionButton>
            {can("inventory.count.approve") && <ActionButton confirm="Se generarán los ajustes por diferencias. ¿Continuar?"
              onClick={async () => { await post(`/inventory/counts/${current}/close`); detail.reload(); reload(); }}>Aprobar y ajustar</ActionButton>}
          </div>}
        </Modal>
      )}
    </Page>
  );
}

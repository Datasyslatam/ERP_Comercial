import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { TracePanel } from "../components/TracePanel";
import { ActionButton, Alert, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useLookup, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

export function StockPage() {
  const [itemId, setItemId] = useState("");
  const [belowMin, setBelowMin] = useState(false);
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const { data } = useFetch<Json[]>(`/inventory/stock${qs({ item_id: itemId, below_min: belowMin || undefined })}`);
  const consistency = useFetch<Json>("/inventory/consistency");
  const total = (data ?? []).reduce((s, r) => s + Number(r.value), 0);
  return (
    <Page title="Existencias" subtitle="Saldos por ubicación y lote, calculados desde el libro de movimientos" actions={<>
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
    </Page>
  );
}

const MOVE_SOURCES: Record<string, [string, string]> = {
  goods_receipt: ["Recepción", "goods_receipt"], dispatch: ["Despacho", "dispatch"], customer_return: ["Devolución", "customer_return"],
  inspection: ["Inspección", "inspection"],
};

/** El kardex expone el origen del movimiento como "tipo:id". */
const sourceOf = (r: Json): [string, string] => {
  const [t, id] = String(r.source ?? "").split(":");
  return [t, id];
};

export function KardexPage() {
  const [itemId, setItemId] = useState("");
  const [start, setStart] = useState(today().slice(0, 8) + "01");
  const [end, setEnd] = useState(today());
  const [traceOf, setTraceOf] = useState<Json | null>(null);
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const { data: k } = useFetch<Json>(itemId ? `/inventory/kardex/${itemId}${qs({ start, end })}` : null);
  return (
    <Page title="Kardex" subtitle="Movimientos valorizados por artículo con saldo y costo promedio">
      <div className="filters">
        <label>Artículo<select value={itemId} onChange={(e) => setItemId(e.target.value)}>
          <option value="">Seleccione…</option>{items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
        <label>Desde<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>Hasta<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
      </div>
      {k && <>
        <div className="summary"><span>Saldo inicial <strong>{fmtNumber(k.opening_qty)}</strong> · {fmtMoney(k.opening_value)}</span>
          {k.moves.length > 0 && <span>Saldo final <strong>{fmtNumber(k.moves[k.moves.length - 1].balance_qty)}</strong> · {fmtMoney(k.moves[k.moves.length - 1].balance_value)}</span>}</div>
        <DataTable rows={k.moves} empty="Sin movimientos en el periodo" onRowClick={(r) => MOVE_SOURCES[sourceOf(r)[0]] && setTraceOf(r)} columns={[
          { key: "date", title: "Fecha", render: (r) => fmtDate(r.date) }, { key: "type", title: "Tipo" }, { key: "reference", title: "Documento" },
          { key: "reason", title: "Motivo" },
          { key: "in", title: "Entrada", align: "right", render: (r) => fmtNumber(r.in) }, { key: "out", title: "Salida", align: "right", render: (r) => fmtNumber(r.out) },
          { key: "unit_cost", title: "Costo unit.", align: "right", render: (r) => fmtMoney(r.unit_cost) },
          { key: "balance_qty", title: "Saldo", align: "right", render: (r) => fmtNumber(r.balance_qty) },
          { key: "balance_value", title: "Saldo valor", align: "right", render: (r) => fmtMoney(r.balance_value) }]} />
        <p className="muted">Haga clic en un movimiento de recepción, despacho, devolución o inspección para ver su cadena documental.</p>
      </>}
      {traceOf && <Modal title={`${MOVE_SOURCES[sourceOf(traceOf)[0]][0]} ${traceOf.reference ?? ""}`} onClose={() => setTraceOf(null)}>
        <TracePanel type={MOVE_SOURCES[sourceOf(traceOf)[0]][1]} id={sourceOf(traceOf)[1]} />
      </Modal>}
    </Page>
  );
}

export function ReplenishmentPage() {
  const { can } = useSession();
  const nav = useNavigate();
  const { data, reload } = useFetch<Json[]>("/inventory/replenishment");
  const sites = useOptions("/sites", (x) => x.name);
  const [qty, setQty] = useState<Record<number, string>>({});
  const [site, setSite] = useState("");
  const [neededBy, setNeededBy] = useState("");
  const [error, setError] = useState<string | null>(null);
  const valueOf = (r: Json) => qty[r.item_id] ?? String(r.suggested_order);
  return (
    <Page title="Reabastecimiento" subtitle="Artículos con disponible por debajo del mínimo y cantidad sugerida hasta el máximo">
      <DataTable rows={data} empty="Ningún artículo bajo el mínimo" columns={[{ key: "sku", title: "SKU" }, { key: "name", title: "Artículo" },
        { key: "available", title: "Disponible", align: "right", render: (r) => fmtNumber(r.available) },
        { key: "min_stock", title: "Mínimo", align: "right", render: (r) => fmtNumber(r.min_stock) },
        { key: "max_stock", title: "Máximo", align: "right", render: (r) => fmtNumber(r.max_stock) },
        { key: "suggested_order", title: "Sugerido", align: "right", render: (r) => fmtNumber(r.suggested_order) },
        { key: "qty", title: "A solicitar", render: (r) => <input type="number" min="0" step="any" aria-label={`Cantidad ${r.sku}`} style={{ width: 110 }}
          value={valueOf(r)} onChange={(e) => setQty({ ...qty, [r.item_id]: e.target.value })} /> }]} />
      {!!data?.length && can("purchasing.requisition.create") && <div className="filters">
        <label>Sede solicitante<select value={site} onChange={(e) => setSite(e.target.value)}><option value="">—</option>
          {sites.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
        <label>Requerida para<input type="date" value={neededBy} onChange={(e) => setNeededBy(e.target.value)} /></label>
        <ActionButton onClick={async () => {
          setError(null);
          if (!site) { setError("Seleccione la sede solicitante"); return; }
          const quantities = Object.fromEntries((data ?? []).map((r) => [r.item_id, valueOf(r) || "0"]));
          const req = await post("/purchasing/requisitions/from-replenishment", { site_id: Number(site), needed_by: neededBy || null, quantities });
          reload(); nav(`/compras/solicitudes?focus=${req.id}`);
        }}>Generar solicitud de compra</ActionButton>
        <Alert>{error}</Alert>
      </div>}
      <p className="muted">La solicitud queda en borrador con el último precio de compra como estimado; siga el flujo normal de aprobación en Compras.</p>
    </Page>
  );
}

export function ExpiringPage() {
  const [days, setDays] = useState("60");
  const { data } = useFetch<Json[]>(`/inventory/expiring?days=${Number(days) || 0}`);
  return (
    <Page title="Vencimientos" subtitle="Lotes con existencia que vencen en el horizonte indicado (FEFO: despachar primero lo que vence antes)">
      <div className="filters"><label>Horizonte (días)<input type="number" min="0" max="365" value={days} onChange={(e) => setDays(e.target.value)} /></label></div>
      <DataTable rows={data} empty="Sin lotes por vencer en el horizonte" columns={[{ key: "sku", title: "SKU" }, { key: "name", title: "Artículo" },
        { key: "lot_number", title: "Lote" }, { key: "expiry_date", title: "Vence" },
        { key: "days_left", title: "Días", align: "right", render: (r) => <span className={Number(r.days_left) <= 7 ? "warn-text" : ""}>{r.days_left}</span> },
        { key: "status", title: "Estado lote", render: (r) => <Badge value={r.status} /> },
        { key: "qty", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.qty) }]} />
      <p className="muted">Los lotes vencidos o en cuarentena se bloquean desde Calidad → Inspecciones (estado del lote).</p>
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
  const itemName = useItemNames();
  const locName = useLookup("/locations?limit=500", (x) => x.code);
  const lotName = useLookup("/inventory/lots?limit=500", (x) => x.lot_number);
  return (
    <Page title="Conteos físicos" subtitle="Conteo ciego: quien cuenta no ve la existencia del sistema; aprueba un usuario distinto">
      {can("inventory.count.create") && <Form fields={[{ name: "warehouse_id", label: "Bodega", type: "select", required: true, options: whs },
        { name: "count_date", label: "Fecha", type: "date", required: true }]} initial={{ count_date: today() }} submitLabel="Abrir conteo"
        onSubmit={async (d) => { const c = await post("/inventory/counts", d); setCurrent(c.id); reload(); }} />}
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "number", title: "Número" },
        { key: "count_date", title: "Fecha" }, { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> }]} />
      {detail.data && current && (
        <Modal title={`Conteo ${detail.data.number}`} onClose={() => setCurrent(null)}>
          <DataTable rows={detail.data.lines} columns={[{ key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
            { key: "location_id", title: "Ubicación", render: (r) => locName(r.location_id) },
            { key: "lot_id", title: "Lote", render: (r) => lotName(r.lot_id) },
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

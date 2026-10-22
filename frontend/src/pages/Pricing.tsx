import { useState } from "react";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { Json, patch, post, put } from "../lib/api";
import { fmtMoney, fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useLookup, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);

// ------------------------------------------------------------------ listas de precios
export function PriceListsPage() {
  const { can } = useSession();
  const lists = useFetch<Json[]>("/sales/price-lists");
  const [creating, setCreating] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  return (
    <Page title="Listas de precios" subtitle="Precios de venta por cliente y moneda, con tramos por cantidad (descuento por volumen)"
          actions={can("sales.pricing.admin") && <button onClick={() => setCreating(true)}>Nueva lista</button>}>
      <Alert kind="info">Al cotizar o vender sin digitar el precio se usa la lista asignada al cliente; si no tiene, la lista
        predeterminada de la moneda; y si el artículo no está en ninguna, su precio base.</Alert>
      <DataTable rows={lists.data} onRowClick={(r) => setCurrent(r.id)} empty="Sin listas de precios" columns={[
        { key: "code", title: "Código" }, { key: "name", title: "Nombre" }, { key: "currency", title: "Moneda" },
        { key: "valid_from", title: "Desde" }, { key: "valid_to", title: "Hasta", render: (r) => r.valid_to ?? "Sin vencimiento" },
        { key: "is_default", title: "Predeterminada", render: (r) => r.is_default ? <Badge value="ok" /> : "" },
        { key: "items_count", title: "Precios", align: "right" }, { key: "customers_count", title: "Clientes", align: "right" },
        { key: "is_active", title: "Estado", render: (r) => <Badge value={r.is_active ? "active" : "inactive"} /> }]} />
      <PriceCheck />
      {creating && <Modal title="Nueva lista de precios" onClose={() => setCreating(false)}>
        <Form initial={{ currency: "COP", valid_from: today() }} fields={[
          { name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
          { name: "currency", label: "Moneda", required: true }, { name: "valid_from", label: "Vigente desde", type: "date", required: true },
          { name: "valid_to", label: "Vigente hasta (opcional)", type: "date" },
          { name: "is_default", label: "Lista predeterminada de la moneda", type: "checkbox" },
          { name: "notes", label: "Notas", type: "textarea" }]}
          onSubmit={async (d) => { const pl = await post("/sales/price-lists", d); setCreating(false); lists.reload(); setCurrent(pl.id); }} />
      </Modal>}
      {current && <PriceListModal id={current} onClose={() => setCurrent(null)} onChanged={lists.reload} />}
    </Page>
  );
}

interface Tier { item_id: string; min_qty: string; unit_price: string }

function PriceListModal({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { can } = useSession();
  const admin = can("sales.pricing.admin");
  const { data: pl, reload } = useFetch<Json>(`/sales/price-lists/${id}`);
  const items = useOptions("/items?active=true&limit=500", (x) => `${x.sku} · ${x.name}`);
  const customers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const itemName = useItemNames();
  const [tiers, setTiers] = useState<Tier[] | null>(null);
  const [assigning, setAssigning] = useState<Set<number> | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!pl) return <Modal title="Lista de precios" onClose={onClose}><p className="muted">Cargando…</p></Modal>;
  const refresh = () => { reload(); onChanged(); };
  const editingTiers = tiers ?? pl.items.map((t: Json) => ({ item_id: String(t.item_id), min_qty: String(Number(t.min_qty)), unit_price: String(Number(t.unit_price)) }));
  const setT = (i: number, k: keyof Tier, v: string) => setTiers(editingTiers.map((t: Tier, j: number) => (j === i ? { ...t, [k]: v } : t)));
  return (
    <Modal title={`${pl.code} · ${pl.name}`} onClose={onClose}>
      <div className="row between">
        <span className="row"><Badge value={pl.is_active ? "active" : "inactive"} />{pl.is_default && <span className="chip">Predeterminada {pl.currency}</span>}</span>
        {admin && <span className="row">
          {!pl.is_default && <ActionButton className="secondary" onClick={async () => { await patch(`/sales/price-lists/${id}`, { is_default: true }); refresh(); }}>Marcar como predeterminada</ActionButton>}
          <ActionButton className="secondary" onClick={async () => { await patch(`/sales/price-lists/${id}`, { is_active: !pl.is_active }); refresh(); }}>
            {pl.is_active ? "Desactivar" : "Activar"}</ActionButton></span>}
      </div>
      <KeyValues data={pl} keys={[["currency", "Moneda"], ["valid_from", "Vigente desde"], ["valid_to", "Vigente hasta"], ["notes", "Notas"]]} />
      <h3>Precios por artículo y cantidad</h3>
      {admin ? <div className="lines">
        <table><thead><tr><th>Artículo</th><th className="num">Desde cantidad</th><th className="num">Precio unitario</th><th /></tr></thead>
          <tbody>{editingTiers.map((t: Tier, i: number) => <tr key={i}>
            <td><select aria-label="Artículo" value={t.item_id} onChange={(e) => setT(i, "item_id", e.target.value)}>
              <option value="">—</option>{items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></td>
            <td><input aria-label="Desde cantidad" type="number" step="any" min="0" value={t.min_qty} onChange={(e) => setT(i, "min_qty", e.target.value)} /></td>
            <td><input aria-label="Precio unitario" type="number" step="any" min="0" value={t.unit_price} onChange={(e) => setT(i, "unit_price", e.target.value)} /></td>
            <td><button type="button" className="secondary" aria-label="Quitar precio" onClick={() => setTiers(editingTiers.filter((_: Tier, j: number) => j !== i))}>✕</button></td>
          </tr>)}</tbody></table>
        <div className="row">
          <button type="button" className="secondary" onClick={() => setTiers([...editingTiers, { item_id: "", min_qty: "1", unit_price: "" }])}>+ Precio</button>
          {tiers && <ActionButton onClick={async () => {
            setError(null);
            const rows = editingTiers.filter((t: Tier) => t.item_id && t.unit_price !== "");
            try { await put(`/sales/price-lists/${id}/items`, { items: rows.map((t: Tier) => ({ item_id: Number(t.item_id), min_qty: t.min_qty || "1", unit_price: t.unit_price })) }); setTiers(null); refresh(); }
            catch (e) { setError((e as Error).message); }
          }}>Guardar precios</ActionButton>}
          {tiers && <button className="secondary" onClick={() => setTiers(null)}>Descartar</button>}
        </div>
        <p className="muted">Para un descuento por volumen agregue el mismo artículo con una cantidad mínima mayor y un precio menor.</p>
        <Alert>{error}</Alert>
      </div> : <DataTable rows={pl.items} empty="Sin precios" columns={[{ key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
        { key: "min_qty", title: "Desde cantidad", align: "right", render: (r) => fmtNumber(r.min_qty) },
        { key: "unit_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.unit_price, pl.currency) }]} />}
      <h3>Clientes con esta lista ({pl.customers.length})</h3>
      {assigning ? <>
        <div className="checklist">{customers.map((c) => <label key={c.value} className="check">
          <input type="checkbox" checked={assigning.has(c.value)} onChange={(e) => {
            const next = new Set(assigning); if (e.target.checked) next.add(c.value); else next.delete(c.value); setAssigning(next); }} />{c.label}</label>)}</div>
        <div className="row"><ActionButton onClick={async () => { await put(`/sales/price-lists/${id}/customers`, { customer_ids: [...assigning] }); setAssigning(null); refresh(); }}>Guardar clientes</ActionButton>
          <button className="secondary" onClick={() => setAssigning(null)}>Cancelar</button></div>
      </> : <>
        <DataTable rows={pl.customers} empty="Ningún cliente asignado: usan la lista predeterminada" columns={[{ key: "legal_name", title: "Cliente" }]} />
        {admin && <p><button className="secondary" onClick={() => setAssigning(new Set(pl.customers.map((c: Json) => c.id)))}>Asignar clientes</button></p>}
      </>}
    </Modal>
  );
}

/** Consulta rápida: precio y descuento que obtendría un cliente por un artículo y cantidad. */
function PriceCheck() {
  const customers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const items = useOptions("/items?active=true&limit=500", (x) => `${x.sku} · ${x.name}`);
  const [result, setResult] = useState<Json | null>(null);
  return (
    <>
      <h3>Consultar precio</h3>
      <Form initial={{ currency: "COP", quantity: "1" }} submitLabel="Consultar" fields={[
        { name: "customer_id", label: "Cliente", type: "select", options: customers },
        { name: "item_id", label: "Artículo", type: "select", required: true, options: items },
        { name: "quantity", label: "Cantidad", type: "number", required: true }, { name: "currency", label: "Moneda", required: true }]}
        onSubmit={async (d) => setResult(await post("/sales/pricing", { customer_id: d.customer_id ?? null, currency: d.currency,
          lines: [{ item_id: d.item_id, quantity: d.quantity }] }))} />
      {result && (() => {
        const ln = result.lines[0];
        const net = Number(ln.unit_price) * (1 - Number(ln.discount_pct) / 100);
        return <div className="summary">
          <span>Precio <strong>{fmtMoney(ln.unit_price)}</strong> ({ln.source === "price_list" ? `lista ${result.lists.find((l: Json) => l.id === ln.price_list_id)?.code ?? ""}` : "precio base del artículo"})</span>
          <span>Descuento <strong>{fmtNumber(ln.discount_pct)} %</strong>{ln.promotion ? ` · ${ln.promotion}` : ""}</span>
          <span>Neto unitario <strong>{fmtMoney(net)}</strong> antes de impuestos</span>
        </div>;
      })()}
    </>
  );
}

// ------------------------------------------------------------------ promociones
export function PromotionsPage() {
  const { can } = useSession();
  const promos = useFetch<Json[]>("/sales/promotions");
  const items = useOptions("/items?active=true&limit=500", (x) => `${x.sku} · ${x.name}`);
  const cats = useOptions("/item-categories?limit=500", (x) => `${x.code} ${x.name}`);
  const customers = useOptions("/parties?limit=500", (x) => x.legal_name);
  const itemName = useItemNames();
  const catName = useLookup("/item-categories?limit=500", (x) => x.name);
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const [creating, setCreating] = useState(false);
  const STATE: Record<string, string> = { active: "active", scheduled: "pending", expired: "expired", inactive: "inactive" };
  return (
    <Page title="Promociones" subtitle="Descuentos con vigencia por artículo, categoría o todo el catálogo"
          actions={can("sales.pricing.admin") && <button onClick={() => setCreating(true)}>Nueva promoción</button>}>
      <Alert kind="info">Se aplican solas cuando la línea no trae un descuento digitado. Si varias aplican, gana la de mayor porcentaje.
        El pedido creado desde una cotización conserva el descuento cotizado.</Alert>
      <DataTable rows={promos.data} empty="Sin promociones" columns={[
        { key: "code", title: "Código" }, { key: "name", title: "Nombre" },
        { key: "discount_pct", title: "Descuento %", align: "right", render: (r) => fmtNumber(r.discount_pct) },
        { key: "scope", title: "Aplica a", render: (r) => r.item_id ? itemName(r.item_id) : r.category_id ? `Categoría ${catName(r.category_id)}` : "Todo el catálogo" },
        { key: "min_qty", title: "Desde cantidad", align: "right", render: (r) => r.min_qty ? fmtNumber(r.min_qty) : "—" },
        { key: "customer_id", title: "Cliente", render: (r) => r.customer_id ? partyName(r.customer_id) : "Todos" },
        { key: "valid", title: "Vigencia", render: (r) => `${r.valid_from} a ${r.valid_to}` },
        { key: "state", title: "Estado", render: (r) => <span title={r.state}><Badge value={STATE[r.state] ?? r.state} /></span> },
        { key: "a", title: "", render: (r) => can("sales.pricing.admin") && <ActionButton className="secondary"
          onClick={async () => { await patch(`/sales/promotions/${r.id}`, { is_active: !r.is_active }); promos.reload(); }}>
          {r.is_active ? "Desactivar" : "Activar"}</ActionButton> }]} />
      {creating && <Modal title="Nueva promoción" onClose={() => setCreating(false)}>
        <Form initial={{ valid_from: today() }} fields={[
          { name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
          { name: "discount_pct", label: "Descuento %", type: "number", required: true },
          { name: "valid_from", label: "Desde", type: "date", required: true }, { name: "valid_to", label: "Hasta", type: "date", required: true },
          { name: "item_id", label: "Artículo (opcional)", type: "select", options: items },
          { name: "category_id", label: "o categoría (opcional)", type: "select", options: cats },
          { name: "min_qty", label: "Desde cantidad (opcional)", type: "number" },
          { name: "customer_id", label: "Solo para el cliente (opcional)", type: "select", options: customers }]}
          onSubmit={async (d) => { await post("/sales/promotions", d); setCreating(false); promos.reload(); }} />
        <p className="muted">Sin artículo ni categoría, la promoción aplica a todo el catálogo.</p>
      </Modal>}
    </Page>
  );
}

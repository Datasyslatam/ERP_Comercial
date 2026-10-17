import { useState } from "react";
import { DataTable, Form, Modal, Page } from "../components/ui";
import { Json, post } from "../lib/api";
import { fmtNumber } from "../lib/format";
import { useFetch, useItemNames, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

interface Component { component_item_id: string; quantity: string; scrap_pct: string }

/** Listas de materiales: componentes por cantidad base del producto, con % de desperdicio esperado.
 *  Al crear una orden de producción con BOM, los materiales planificados se calculan desde aquí. */
export function BomsPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json[]>("/operations/boms");
  const items = useOptions("/items?active=true&limit=500", (x) => `${x.sku} · ${x.name}`);
  const itemName = useItemNames();
  const [creating, setCreating] = useState(false);
  const [rows, setRows] = useState<Component[]>([{ component_item_id: "", quantity: "1", scrap_pct: "0" }]);
  const [open, setOpen] = useState<Json | null>(null);
  const set = (i: number, patch: Partial<Component>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <Page title="Listas de materiales" subtitle="Base para calcular consumos planificados de las órdenes de producción"
          actions={can("operations.work_order.approve") && <button onClick={() => setCreating(true)}>Nueva lista</button>}>
      <DataTable rows={data} empty="Sin listas de materiales" onRowClick={setOpen} columns={[
        { key: "code", title: "Código" }, { key: "item_id", title: "Producto", render: (r) => itemName(r.item_id) },
        { key: "base_quantity", title: "Cantidad base", align: "right", render: (r) => fmtNumber(r.base_quantity) },
        { key: "lines", title: "Componentes", align: "right", render: (r) => r.lines.length }]} />
      {open && <Modal title={`Lista ${open.code}`} onClose={() => setOpen(null)}>
        <p>Producto: <strong>{itemName(open.item_id)}</strong> · por {fmtNumber(open.base_quantity)} unidades</p>
        <DataTable rows={open.lines} columns={[{ key: "component_item_id", title: "Componente", render: (r) => itemName(r.component_item_id) },
          { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
          { key: "scrap_pct", title: "Desperdicio %", align: "right", render: (r) => fmtNumber(r.scrap_pct) }]} />
      </Modal>}
      {creating && <Modal title="Nueva lista de materiales" onClose={() => setCreating(false)}>
        <h3>Componentes</h3>
        <table className="lines"><tbody>{rows.map((r, i) => <tr key={i}>
          <td><select aria-label="Componente" value={r.component_item_id} onChange={(e) => set(i, { component_item_id: e.target.value })}>
            <option value="">—</option>{items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></td>
          <td><input aria-label="Cantidad del componente" type="number" step="any" min="0" value={r.quantity}
                     onChange={(e) => set(i, { quantity: e.target.value })} /></td>
          <td><input aria-label="Desperdicio %" type="number" step="any" min="0" max="100" value={r.scrap_pct}
                     onChange={(e) => set(i, { scrap_pct: e.target.value })} /></td>
          <td><button type="button" className="secondary" aria-label="Quitar componente"
                      onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button></td>
        </tr>)}</tbody></table>
        <button type="button" className="secondary"
                onClick={() => setRows([...rows, { component_item_id: "", quantity: "1", scrap_pct: "0" }])}>+ Componente</button>
        <Form initial={{ base_quantity: "1" }} fields={[{ name: "code", label: "Código", required: true },
          { name: "item_id", label: "Producto a fabricar", type: "select", required: true, options: items },
          { name: "base_quantity", label: "Cantidad base", type: "number", required: true }]}
          onSubmit={async (d) => {
            const lines = rows.filter((r) => r.component_item_id).map((r) => ({
              component_item_id: Number(r.component_item_id), quantity: r.quantity, scrap_pct: r.scrap_pct || "0" }));
            if (!lines.length) throw new Error("Agregue al menos un componente");
            if (lines.some((l) => l.component_item_id === d.item_id)) throw new Error("Un producto no puede ser componente de sí mismo");
            await post("/operations/boms", { ...d, lines });
            setCreating(false); setRows([{ component_item_id: "", quantity: "1", scrap_pct: "0" }]); reload();
          }} />
      </Modal>}
    </Page>
  );
}

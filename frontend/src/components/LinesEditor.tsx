import { useOptions } from "../lib/hooks";

export interface Line {
  item_id: string;
  quantity: string;
  unit_price: string;
  discount_pct?: string;
}

/** Editor de líneas de documento (artículo, cantidad, precio y descuento opcional). */
export function LinesEditor({ lines, onChange, withDiscount = false, priceRequired = true }: {
  lines: Line[]; onChange: (l: Line[]) => void; withDiscount?: boolean; priceRequired?: boolean;
}) {
  const items = useOptions("/items?active=true&limit=500", (x) => `${x.sku} · ${x.name}`);
  const set = (i: number, k: keyof Line, v: string) => onChange(lines.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  return (
    <div className="lines">
      <table>
        <thead>
          <tr><th>Artículo</th><th className="num">Cantidad</th><th className="num">Precio unitario</th>
            {withDiscount && <th className="num">Desc. %</th>}<th /></tr>
        </thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i}>
              <td>
                <select aria-label="Artículo" required value={l.item_id} onChange={(e) => set(i, "item_id", e.target.value)}>
                  <option value="">—</option>
                  {items.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </td>
              <td><input aria-label="Cantidad" type="number" step="any" min="0" required value={l.quantity}
                         onChange={(e) => set(i, "quantity", e.target.value)} /></td>
              <td><input aria-label="Precio" type="number" step="any" min="0" required={priceRequired} placeholder={priceRequired ? undefined : "Automático"}
                         value={l.unit_price} onChange={(e) => set(i, "unit_price", e.target.value)} /></td>
              {withDiscount && <td><input aria-label="Descuento" type="number" step="any" min="0" max="100" placeholder="Promoción"
                                          value={l.discount_pct ?? ""} onChange={(e) => set(i, "discount_pct", e.target.value)} /></td>}
              <td><button type="button" className="secondary" onClick={() => onChange(lines.filter((_, j) => j !== i))}
                          aria-label="Quitar línea">✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button type="button" className="secondary"
              onClick={() => onChange([...lines, { item_id: "", quantity: "1", unit_price: "" }])}>+ Línea</button>
    </div>
  );
}

export function linesPayload(lines: Line[]) {
  return lines.filter((l) => l.item_id).map((l) => ({
    item_id: Number(l.item_id), quantity: l.quantity, ...(l.unit_price !== "" ? { unit_price: l.unit_price } : {}),
    ...(l.discount_pct ? { discount_pct: l.discount_pct } : {}),
  }));
}

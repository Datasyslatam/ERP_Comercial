import { useState } from "react";
import { Json } from "../lib/api";
import { Line, LinesEditor, linesPayload } from "./LinesEditor";
import { Field, Form, Modal } from "./ui";

/** Líneas del documento listas para editar. En ventas, un precio que vino de la lista o un descuento que vino de una
 * promoción se dejan vacíos para que el servidor los vuelva a calcular; lo digitado a mano se conserva, igual que el
 * precio de líneas anteriores a las listas de precios (sin origen registrado), para no alterar lo ya pactado. */
const RECALCULATED = ["price_list", "list_price"];

export function editableLines(lines: Json[], sales: boolean): Line[] {
  return lines.map((l) => ({
    item_id: String(l.item_id), quantity: String(Number(l.quantity)),
    unit_price: !sales || !RECALCULATED.includes(l.price_source) ? String(Number(l.unit_price)) : "",
    discount_pct: sales && !l.promotion_id && Number(l.discount_pct) ? String(Number(l.discount_pct)) : "",
  }));
}

/** Edición de un documento en borrador: encabezado (Form) y líneas (LinesEditor) se guardan juntos. */
export function DraftEditor({ title, fields, initial, lines: initialLines, sales, onSubmit, onClose }: {
  title: string; fields: Field[]; initial: Json; lines: Line[]; sales: boolean;
  onSubmit: (header: Json, lines: Json[]) => Promise<void>; onClose: () => void;
}) {
  const [lines, setLines] = useState<Line[]>(initialLines);
  return (
    <Modal title={title} onClose={onClose}>
      <LinesEditor lines={lines} onChange={setLines} withDiscount={sales} priceRequired={!sales} />
      {sales && <p className="muted">Precio vacío: se aplica la lista de precios del cliente. Descuento vacío: se aplica la mejor promoción vigente.</p>}
      <Form initial={initial} fields={fields} submitLabel="Guardar cambios" onCancel={onClose}
        onSubmit={async (d) => {
          const payload = linesPayload(lines);
          if (!payload.length) throw new Error("Agregue al menos una línea");
          await onSubmit(d, payload);
        }} />
    </Modal>
  );
}

export const PRICE_SOURCES: Record<string, string> = {
  manual: "Manual", price_list: "Lista de precios", list_price: "Precio base", quote: "Cotización",
};

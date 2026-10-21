import { useState } from "react";
import { TracePanel } from "../components/TracePanel";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { download, Json, post, qs } from "../lib/api";
import { fmtDate, fmtMoney, fmtNumber, label } from "../lib/format";
import { useFetch, useItemNames, useLookup } from "../lib/hooks";
import { useSession } from "../lib/session";

export const DOC_TYPES: Record<string, string> = { invoice: "Factura", credit_note: "Nota crédito", debit_note: "Nota débito" };

export function InvoicingPage() {
  const { can } = useSession();
  const [edoc, setEdoc] = useState("");
  const [docType, setDocType] = useState("");
  const { data, reload } = useFetch<Json>(`/einvoicing/invoices${qs({ edoc_status: edoc, doc_type: docType })}`);
  const focus = Number(new URLSearchParams(window.location.search).get("focus")) || null;
  const [current, setCurrent] = useState<number | null>(focus);
  const detail = useFetch<Json>(current ? `/einvoicing/invoices/${current}` : null);
  const [noting, setNoting] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [checking, setChecking] = useState(false);
  const itemName = useItemNames();
  const customerName = useLookup("/parties?limit=500", (x) => x.legal_name);
  return (
    <Page title="Facturación electrónica" actions={<>
      <select aria-label="Tipo de documento" value={docType} onChange={(e) => setDocType(e.target.value)}>
        <option value="">Todos los tipos</option>
        {Object.entries(DOC_TYPES).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      <select aria-label="Estado electrónico" value={edoc} onChange={(e) => setEdoc(e.target.value)}>
        <option value="">Todos</option>
        {["draft", "pending", "sent", "accepted", "rejected", "error"].map((s) => <option key={s} value={s}>{label(s)}</option>)}
      </select>
      <button className="secondary" onClick={() => setChecking(true)}>Conciliación fiscal</button>
    </>}>
      <Alert kind="warning">Proveedor tecnológico no definido: los documentos se procesan con el adaptador SANDBOX y NO tienen validez fiscal.</Alert>
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[
        { key: "full_number", title: "Número", render: (r) => r.full_number ?? "(borrador)" },
        { key: "doc_type", title: "Tipo", render: (r) => DOC_TYPES[r.doc_type] ?? r.doc_type }, { key: "issue_date", title: "Fecha" },
        { key: "customer_id", title: "Cliente", render: (r) => customerName(r.customer_id) },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "edoc_status", title: "Documento electrónico", render: (r) => <Badge value={r.edoc_status} /> },
        { key: "total", title: "Total", align: "right", render: (r) => fmtMoney(r.total, r.currency) },
        { key: "a", title: "", render: (r) => <span className="row" onClick={(e) => e.stopPropagation()}>
          {r.status === "draft" && can("einvoicing.invoice.post") && <ActionButton confirm="Se asignará número autorizado y se contabilizará. ¿Emitir?"
            onClick={async () => { await post(`/einvoicing/invoices/${r.id}/issue`); reload(); }}>Emitir</ActionButton>}
          {["rejected", "error"].includes(r.edoc_status) && can("einvoicing.invoice.post") &&
            <ActionButton onClick={async () => { await post(`/einvoicing/invoices/${r.id}/resend`); reload(); }}>Reenviar</ActionButton>}
        </span> }]} />
      {detail.data && current && (
        <Modal title={`${DOC_TYPES[detail.data.doc_type] ?? "Documento"} ${detail.data.full_number ?? "borrador"}`} onClose={() => setCurrent(null)}>
          {detail.data.fiscal_notice && <Alert kind="warning">{detail.data.fiscal_notice}</Alert>}
          <KeyValues data={detail.data} keys={[["edoc_status", "Estado electrónico", (v) => <Badge value={v} />], ["edoc_environment", "Ambiente"],
            ["fiscal_uid", "CUFE / identificador"], ["control_number", "Número de control"], ["edoc_message", "Mensaje"],
            ["correction_reason", "Motivo de la nota"], ["subtotal", "Subtotal", fmtMoney], ["tax_total", "Impuestos", fmtMoney],
            ["total", "Total", fmtMoney], ["journal_entry_id", "Asiento contable"]]} />
          <DataTable rows={detail.data.lines} columns={[{ key: "line_no", title: "#" },
            { key: "item_id", title: "Artículo", render: (r) => itemName(r.item_id) },
            { key: "quantity", title: "Cantidad", align: "right", render: (r) => fmtNumber(r.quantity) },
            { key: "unit_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.unit_price) },
            { key: "line_subtotal", title: "Subtotal", align: "right", render: (r) => fmtMoney(r.line_subtotal) }]} />
          <h3>Intentos de envío</h3>
          <DataTable rows={detail.data.submissions} empty="Sin envíos" columns={[{ key: "attempt_no", title: "#" },
            { key: "created_at", title: "Fecha", render: (r) => fmtDate(r.created_at) }, { key: "adapter", title: "Adaptador" },
            { key: "result_status", title: "Resultado", render: (r) => <Badge value={r.result_status} /> },
            { key: "provider_message", title: "Mensaje" }]} />
          <div className="row">
            {detail.data.submissions?.some((s: Json) => s.document_attachment_id) &&
              <button className="secondary" onClick={() => download(`/einvoicing/invoices/${current}/document`, `${detail.data.full_number}.xml`)}>
                Descargar documento</button>}
            {detail.data.doc_type === "invoice" && detail.data.status === "issued" && can("einvoicing.invoice.create") &&
              <button onClick={() => setNoting(true)}>Nota crédito / débito</button>}
            {detail.data.status === "draft" && can("einvoicing.invoice.void") && <button className="danger" onClick={() => setVoiding(true)}>Anular borrador</button>}
          </div>
          {detail.data.status === "issued" && <p className="muted">Un documento emitido no se anula: se corrige con nota crédito o débito.</p>}
          {voiding && <Form submitLabel="Anular borrador" fields={[{ name: "reason", label: "Motivo", type: "textarea", required: true }]}
            onSubmit={async (d) => { await post(`/einvoicing/invoices/${current}/cancel`, d); setVoiding(false); detail.reload(); reload(); }} />}
          <h3>Trazabilidad</h3>
          {detail.data.id && <TracePanel type="sales_invoice" id={detail.data.id} />}
        </Modal>
      )}
      {checking && <FiscalCheckModal onClose={() => setChecking(false)} />}
      {noting && detail.data && <NoteModal invoice={detail.data} itemName={itemName} onClose={() => setNoting(false)}
        onCreated={(note) => { setNoting(false); reload(); setCurrent(note.id); }} />}
    </Page>
  );
}

/** Nota crédito o débito sobre una factura emitida. Se crea en borrador y se emite desde el listado. */
export function NoteModal({ invoice, itemName, onClose, onCreated }: {
  invoice: Json; itemName: (id: unknown) => string; onClose: () => void; onCreated: (note: Json) => void;
}) {
  const codes = useFetch<Record<string, Record<string, string>>>("/einvoicing/correction-codes");
  const [docType, setDocType] = useState("credit_note");
  const options = Object.entries(codes.data?.[docType] ?? {}).map(([value, label]) => ({ value, label: `${value} · ${label}` }));
  return (
    <Modal title={`Nota sobre la factura ${invoice.full_number}`} onClose={onClose}>
      <div className="filters">
        <label>Tipo de nota
          <select aria-label="Tipo de nota" value={docType} onChange={(e) => setDocType(e.target.value)}>
            <option value="credit_note">Nota crédito (disminuye el valor)</option>
            <option value="debit_note">Nota débito (aumenta el valor)</option>
          </select>
        </label>
      </div>
      <Form key={docType} submitLabel="Crear nota en borrador"
        initial={Object.fromEntries(invoice.lines.map((l: Json) => [`p_${l.id}`, l.unit_price]))}
        fields={[
          { name: "correction_code", label: "Concepto de corrección", type: "select", required: true, options },
          { name: "reason", label: "Motivo", required: true },
          ...invoice.lines.flatMap((l: Json) => [
            { name: `q_${l.id}`, label: `${itemName(l.item_id)}: cantidad (facturado ${fmtNumber(l.quantity)})`, type: "number" as const },
            { name: `p_${l.id}`, label: `${itemName(l.item_id)}: precio unitario de la nota`, type: "number" as const }])]}
        onSubmit={async (v) => {
          const lines = invoice.lines.filter((l: Json) => Number(v[`q_${l.id}`]) > 0).map((l: Json) => ({
            invoice_line_id: l.id, quantity: v[`q_${l.id}`], unit_price: v[`p_${l.id}`] ?? l.unit_price }));
          if (!lines.length) throw new Error("Indique la cantidad de al menos una línea");
          onCreated(await post(`/einvoicing/invoices/${invoice.id}/notes`, {
            doc_type: docType, correction_code: v.correction_code, reason: v.reason, lines }));
        }} />
      <p className="muted">La nota crédito no puede superar el saldo pendiente de la factura y requiere numeración autorizada vigente para su tipo.</p>
    </Modal>
  );
}

/** Verifica que cada documento emitido tenga asiento contable, partida en cartera y aceptación electrónica. */
function FiscalCheckModal({ onClose }: { onClose: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const [start, setStart] = useState(today.slice(0, 8) + "01");
  const [end, setEnd] = useState(today);
  const { data } = useFetch<Json>(`/einvoicing/reconciliation${qs({ start, end })}`);
  return (
    <Modal title="Conciliación fiscal y contable" onClose={onClose}>
      <div className="filters">
        <label>Desde<input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>Hasta<input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
      </div>
      {data && (data.ok
        ? <Alert kind="ok">{data.documents} documento(s) revisados: todos tienen asiento contable, partida en cartera y aceptación electrónica.</Alert>
        : <>
          <Alert kind="warning">{data.issues.length} inconsistencia(s) en {data.documents} documento(s).</Alert>
          <DataTable rows={data.issues} columns={[{ key: "invoice", title: "Documento" }, { key: "problem", title: "Problema" }]} />
        </>)}
    </Modal>
  );
}

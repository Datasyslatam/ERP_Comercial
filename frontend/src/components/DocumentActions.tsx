import { FormEvent, useState } from "react";
import { download, Json, post } from "../lib/api";
import { fmtDate } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { ActionButton, Alert, Badge, DataTable, Modal } from "./ui";

const splitEmails = (s: string) => s.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);

/** PDF del documento y envío por correo (con historial de envíos). `canSend` según permiso y estado del documento. */
export function DocumentActions({ type, id, number, canSend, sendHint }: {
  type: "sales_quote" | "sales_order" | "purchase_order" | "sales_invoice"; id: number; number: string;
  canSend: boolean; sendHint?: string;
}) {
  const [sending, setSending] = useState(false);
  return (
    <>
      <ActionButton className="secondary" onClick={() => download(`/documents/${type}/${id}/pdf`, `${number}.pdf`)}>Descargar PDF</ActionButton>
      {canSend && <button className="secondary" onClick={() => setSending(true)}>Enviar por correo</button>}
      {!canSend && sendHint && <span className="muted">{sendHint}</span>}
      {sending && <EmailModal type={type} id={id} number={number} onClose={() => setSending(false)} />}
    </>
  );
}

function EmailModal({ type, id, number, onClose }: { type: string; id: number; number: string; onClose: () => void }) {
  const defaults = useFetch<Json>(`/documents/${type}/${id}/email-defaults`);
  const history = useFetch<Json[]>(`/documents/${type}/${id}/emails`);
  const [form, setForm] = useState<Json | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [queued, setQueued] = useState(false);
  const v = form ?? (defaults.data ? { to: (defaults.data.to ?? []).join(", "), cc: "", subject: defaults.data.subject, body: defaults.data.body } : null);
  const set = (k: string) => (e: { target: { value: string } }) => setForm({ ...v, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post(`/documents/${type}/${id}/email`, { to: splitEmails(v.to), cc: splitEmails(v.cc), subject: v.subject, body: v.body });
      setQueued(true);
      history.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Enviar ${number} por correo`} onClose={onClose}>
      <Alert>{defaults.error}</Alert>
      {queued && <Alert kind="ok">Envío en cola: el PDF se genera con los datos vigentes y se entrega en unos segundos. El estado se actualiza en el historial.</Alert>}
      {v && !queued && <form className="form" onSubmit={submit}>
        <div className="form-grid">
          <label className="span-2"><span>Para * (separe varios correos con coma)</span><input required value={v.to} onChange={set("to")} aria-label="Para" /></label>
          <label className="span-2"><span>Copia</span><input value={v.cc} onChange={set("cc")} aria-label="Copia" /></label>
          <label className="span-2"><span>Asunto *</span><input required value={v.subject} onChange={set("subject")} aria-label="Asunto" /></label>
          <label className="span-2"><span>Mensaje *</span><textarea required rows={7} value={v.body} onChange={set("body")} aria-label="Mensaje" /></label>
        </div>
        <p className="muted">Se adjunta el documento en PDF. Las respuestas del destinatario llegan al correo de la empresa.</p>
        <Alert>{error}</Alert>
        <div className="row"><button type="submit" disabled={busy}>{busy ? "Enviando…" : "Enviar"}</button>
          <button type="button" className="secondary" onClick={onClose}>Cancelar</button></div>
      </form>}
      <h3>Envíos anteriores</h3>
      <div className="row"><button className="secondary" onClick={history.reload}>Actualizar estado</button></div>
      <DataTable rows={history.data} empty="Sin envíos" columns={[{ key: "created_at", title: "Fecha", render: (r) => fmtDate(r.created_at) },
        { key: "to_addresses", title: "Para" }, { key: "subject", title: "Asunto" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status === "queued" ? "pending" : r.status} /> },
        { key: "error", title: "Detalle", render: (r) => r.status === "sent" ? `Entregado ${fmtDate(r.sent_at)}` : r.error ?? "En cola" }]} />
    </Modal>
  );
}

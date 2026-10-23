import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ActionButton, Alert, DataTable, Form, Modal, Page } from "../components/ui";
import { download, get, Json, post } from "../lib/api";
import { fmtDate, fmtMoney } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { useSession } from "../lib/session";
import { distribute, PaymentModal } from "./Accounting";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => today().slice(0, 8) + "01";
const BUCKETS = ["current", "1_30", "31_60", "61_90", "over_90", "advances"];

/** Cartera por cobrar y por pagar: edades por documento o por tercero, conciliación con la contabilidad, estado de
 * cuenta, anticipos y pago de varias facturas del mismo tercero. */
export function ReceivablesPage() {
  const { can } = useSession();
  // El tipo sale de la ruta (cuentas-por-cobrar / cuentas-por-pagar) o de ?kind= (enlaces de los indicadores)
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const kind = pathname.endsWith("cuentas-por-pagar") || new URLSearchParams(search).get("kind") === "payable"
    ? "payable" : "receivable";
  const [asOf, setAsOf] = useState(today());
  const [party, setParty] = useState("");
  const [view, setView] = useState<"documents" | "parties">("documents");
  const receivable = kind === "receivable";
  const qp = `kind=${kind}&as_of=${asOf}`;
  const aging = useFetch<Json>(`/accounting/aging?${qp}${party ? `&party_id=${party}` : ""}`);
  const byParty = useFetch<Json[]>(`/accounting/aging/by-party?${qp}`);
  // Terceros con saldo y, si el usuario puede consultarlos, todos los clientes o proveedores (para anticipos nuevos)
  const parties = useFetch<Json>(can("masters.parties.read") ? "/parties?limit=500&active=true" : null);
  const partyOptions: Json[] = Object.values(Object.fromEntries([
    ...(byParty.data ?? []).map((r) => [r.party_id, { id: r.party_id, legal_name: r.party }]),
    ...(parties.data?.items ?? []).filter((x: Json) => (receivable ? x.is_customer : x.is_supplier)).map((x: Json) => [x.id, x]),
  ])).sort((x: Json, y: Json) => String(x.legal_name).localeCompare(String(y.legal_name)));
  const [selected, setSelected] = useState<Record<number, Json>>({});
  const [paying, setPaying] = useState<Json[] | null>(null);
  const [advanceFor, setAdvanceFor] = useState<{ id: number; name: string } | null>(null);
  const [crossing, setCrossing] = useState<Json | null>(null);
  const [statement, setStatement] = useState<{ id: number; name: string } | null>(null);
  const [tick, setTick] = useState(0);  // vuelve a consultar la conciliación tras cada pago o cruce
  const reload = () => { setSelected({}); aging.reload(); byParty.reload(); setTick((t) => t + 1); };
  const chosen = Object.values(selected);
  const toggle = (r: Json) => {
    const next = { ...selected };
    if (next[r.open_item_id]) delete next[r.open_item_id];
    else if (chosen.length && (chosen[0].party_id !== r.party_id || chosen[0].currency !== r.currency)) return;
    else next[r.open_item_id] = r;
    setSelected(next);
  };
  const changeKind = (k: string) => {
    setParty("");
    setSelected({});
    navigate(k === "payable" ? "/contabilidad/cuentas-por-pagar" : "/contabilidad/cuentas-por-cobrar");
  };
  const labels = aging.data?.labels ?? {};
  const payable = can("accounting.payments.create");
  return (
    <Page title={receivable ? "Cuentas por cobrar" : "Cuentas por pagar"} subtitle={receivable
      ? "Cartera de clientes por edades, anticipos, estado de cuenta y conciliación con la contabilidad"
      : "Obligaciones con proveedores por edades, anticipos, estado de cuenta y conciliación con la contabilidad"} actions={<>
      <select aria-label="Tipo" value={kind} onChange={(e) => changeKind(e.target.value)}>
        <option value="receivable">Cuentas por cobrar</option><option value="payable">Cuentas por pagar</option></select>
      <select aria-label="Tercero" value={party} onChange={(e) => { setParty(e.target.value); setSelected({}); }}>
        <option value="">Todos los {receivable ? "clientes" : "proveedores"}</option>
        {partyOptions.map((x) => <option key={x.id} value={x.id}>{x.legal_name}</option>)}</select>
      <input type="date" aria-label="Fecha de corte" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
      <select aria-label="Vista" value={view} onChange={(e) => setView(e.target.value as "documents" | "parties")}>
        <option value="documents">Por documento</option><option value="parties">Por tercero</option></select>
      {can("accounting.reports.export") && <ActionButton className="secondary" onClick={() =>
        download(`/accounting/aging.xlsx?${qp}`, `cartera_${kind}_${asOf}.xlsx`)}>Excel</ActionButton>}
    </>}>
      {can("accounting.reports.read") && <Reconciliation key={`${kind}-${tick}`} kind={kind} />}
      {aging.data && <p className="summary">{BUCKETS.filter((b) => b !== "advances" || Number(aging.data.totals.advances))
        .map((b) => <span key={b}>{labels[b] ?? b}: {fmtMoney(aging.data.totals[b])}</span>)}
        <strong>Saldo neto {fmtMoney(aging.data.total)}</strong></p>}
      {payable && <p className="row">
        {party && <button className="secondary" onClick={() => setAdvanceFor({ id: Number(party),
          name: partyOptions.find((x) => String(x.id) === party)?.legal_name ?? "" })}>
          Registrar anticipo {receivable ? "del cliente" : "al proveedor"}</button>}
        {party && <button className="secondary" onClick={() => setStatement({ id: Number(party),
          name: partyOptions.find((x) => String(x.id) === party)?.legal_name ?? "" })}>Estado de cuenta</button>}
        {chosen.length > 0 && <button onClick={() => setPaying(chosen)}>
          {receivable ? "Recaudar" : "Pagar"} {chosen.length} seleccionada(s) · {fmtMoney(chosen.reduce((t, r) => t + Number(r.open_amount), 0), chosen[0].currency)}</button>}
        {!party && <span className="muted">Elija un tercero para registrar anticipos o ver su estado de cuenta. Marque varias facturas del mismo tercero para pagarlas juntas.</span>}
      </p>}
      {view === "documents" ? <DataTable rows={aging.data?.items} empty="Sin partidas abiertas" columns={[
        ...(payable ? [{ key: "sel", title: "", render: (r: Json) => !r.is_advance && <input type="checkbox" aria-label={`Seleccionar ${r.document}`}
          checked={!!selected[r.open_item_id]} onChange={() => toggle(r)} /> }] : []),
        { key: "party", title: "Tercero", render: (r) => <button className="link" onClick={() => setStatement({ id: r.party_id, name: r.party })}>{r.party}</button> },
        { key: "document", title: "Documento", render: (r) => r.is_advance ? `Anticipo ${r.document}` : r.document },
        { key: "due_date", title: "Vence", render: (r) => r.is_advance ? "—" : fmtDate(r.due_date) },
        { key: "days_overdue", title: "Días vencido", align: "right", render: (r) => r.is_advance ? "—" : r.days_overdue },
        { key: "bucket", title: "Rango", render: (r) => labels[r.bucket] ?? r.bucket },
        { key: "open_amount", title: "Saldo", align: "right", render: (r) => fmtMoney(r.open_amount, r.currency) },
        { key: "a", title: "", render: (r) => payable && (r.is_advance
          ? <button className="secondary" onClick={() => setCrossing(r)}>Cruzar con facturas</button>
          : <button onClick={() => setPaying([r])}>{receivable ? "Recaudar" : "Pagar"}</button>) }]} />
        : <DataTable rows={byParty.data} empty="Sin saldos" columns={[
          { key: "tax_id", title: "Identificación" },
          { key: "party", title: "Tercero", render: (r) => <button className="link" onClick={() => setStatement({ id: r.party_id, name: r.party })}>{r.party}</button> },
          ...BUCKETS.map((b) => ({ key: b, title: labels[b] ?? b, align: "right" as const, render: (r: Json) => fmtMoney(r[b]) })),
          { key: "total", title: "Saldo neto", align: "right", render: (r) => <strong>{fmtMoney(r.total)}</strong> },
          ...(receivable ? [{ key: "credit_limit", title: "Cupo", align: "right" as const, render: (r: Json) => Number(r.credit_limit)
            ? <span className={Number(r.total) > Number(r.credit_limit) ? "danger" : ""}>{fmtMoney(r.credit_limit)}</span> : "—" }] : [])]} />}
      {paying && <PaymentModal kind={kind} items={paying} onClose={() => setPaying(null)} onDone={() => { setPaying(null); reload(); }} />}
      {advanceFor && <PaymentModal kind={kind} party={advanceFor} onClose={() => setAdvanceFor(null)} onDone={() => { setAdvanceFor(null); reload(); }} />}
      {crossing && <ApplyAdvanceModal kind={kind} advance={crossing} onClose={() => setCrossing(null)} onDone={() => { setCrossing(null); reload(); }} />}
      {statement && <StatementModal kind={kind} party={statement} onClose={() => setStatement(null)} />}
    </Page>
  );
}

/** Auxiliar de cartera (partidas abiertas) frente a las cuentas de control del mayor. */
export function Reconciliation({ kind }: { kind: string }) {
  const { data, error } = useFetch<Json>(`/accounting/reconciliation?kind=${kind}`);
  const [open, setOpen] = useState(false);
  if (error) return <Alert>{error}</Alert>;
  if (!data) return null;
  const accounts = data.accounts.map((a: Json) => `${a.label} ${a.account_code}: mayor ${fmtMoney(a.gl)} · auxiliar ${fmtMoney(a.subledger)}`).join(" · ");
  return data.balanced
    ? <Alert kind="ok">Auxiliar y contabilidad cuadran. {accounts}</Alert>
    : <Alert kind="warning">
      Diferencia de {fmtMoney(data.difference)} {data.currency} entre el auxiliar y la contabilidad ({data.parties_with_difference} tercero(s)). {accounts}{" "}
      <button className="link" onClick={() => setOpen(!open)}>{open ? "Ocultar" : "Ver terceros"}</button>
      {open && <ul>{data.parties.filter((r: Json) => Number(r.difference) !== 0).slice(0, 20).map((r: Json) =>
        <li key={r.party_id}>{r.party}: mayor {fmtMoney(r.gl)} · auxiliar {fmtMoney(r.subledger)} · diferencia {fmtMoney(r.difference)}</li>)}</ul>}
      <br /><span className="muted">Suele deberse a comprobantes manuales en la cuenta de control o a diferencias de cambio en documentos en divisas.</span>
    </Alert>;
}

/** Cruce de un anticipo contra facturas abiertas del mismo tercero (vencimiento más antiguo primero). */
export function ApplyAdvanceModal({ kind, advance, onClose, onDone }: { kind: string; advance: Json; onClose: () => void; onDone: () => void }) {
  const { data } = useFetch<Json>(`/accounting/aging?kind=${kind}&party_id=${advance.party_id}`);
  const invoices: Json[] = (data?.items ?? []).filter((r: Json) => !r.is_advance && r.currency === advance.currency);
  const available = Math.abs(Number(advance.open_amount));
  const [amounts, setAmounts] = useState<Record<number, string> | null>(null);
  const suggested = Object.fromEntries(distribute(invoices, available).allocations.map((a) => [a.open_item_id, a.amount]));
  const values = amounts ?? suggested;
  const total = Object.values(values).reduce((t, v) => t + (Number(v) || 0), 0);
  return (
    <Modal title={`Cruce del anticipo ${advance.document}`} onClose={onClose}>
      <p>Saldo a favor disponible: <strong>{fmtMoney(available, advance.currency)}</strong> · a cruzar {fmtMoney(total)}</p>
      <DataTable rows={invoices} empty="El tercero no tiene facturas abiertas en esta moneda" columns={[
        { key: "document", title: "Documento" }, { key: "due_date", title: "Vence", render: (r) => fmtDate(r.due_date) },
        { key: "open_amount", title: "Saldo", align: "right", render: (r) => fmtMoney(r.open_amount, r.currency) },
        { key: "x", title: "Cruzar", render: (r) => <input type="number" step="any" aria-label={`Cruzar ${r.document}`} value={values[r.open_item_id] ?? ""}
          onChange={(e) => setAmounts({ ...values, [r.open_item_id]: e.target.value })} /> }]} />
      {total > available + 0.001 && <Alert>El cruce supera el saldo del anticipo.</Alert>}
      <p className="row"><ActionButton onClick={async () => {
        const allocations = Object.entries(values).filter(([, v]) => Number(v) > 0)
          .map(([id, v]) => ({ open_item_id: Number(id), amount: Number(v).toFixed(2) }));
        await post(`/accounting/advances/${advance.open_item_id}/apply`, { allocations });
        onDone();
      }}>Cruzar anticipo</ActionButton></p>
    </Modal>
  );
}

/** Estado de cuenta del tercero: movimientos con saldo corrido, documentos pendientes, PDF y envío por correo. */
export function StatementModal({ kind, party, onClose }: { kind: string; party: { id: number; name: string }; onClose: () => void }) {
  const { can } = useSession();
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(today());
  const q = `party_id=${party.id}&kind=${kind}&start=${start}&end=${end}`;
  const { data, error } = useFetch<Json>(`/accounting/party-statement?${q}`);
  const [sending, setSending] = useState<Json | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  return (
    <Modal title={`Estado de cuenta · ${party.name}`} onClose={onClose}>
      <p className="row">
        <input type="date" aria-label="Desde" value={start} onChange={(e) => setStart(e.target.value)} />
        <input type="date" aria-label="Hasta" value={end} onChange={(e) => setEnd(e.target.value)} />
        <ActionButton className="secondary" onClick={() => download(`/accounting/party-statement/pdf?${q}`, `estado_cuenta_${party.id}_${end}.pdf`)}>PDF</ActionButton>
        {can("accounting.payments.create") && <ActionButton className="secondary" onClick={async () =>
          setSending(await get(`/accounting/party-statement/email-defaults?${q}`))}>Enviar por correo</ActionButton>}
      </p>
      <Alert>{error}</Alert>
      {sent && <Alert kind="ok">{sent}</Alert>}
      {sending && <Form initial={{ to: sending.to.join(", "), subject: sending.subject, body: sending.body }} submitLabel="Enviar"
        onCancel={() => setSending(null)} fields={[{ name: "to", label: "Para", required: true }, { name: "subject", label: "Asunto" },
          { name: "body", label: "Mensaje", type: "textarea" }]}
        onSubmit={async (d) => {
          await post("/accounting/party-statement/email", { party_id: party.id, kind, start, end, subject: d.subject, body: d.body,
            to: String(d.to).split(/[,;]/).map((x) => x.trim()).filter(Boolean) });
          setSending(null);
          setSent("Estado de cuenta en cola de envío.");
        }} />}
      {data && <>
        <p className="totals">Saldo inicial {fmtMoney(data.opening)} · cargos {fmtMoney(data.charges)} · abonos {fmtMoney(data.credits)} ·
          saldo final <strong>{fmtMoney(data.closing)}</strong> {data.currency}</p>
        <DataTable rows={data.rows} empty="Sin movimientos en el periodo" columns={[
          { key: "date", title: "Fecha", render: (r) => fmtDate(r.date) }, { key: "entry", title: "Comprobante" },
          { key: "source", title: "Tipo" }, { key: "description", title: "Concepto" },
          { key: "charge", title: "Cargos", align: "right", render: (r) => Number(r.charge) ? fmtMoney(r.charge) : "" },
          { key: "credit", title: "Abonos", align: "right", render: (r) => Number(r.credit) ? fmtMoney(r.credit) : "" },
          { key: "balance", title: "Saldo", align: "right", render: (r) => fmtMoney(r.balance) }]} />
        <h3>Documentos pendientes</h3>
        <DataTable rows={data.pending} empty="Sin documentos pendientes" columns={[
          { key: "document", title: "Documento", render: (r) => r.is_advance ? `Anticipo ${r.document}` : r.document },
          { key: "due_date", title: "Vence", render: (r) => r.is_advance ? "—" : fmtDate(r.due_date) },
          { key: "days_overdue", title: "Días vencido", align: "right" },
          { key: "functional", title: "Saldo", align: "right", render: (r) => fmtMoney(r.functional) }]} />
      </>}
    </Modal>
  );
}

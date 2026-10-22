import { useState } from "react";
import { useLocation } from "react-router-dom";
import { DocumentActions } from "../components/DocumentActions";
import { TracePanel } from "../components/TracePanel";
import { ActionButton, Alert, Badge, DataTable, Form, KeyValues, Modal, Page } from "../components/ui";
import { download, get, Json, patch, post, put, qs } from "../lib/api";
import { fmtDate, fmtMoney } from "../lib/format";
import { useFetch, useLookup, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => today().slice(0, 8) + "01";

export function ReportsPage() {
  const { can } = useSession();
  const { pathname } = useLocation();
  const [report, setReport] = useState(pathname.endsWith("estado-resultados") ? "income-statement"
    : pathname.endsWith("flujo-efectivo") ? "cash-flow" : "trial-balance");
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(today());
  const [account, setAccount] = useState("");
  const accounts = useOptions("/accounts?limit=500", (x) => `${x.code} ${x.name}`);
  const path = report === "balance-sheet" ? `/accounting/reports/balance-sheet?as_of=${end}`
    : report === "general-ledger" ? (account ? `/accounting/reports/general-ledger/${account}?start=${start}&end=${end}` : null)
    : `/accounting/reports/${report}?start=${start}&end=${end}`;
  const { data, error } = useFetch<Json>(path);
  return (
    <Page title="Estados financieros" actions={<>
      <select aria-label="Reporte" value={report} onChange={(e) => setReport(e.target.value)}>
        <option value="trial-balance">Balance de prueba</option><option value="income-statement">Estado de resultados</option>
        <option value="balance-sheet">Balance general</option><option value="cash-flow">Flujo de efectivo</option>
        <option value="general-ledger">Libro mayor</option><option value="journal">Libro diario</option>
      </select>
      {report === "general-ledger" && <select aria-label="Cuenta" value={account} onChange={(e) => setAccount(e.target.value)}>
        <option value="">Seleccione la cuenta…</option>{accounts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>}
      {report !== "balance-sheet" && <input type="date" aria-label="Desde" value={start} onChange={(e) => setStart(e.target.value)} />}
      <input type="date" aria-label="Hasta" value={end} onChange={(e) => setEnd(e.target.value)} />
      {report === "trial-balance" && can("accounting.reports.export") &&
        <button className="secondary" onClick={() => download(`/accounting/reports/trial-balance.csv?start=${start}&end=${end}`, "balance_prueba.csv")}>CSV</button>}
    </>}>
      <Alert>{error}</Alert>
      {data && report === "trial-balance" && <>
        <p><Badge value={data.balanced ? "ok" : "critical"} /> Débitos {fmtMoney(data.total_debit)} · Créditos {fmtMoney(data.total_credit)}</p>
        <DataTable rows={data.rows} columns={[{ key: "code", title: "Cuenta", render: (r) => r.is_postable ? r.code : <strong>{r.code}</strong> },
          { key: "name", title: "Nombre" }, ...["opening", "debit", "credit", "closing"].map((k) => ({ key: k,
            title: { opening: "Saldo inicial", debit: "Débitos", credit: "Créditos", closing: "Saldo final" }[k] as string,
            align: "right" as const, render: (r: Json) => fmtMoney(r[k]) }))]} />
      </>}
      {data && report === "income-statement" && <>
        {(["revenue", "cost", "expense"] as const).map((s) => <div key={s}>
          <h3>{{ revenue: "Ingresos", cost: "Costos", expense: "Gastos" }[s]}</h3>
          <DataTable rows={data.sections[s]} empty="Sin movimiento" columns={[{ key: "code", title: "Cuenta" }, { key: "name", title: "Nombre" },
            { key: "amount", title: "Valor", align: "right", render: (r) => fmtMoney(r.amount) }]} />
        </div>)}
        <p className="totals">Utilidad bruta {fmtMoney(data.gross_profit)} · Utilidad neta <strong>{fmtMoney(data.net_income)}</strong></p>
      </>}
      {data && report === "balance-sheet" && <>
        <p><Badge value={data.balanced ? "ok" : "critical"} /> Activo {fmtMoney(data.total_assets)} = Pasivo {fmtMoney(data.total_liabilities)} + Patrimonio {fmtMoney(data.total_equity)}</p>
        {(["assets", "liabilities", "equity"] as const).map((s) => <div key={s}>
          <h3>{{ assets: "Activo", liabilities: "Pasivo", equity: "Patrimonio" }[s]}</h3>
          <DataTable rows={data[s]} empty="Sin saldo" columns={[{ key: "code", title: "Cuenta" }, { key: "name", title: "Nombre" },
            { key: "balance", title: "Saldo", align: "right", render: (r) => fmtMoney(r.balance) }]} />
        </div>)}
        <p>Resultado del ejercicio no cerrado: {fmtMoney(data.current_result)}</p>
      </>}
      {data && report === "general-ledger" && data.account && <>
        <p>{data.account.code} {data.account.name} · Saldo inicial {fmtMoney(data.opening)} · Saldo final <strong>{fmtMoney(data.closing)}</strong></p>
        <DataTable rows={data.lines} empty="Sin movimientos en el periodo" columns={[{ key: "entry_date", title: "Fecha" }, { key: "number", title: "Comprobante" },
          { key: "description", title: "Detalle", render: (r) => r.description ?? (r.source_type ? `${r.source_type} #${r.source_id}` : "—") },
          { key: "debit", title: "Débito", align: "right", render: (r) => fmtMoney(r.debit) }, { key: "credit", title: "Crédito", align: "right", render: (r) => fmtMoney(r.credit) },
          { key: "balance", title: "Saldo", align: "right", render: (r) => fmtMoney(r.balance) }]} />
      </>}
      {report === "general-ledger" && !account && <p className="muted">Seleccione una cuenta para ver su libro mayor.</p>}
      {data && report === "journal" && Array.isArray(data) && (data.length ? data.map((e: Json) => <div key={e.id}>
        <h3>{e.number} · {e.date} · {e.description}</h3>
        <DataTable rows={e.lines} columns={[{ key: "account", title: "Cuenta" }, { key: "account_name", title: "Nombre" },
          { key: "debit", title: "Débito", align: "right", render: (r) => fmtMoney(r.debit) }, { key: "credit", title: "Crédito", align: "right", render: (r) => fmtMoney(r.credit) }]} />
      </div>) : <p className="muted">Sin comprobantes en el periodo.</p>)}
      {data && report === "cash-flow" && (data.status ? <Alert kind="warning">{data.message}</Alert> : <>
        <p>Efectivo inicial {fmtMoney(data.opening_cash)} · final <strong>{fmtMoney(data.closing_cash)}</strong></p>
        <DataTable rows={data.operating} columns={[{ key: "concept", title: "Concepto" }, { key: "amount", title: "Valor", align: "right", render: (r) => fmtMoney(r.amount) }]} />
        <p className="muted">{data.note}</p>
      </>)}
    </Page>
  );
}

export function EntriesPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/accounting/entries?limit=100");
  const accounts = useOptions("/accounts?limit=500", (x) => `${x.code} ${x.name}`);
  const [creating, setCreating] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const [rows, setRows] = useState([{ account_id: "", debit: "", credit: "" }, { account_id: "", debit: "", credit: "" }]);
  const sum = (k: "debit" | "credit") => rows.reduce((s, r) => s + Number(r[k] || 0), 0);
  return (
    <Page title="Comprobantes contables" actions={can("accounting.journal.create") && <button onClick={() => setCreating(true)}>Comprobante manual</button>}>
      <DataTable rows={data?.items} onRowClick={(r) => setCurrent(r.id)} columns={[{ key: "number", title: "Número" }, { key: "entry_date", title: "Fecha" },
        { key: "journal_type", title: "Diario" }, { key: "description", title: "Descripción" },
        { key: "source", title: "Origen", render: (r) => r.source_type ? `${r.source_type} #${r.source_id ?? ""}` : "manual" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status} /> },
        { key: "total_debit", title: "Valor", align: "right", render: (r) => fmtMoney(r.total_debit) },
        { key: "a", title: "", render: (r) => <span className="row">
          {r.status === "draft" && can("accounting.journal.post") && <ActionButton onClick={async () => { await post(`/accounting/entries/${r.id}/post`); reload(); }}>Contabilizar</ActionButton>}
          {r.status === "posted" && (!r.source_type || r.source_type === "manual") && can("accounting.journal.void") &&
            <ActionButton className="danger" onClick={async () => { const reason = window.prompt("Motivo del reverso");
              if (reason) { await post(`/accounting/entries/${r.id}/reverse`, { reversal_date: today(), reason }); reload(); } }}>Reversar</ActionButton>}
        </span> }]} />
      {current && <EntryModal id={current} accounts={accounts} onClose={() => setCurrent(null)} />}
      {creating && <Modal title="Comprobante manual (borrador)" onClose={() => setCreating(false)}>
        <table className="lines"><tbody>{rows.map((r, i) => <tr key={i}>
          <td><select aria-label="Cuenta" value={r.account_id} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, account_id: e.target.value } : x))}>
            <option value="">—</option>{accounts.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}</select></td>
          <td><input aria-label="Débito" type="number" step="any" placeholder="Débito" value={r.debit} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, debit: e.target.value } : x))} /></td>
          <td><input aria-label="Crédito" type="number" step="any" placeholder="Crédito" value={r.credit} onChange={(e) => setRows(rows.map((x, j) => j === i ? { ...x, credit: e.target.value } : x))} /></td>
        </tr>)}</tbody></table>
        <button className="secondary" onClick={() => setRows([...rows, { account_id: "", debit: "", credit: "" }])}>+ Línea</button>
        <p>Débitos {fmtMoney(sum("debit"))} · Créditos {fmtMoney(sum("credit"))} {sum("debit") !== sum("credit") && <Badge value="critical" />}</p>
        <Form initial={{ entry_date: today() }} fields={[{ name: "entry_date", label: "Fecha", type: "date", required: true },
          { name: "description", label: "Descripción", required: true }]}
          onSubmit={async (d) => { await post("/accounting/entries", { ...d, lines: rows.filter((r) => r.account_id).map((r) => ({
            account_id: Number(r.account_id), debit: r.debit || "0", credit: r.credit || "0" })) }); setCreating(false); reload(); }} />
      </Modal>}
    </Page>
  );
}

export function ReceivablesPage() {
  const { can } = useSession();
  const [kind, setKind] = useState("receivable");
  const aging = useFetch<Json>(`/accounting/aging?kind=${kind}`);
  const [paying, setPaying] = useState<Json | null>(null);
  return (
    <Page title="Cartera y pagos" actions={<select aria-label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}>
      <option value="receivable">Cuentas por cobrar</option><option value="payable">Cuentas por pagar</option></select>}>
      {aging.data && <p className="summary">{Object.entries(aging.data.totals).map(([k, v]) => <span key={k}>{k.replace("_", "-")}: {fmtMoney(v)}</span>)}
        <strong>Total {fmtMoney(aging.data.total)}</strong></p>}
      <DataTable rows={aging.data?.items} columns={[{ key: "party", title: "Tercero" }, { key: "document", title: "Documento" },
        { key: "due_date", title: "Vence" }, { key: "days_overdue", title: "Días vencido", align: "right" },
        { key: "open_amount", title: "Saldo", align: "right", render: (r) => fmtMoney(r.open_amount, r.currency) },
        { key: "a", title: "", render: (r) => can("accounting.payments.create") && <button onClick={() => setPaying(r)}>{kind === "receivable" ? "Recaudar" : "Pagar"}</button> }]} />
      {paying && <PaymentModal kind={kind} item={paying} onClose={() => setPaying(null)} onDone={() => { setPaying(null); aging.reload(); }} />}
    </Page>
  );
}

export function PeriodsPage() {
  const { can } = useSession();
  const year = new Date().getFullYear();
  const { data, reload } = useFetch<Json[]>(`/accounting/periods?year=${year}`);
  return (
    <Page title={`Periodos contables ${year}`} actions={can("accounting.period.admin") &&
      <ActionButton className="secondary" confirm={`Se generará el asiento de cierre de ${year - 1}: traslada ingresos, costos y gastos a resultados acumulados. ¿Continuar?`}
        onClick={async () => { await post("/accounting/year-close", { year: year - 1, month: 12 }); reload(); }}>Cierre del ejercicio {year - 1}</ActionButton>}>
      <DataTable rows={data} columns={[{ key: "month", title: "Mes" }, { key: "start_date", title: "Desde" }, { key: "end_date", title: "Hasta" },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status === "open" ? "open" : "closed"} /> },
        { key: "reopen_reason", title: "Motivo reapertura" },
        { key: "a", title: "", render: (r) => can("accounting.period.admin") && (r.status === "open"
          ? <ActionButton confirm="Cerrar el periodo bloquea nuevas contabilizaciones. ¿Continuar?" onClick={async () => { await post("/accounting/periods/close", { year: r.year, month: r.month }); reload(); }}>Cerrar</ActionButton>
          : <ActionButton onClick={async () => { const reason = window.prompt("Justificación de la reapertura (mín. 10 caracteres)");
              if (reason) { await post("/accounting/periods/reopen", { year: r.year, month: r.month, reason }); reload(); } }}>Reabrir</ActionButton>) }]} />
    </Page>
  );
}

export function GoalsBudgetsPage() {
  const { can } = useSession();
  const goals = useFetch<Json>("/accounting/goals");
  const budgets = useFetch<Json>("/accounting/budgets?limit=200");
  const defs = useFetch<Json[]>("/kpi/definitions");
  const ccs = useOptions("/cost-centers", (x) => `${x.code} ${x.name}`);
  const [target, setTarget] = useState(false);
  return (
    <Page title="Metas y presupuestos">
      <h3>Presupuesto</h3>
      {can("accounting.budget.create") && <Form fields={[{ name: "year", label: "Año", type: "number", required: true }, { name: "month", label: "Mes", type: "number", required: true },
        { name: "category", label: "Categoría", type: "select", required: true, options: [["purchases", "Compras"], ["expenses", "Gastos"], ["revenue", "Ingresos"]].map(([v, l]) => ({ value: v, label: l })) },
        { name: "cost_center_id", label: "Centro de costo", type: "select", options: ccs }, { name: "amount", label: "Valor", type: "number", required: true }]}
        initial={{ year: new Date().getFullYear(), month: new Date().getMonth() + 1 }} submitLabel="Agregar presupuesto"
        onSubmit={async (d) => { await post("/accounting/budgets", { ...d, year: Number(d.year), month: Number(d.month) }); budgets.reload(); }} />}
      <DataTable rows={budgets.data?.items} columns={[{ key: "year", title: "Año" }, { key: "month", title: "Mes" }, { key: "category", title: "Categoría" },
        { key: "cost_center_id", title: "Centro de costo" }, { key: "amount", title: "Valor", align: "right", render: (r) => fmtMoney(r.amount) }]} />
      <h3>Metas estratégicas</h3>
      {can("kpi.config.admin") && <Form fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Meta", required: true },
        { name: "kpi_code", label: "Indicador asociado", type: "select", required: true, options: (defs.data ?? []).map((d) => ({ value: d.code, label: d.name })) },
        { name: "target_value", label: "Valor meta", type: "number", required: true }, { name: "period_start", label: "Inicio", type: "date", required: true },
        { name: "period_end", label: "Fin", type: "date", required: true }, { name: "weight", label: "Peso", type: "number" }]} submitLabel="Agregar meta"
        onSubmit={async (d) => { await post("/accounting/goals", d); goals.reload(); }} />}
      <DataTable rows={goals.data?.items} columns={[{ key: "code", title: "Código" }, { key: "name", title: "Meta" }, { key: "kpi_code", title: "KPI" },
        { key: "target_value", title: "Meta", align: "right" }, { key: "period_end", title: "Hasta" }]} />
      {can("kpi.config.admin") && <button className="secondary" onClick={() => setTarget(true)}>Configurar meta y umbral de un KPI</button>}
      {target && <Modal title="Meta y umbrales de indicador" onClose={() => setTarget(false)}>
        <Form fields={[{ name: "kpi_code", label: "Indicador", type: "select", required: true, options: (defs.data ?? []).map((d) => ({ value: d.code, label: d.name })) },
          { name: "target", label: "Meta", type: "number", required: true }, { name: "critical_threshold", label: "Umbral crítico", type: "number" },
          { name: "owner_id", label: "Responsable (id usuario)", type: "number" }, { name: "alerts_enabled", label: "Generar alertas", type: "checkbox" }]}
          initial={{ alerts_enabled: true }} onSubmit={async (d) => { await put("/kpi/targets", d); setTarget(false); }} />
      </Modal>}
    </Page>
  );
}

export function AlertsPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json>("/kpi/alerts");
  return (
    <Page title="Alertas" actions={can("kpi.config.admin") && <ActionButton onClick={async () => { await post("/kpi/alerts/evaluate"); reload(); }}>Evaluar ahora</ActionButton>}>
      <DataTable rows={data?.items} empty="Sin alertas abiertas" columns={[{ key: "severity", title: "Severidad", render: (r) => <Badge value={r.severity} /> },
        { key: "message", title: "Mensaje" }, { key: "source", title: "Origen" },
        { key: "a", title: "", render: (r) => can("kpi.alerts.approve") && <ActionButton onClick={async () => { await post(`/kpi/alerts/${r.id}/ack`, { close: true }); reload(); }}>Cerrar</ActionButton> }]} />
    </Page>
  );
}


interface WithholdingRow { tax_id: string; base: string; amount: string; certificate_number?: string }

/** Recaudo o pago de una partida abierta. En recaudos admite las retenciones que practica el cliente:
 *  el valor aplicado a la partida = valor recibido en banco + retenciones. */
export function PaymentModal({ kind, item, onClose, onDone }: {
  kind: string; item: Json; onClose: () => void; onDone: () => void;
}) {
  const receipt = kind === "receivable";
  const banks = useOptions("/bank-accounts", (x) => `${x.name} (${x.currency})`);
  const taxes = useFetch<Json>("/taxes?active=true&limit=200");
  const withholdingTaxes: Json[] = (taxes.data?.items ?? []).filter((t: Json) => String(t.kind).startsWith("withholding")
    && [receipt ? "sales" : "purchases", "both"].includes(t.applies_to));
  const [rows, setRows] = useState<WithholdingRow[]>([]);
  const [hint, setHint] = useState<string | null>(null);
  // Al aplicar las sugerencias se rehace el formulario para proponer el valor neto de retenciones.
  const [formKey, setFormKey] = useState(0);
  /** Retenciones del proveedor sobre lo que se paga (bases mínimas y retenciones ya hechas en la factura). */
  const suggest = async () => {
    const r = await get(`/accounting/payments/withholding-suggestions?open_item_id=${item.open_item_id}&applied=${item.open_amount}`);
    setRows(r.suggestions.map((s: Json) => ({ tax_id: String(s.tax_id), base: String(s.base), amount: String(s.amount) })));
    setHint(!r.agent ? "La empresa no está marcada como agente de retención."
      : r.suggestions.length ? null : r.already_withheld.length ? "La factura ya liquidó sus retenciones al causarse."
      : "El proveedor no tiene retenciones configuradas o la base no alcanza el mínimo.");
    setFormKey((k) => k + 1);
  };
  // Clave fija mientras el formulario esté abierto: un doble envío no duplica el pago.
  const [idempotencyKey] = useState(() => `ui-${item.open_item_id}-${crypto.randomUUID?.() ?? Date.now()}`);
  const whTotal = rows.reduce((s, r) => s + (Number(r.amount) || 0), 0);
  const setRow = (i: number, patch: Partial<WithholdingRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const calc = (i: number) => {
    const r = rows[i];
    const tax = withholdingTaxes.find((t) => String(t.id) === r.tax_id);
    if (tax && r.base) setRow(i, { amount: (Math.round(Number(r.base) * Number(tax.rate)) / 100).toFixed(2) });
  };
  const cashDefault = (Number(item.open_amount) - whTotal).toFixed(2);
  return (
    <Modal title={`${receipt ? "Recaudo" : "Pago"} de ${item.document}`} onClose={onClose}>
      <p>Saldo de la partida: <strong>{fmtMoney(item.open_amount, item.currency)}</strong></p>
      <>
        <h3>{receipt ? "Retenciones practicadas por el cliente" : "Retenciones que practica la empresa"}</h3>
        {!receipt && <p className="row"><ActionButton className="secondary" onClick={suggest}>Sugerir según el proveedor</ActionButton>
          {hint && <span className="muted">{hint}</span>}</p>}
        <table className="lines"><tbody>{rows.map((r, i) => <tr key={i}>
          <td><select aria-label="Retención" value={r.tax_id} onChange={(e) => setRow(i, { tax_id: e.target.value })}>
            <option value="">—</option>{withholdingTaxes.map((t) => <option key={t.id} value={t.id}>{t.code} · {t.name}</option>)}</select></td>
          <td><input aria-label="Base" type="number" step="any" placeholder="Base" value={r.base} onChange={(e) => setRow(i, { base: e.target.value })} /></td>
          <td><input aria-label="Valor retenido" type="number" step="any" placeholder="Valor" value={r.amount} onChange={(e) => setRow(i, { amount: e.target.value })} /></td>
          {receipt && <td><input aria-label="Comprobante del cliente" placeholder="N.º comprobante" maxLength={30}
            value={r.certificate_number ?? ""} onChange={(e) => setRow(i, { certificate_number: e.target.value })} /></td>}
          <td className="row"><button type="button" className="secondary" onClick={() => calc(i)}>Calcular</button>
            <button type="button" className="secondary" aria-label="Quitar retención" onClick={() => setRows(rows.filter((_, j) => j !== i))}>✕</button></td>
        </tr>)}</tbody></table>
        <button type="button" className="secondary" onClick={() => setRows([...rows, { tax_id: "", base: "", amount: "" }])}>+ Retención</button>
        <p className="muted">Total retenido {fmtMoney(whTotal)}. {receipt
          ? "El valor recibido en banco más las retenciones se aplica a la partida. Registre el número del comprobante que entrega el cliente: va al libro de ventas."
          : "Se paga el saldo menos las retenciones; cada retención genera su comprobante para el proveedor."}</p>
      </>
      <Form key={formKey} initial={{ payment_date: today(), amount: cashDefault, method: "transfer" }} fields={[
        { name: "bank_account_id", label: "Cuenta bancaria", type: "select", required: true, options: banks },
        { name: "payment_date", label: "Fecha", type: "date", required: true },
        { name: "amount", label: `${receipt ? "Valor recibido en banco" : "Valor pagado"} (sugerido: saldo − retenciones = ${cashDefault})`,
          type: "number", required: true },
        { name: "method", label: "Medio", type: "select", options: ["transfer", "cash", "check", "card", "mobile_payment"].map((v) => ({ value: v, label: v })) },
        { name: "reference", label: "Referencia" }]}
        onSubmit={async (d) => {
          const withholdings = rows.filter((r) => r.tax_id && Number(r.amount) > 0)
            .map((r) => ({ tax_id: Number(r.tax_id), base: r.base || "0", amount: r.amount,
              ...(receipt && r.certificate_number?.trim() ? { certificate_number: r.certificate_number.trim() } : {}) }));
          const applied = (Number(d.amount) + withholdings.reduce((s, w) => s + Number(w.amount), 0)).toFixed(2);
          await post("/accounting/payments", { ...d, kind: receipt ? "receipt" : "disbursement", party_id: item.party_id,
            currency: item.currency, idempotency_key: idempotencyKey, withholdings,
            allocations: [{ open_item_id: item.open_item_id, amount: applied }] });
          onDone();
        }} />
    </Modal>
  );
}

// ------------------------------------------------------------------ pagos y recaudos
export function PaymentsPage() {
  const { can } = useSession();
  const [kind, setKind] = useState("");
  const { data, reload } = useFetch<Json>(`/accounting/payments${qs({ kind, limit: 200 })}`);
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const [current, setCurrent] = useState<Json | null>(null);
  const [voiding, setVoiding] = useState(false);
  return (
    <Page title="Pagos y recaudos" subtitle="Movimientos de tesorería aplicados a facturas, con retenciones e IGTF" actions={<>
      {can("admin.company.admin") && <WithholdingPolicy />}
      <select aria-label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">Todos</option>
        <option value="receipt">Recaudos de clientes</option><option value="disbursement">Pagos a proveedores</option></select></>}>
      <DataTable rows={data?.items} onRowClick={setCurrent} columns={[{ key: "number", title: "Número" }, { key: "payment_date", title: "Fecha" },
        { key: "kind", title: "Tipo", render: (r) => r.kind === "receipt" ? "Recaudo" : "Pago" },
        { key: "party_id", title: "Tercero", render: (r) => partyName(r.party_id) }, { key: "method", title: "Medio" },
        { key: "reference", title: "Referencia", render: (r) => r.reference ?? "—" },
        { key: "withholding_amount", title: "Retenciones", align: "right", render: (r) => fmtMoney(r.withholding_amount) },
        { key: "amount", title: "Valor", align: "right", render: (r) => fmtMoney(r.amount, r.currency) },
        { key: "status", title: "Estado", render: (r) => <Badge value={r.status === "voided" ? "cancelled" : "posted"} /> }]} />
      {current && <Modal title={`${current.kind === "receipt" ? "Recaudo" : "Pago"} ${current.number}`} onClose={() => { setCurrent(null); setVoiding(false); }}>
        <KeyValues data={current} keys={[["payment_date", "Fecha"], ["party_id", "Tercero", (v) => partyName(v)], ["method", "Medio"],
          ["reference", "Referencia"], ["amount", "Valor", fmtMoney], ["withholding_amount", "Retenciones", fmtMoney], ["igtf_amount", "IGTF", fmtMoney]]} />
        {current.status === "posted" && can("accounting.payments.void") && (voiding
          ? <Form submitLabel="Anular pago" fields={[{ name: "reason", label: "Motivo de la anulación", type: "textarea", required: true }]}
              onSubmit={async (d) => { await post(`/accounting/payments/${current.id}/void`, d); setCurrent(null); setVoiding(false); reload(); }} />
          : <p><button className="danger" onClick={() => setVoiding(true)}>Anular</button> <span className="muted">Reabre las partidas aplicadas y reversa el comprobante.</span></p>)}
        <p className="row"><DocumentActions type="payment" id={current.id} number={current.number}
          canSend={current.status === "posted" && can("accounting.payments.create")} /></p>
        <h3>Trazabilidad</h3>
        <TracePanel type="payment" id={current.id} />
      </Modal>}
    </Page>
  );
}

// ------------------------------------------------------------------ conciliación bancaria
/** Interpreta líneas pegadas desde el extracto: fecha;descripción;referencia;valor (separador ; o tabulador). */
export function parseStatementLines(text: string): Json[] {
  return text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean).map((l) => {
    const [txn_date, description, reference, amount] = l.split(/[;\t]/).map((x) => x.trim());
    const raw = amount ?? "";
    // 1.500.000,50 (formato local) o 1500000.50
    return { txn_date, description, reference: reference || null, amount: raw.includes(",") ? raw.replace(/\./g, "").replace(",", ".") : raw };
  }).filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x.txn_date) && x.amount !== "" && !Number.isNaN(Number(x.amount)));
}

export function BankReconciliationPage() {
  const { can } = useSession();
  const banks = useOptions("/bank-accounts", (x) => `${x.name} (${x.currency})`);
  const [bank, setBank] = useState("");
  const statements = useFetch<Json[]>(`/accounting/bank-statements${qs({ bank_account_id: bank })}`);
  const [current, setCurrent] = useState<number | null>(null);
  const [importing, setImporting] = useState(false);
  return (
    <Page title="Conciliación bancaria" subtitle="Extractos del banco frente a los movimientos contables de la cuenta"
          actions={can("accounting.bank.create") && <button onClick={() => setImporting(true)}>Cargar extracto</button>}>
      <div className="filters"><label>Cuenta bancaria<select value={bank} onChange={(e) => setBank(e.target.value)}><option value="">Todas</option>
        {banks.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label></div>
      <DataTable rows={statements.data} onRowClick={(r) => setCurrent(r.id)} empty="Sin extractos cargados" columns={[
        { key: "statement_date", title: "Fecha de corte" }, { key: "source_filename", title: "Archivo", render: (r) => r.source_filename ?? "—" },
        { key: "opening_balance", title: "Saldo inicial", align: "right", render: (r) => fmtMoney(r.opening_balance) },
        { key: "closing_balance", title: "Saldo final", align: "right", render: (r) => fmtMoney(r.closing_balance) }]} />
      {importing && <StatementImport banks={banks} onClose={() => setImporting(false)} onDone={(id) => { setImporting(false); statements.reload(); setCurrent(id); }} />}
      {current && <ReconciliationModal statementId={current} onClose={() => setCurrent(null)} />}
    </Page>
  );
}

export function StatementImport({ banks, onClose, onDone }: { banks: { value: number; label: string }[]; onClose: () => void; onDone: (id: number) => void }) {
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<Json | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const lines = parseStatementLines(text);
  const total = lines.reduce((s, l) => s + Number(l.amount), 0);
  const readFile = async (file: File | undefined) => {
    if (!file) return;
    setFileError(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const r = await post("/accounting/bank-statements/parse", body);
      setText(r.lines.map((l: Json) => [l.txn_date, String(l.description).replace(/[;\t]/g, ","), String(l.reference ?? "").replace(/[;\t]/g, ","), l.amount].join(";")).join("\n"));
      setParsed({ ...r, source_filename: file.name });
    } catch (e) {
      setFileError((e as Error).message);
    }
  };
  return (
    <Modal title="Cargar extracto bancario" onClose={onClose}>
      <label className="span-2"><span>Archivo del banco (CSV, Excel .xlsx u OFX)</span>
        <input aria-label="Archivo del extracto" type="file" accept=".csv,.txt,.xlsx,.ofx,.qfx" onChange={(e) => readFile(e.target.files?.[0])} /></label>
      <Alert>{fileError}</Alert>
      {parsed && <Alert kind={parsed.warnings.length ? "warning" : "ok"}>
        {parsed.lines.length} movimiento(s) leídos del archivo ({String(parsed.format).toUpperCase()}). Revíselos abajo antes de cargar.
        {parsed.warnings.length > 0 && <ul>{parsed.warnings.slice(0, 6).map((w: string) => <li key={w}>{w}</li>)}</ul>}</Alert>}
      <label className="span-2"><span>Movimientos (una línea por movimiento: AAAA-MM-DD;descripción;referencia;valor — débitos con signo negativo)</span>
        <textarea aria-label="Movimientos del extracto" rows={8} value={text} onChange={(e) => setText(e.target.value)}
          placeholder={"2026-10-01;Consignación cliente;RC-000001;1500000\n2026-10-02;Pago proveedor;CE-000004;-850000"} /></label>
      <p className="muted">{lines.length} movimiento(s) reconocidos · neto {fmtMoney(total)}</p>
      <Form key={parsed?.source_filename ?? "manual"} initial={parsed ? { statement_date: parsed.statement_date ?? "",
          opening_balance: parsed.opening_balance ?? "", closing_balance: parsed.closing_balance ?? "", source_filename: parsed.source_filename } : {}}
        fields={[{ name: "bank_account_id", label: "Cuenta bancaria", type: "select", required: true, options: banks },
        { name: "statement_date", label: "Fecha de corte", type: "date", required: true },
        { name: "opening_balance", label: "Saldo inicial según banco", type: "number", required: true },
        { name: "closing_balance", label: "Saldo final según banco", type: "number", required: true },
        { name: "source_filename", label: "Archivo o referencia del extracto" }]}
        submitLabel="Cargar extracto"
        onSubmit={async (d) => {
          if (!lines.length) throw new Error("Pegue al menos un movimiento con el formato indicado");
          if (Math.abs(Number(d.opening_balance) + total - Number(d.closing_balance)) > 0.005)
            throw new Error(`Saldo inicial + movimientos (${fmtMoney(Number(d.opening_balance) + total)}) no coincide con el saldo final`);
          const st = await post("/accounting/bank-statements", { ...d, lines });
          onDone(st.id);
        }} />
    </Modal>
  );
}

function ReconciliationModal({ statementId, onClose }: { statementId: number; onClose: () => void }) {
  const { can } = useSession();
  const { data: r, reload } = useFetch<Json>(`/accounting/bank-statements/${statementId}/reconciliation`);
  const [matching, setMatching] = useState<Json | null>(null);
  const approve = can("accounting.bank.approve");
  if (!r) return <Modal title="Conciliación" onClose={onClose}><p className="muted">Cargando…</p></Modal>;
  const diff = Number(r.difference);
  return (
    <Modal title="Conciliación del extracto" onClose={onClose}>
      <div className="summary">
        <span>Saldo banco <strong>{fmtMoney(r.statement_balance)}</strong></span><span>Saldo libros <strong>{fmtMoney(r.book_balance)}</strong></span>
        <span>Diferencia <strong className={Math.abs(diff) > 0.005 ? "warn-text" : ""}>{fmtMoney(r.difference)}</strong></span>
        <span>Conciliados {r.matched_in_statement}</span>
        {approve && <ActionButton onClick={async () => { await post(`/accounting/bank-statements/${statementId}/auto-match`); reload(); }}>Conciliar automáticamente</ActionButton>}
      </div>
      <h3>Movimientos del banco sin conciliar</h3>
      <DataTable rows={r.unmatched_statement_lines} empty="Todos los movimientos del extracto están conciliados" columns={[
        { key: "date", title: "Fecha" }, { key: "description", title: "Descripción" },
        { key: "amount", title: "Valor", align: "right", render: (x) => fmtMoney(x.amount) },
        { key: "a", title: "", render: (x) => approve && <span className="row">
          <button className="secondary" onClick={() => setMatching(x)}>Conciliar con…</button>
          <ActionButton className="secondary" confirm="¿Marcar como partida que no requiere registro contable (p. ej. ajuste del banco ya registrado)?"
            onClick={async () => { await post(`/accounting/bank-statement-lines/${x.id}/match`, { ignore: true }); reload(); }}>Ignorar</ActionButton></span> }]} />
      <h3>Partidas en libros no reflejadas en el banco</h3>
      <DataTable rows={r.outstanding_book_items} empty="Sin partidas pendientes" columns={[{ key: "entry_date", title: "Fecha" }, { key: "number", title: "Comprobante" },
        { key: "amount", title: "Valor", align: "right", render: (x) => fmtMoney(x.amount) }]} />
      <p className="muted">Las partidas en libros pendientes (cheques no cobrados, consignaciones en tránsito) explican la diferencia hasta que aparezcan en un extracto posterior.</p>
      {matching && <Modal title={`Conciliar ${matching.description} (${fmtMoney(matching.amount)})`} onClose={() => setMatching(null)}>
        <DataTable rows={r.outstanding_book_items.filter((b: Json) => Number(b.amount) === Number(matching.amount))}
          empty="No hay partidas en libros por el mismo valor; registre primero el comprobante que falta." columns={[
            { key: "entry_date", title: "Fecha" }, { key: "number", title: "Comprobante" }, { key: "amount", title: "Valor", align: "right", render: (x) => fmtMoney(x.amount) },
            { key: "a", title: "", render: (b) => <ActionButton onClick={async () => {
              await post(`/accounting/bank-statement-lines/${matching.id}/match`, { journal_line_id: b.id }); setMatching(null); reload(); }}>Conciliar</ActionButton> }]} />
      </Modal>}
    </Modal>
  );
}

function EntryModal({ id, accounts, onClose }: { id: number; accounts: { value: number; label: string }[]; onClose: () => void }) {
  const { data: e } = useFetch<Json>(`/accounting/entries/${id}`);
  const partyName = useLookup("/parties?limit=500", (x) => x.legal_name);
  const accountName = (aid: unknown) => accounts.find((a) => a.value === Number(aid))?.label ?? `#${aid}`;
  if (!e) return <Modal title="Comprobante" onClose={onClose}><p className="muted">Cargando…</p></Modal>;
  return (
    <Modal title={`Comprobante ${e.number}`} onClose={onClose}>
      <KeyValues data={e} keys={[["entry_date", "Fecha"], ["journal_type", "Diario"], ["description", "Descripción"],
        ["status", "Estado", (v) => <Badge value={v} />], ["source_type", "Origen", (v) => v ?? "manual"], ["created_at", "Registrado", fmtDate]]} />
      <DataTable rows={e.lines} columns={[{ key: "account_id", title: "Cuenta", render: (r) => accountName(r.account_id) },
        { key: "party_id", title: "Tercero", render: (r) => r.party_id ? partyName(r.party_id) : "—" }, { key: "description", title: "Detalle", render: (r) => r.description ?? "" },
        { key: "debit", title: "Débito", align: "right", render: (r) => fmtMoney(r.debit) }, { key: "credit", title: "Crédito", align: "right", render: (r) => fmtMoney(r.credit) }]} />
      <h3>Trazabilidad</h3>
      <TracePanel type="journal_entry" id={id} />
    </Modal>
  );
}

/** Política de la empresa: practicar las retenciones a proveedores al causar la factura o al pagar. */
function WithholdingPolicy() {
  const { data, reload } = useFetch<Json>("/company");
  if (!data) return null;
  const onPayment = !!data.settings?.withholding_on_payment;
  return (
    <label className="row muted" title="Aplica a las facturas de proveedor que se registren desde ahora">Retenciones a proveedores:
      <select aria-label="Momento de la retención" value={onPayment ? "payment" : "invoice"}
        onChange={async (e) => { await patch("/company/settings", { settings: { withholding_on_payment: e.target.value === "payment" } }); reload(); }}>
        <option value="invoice">al causar la factura</option><option value="payment">al pagar</option></select></label>
  );
}

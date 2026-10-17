import { useState } from "react";
import { ActionButton, Alert, Badge, DataTable, Form, Modal, Page } from "../components/ui";
import { download, Json, post, put } from "../lib/api";
import { fmtMoney } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => today().slice(0, 8) + "01";

export function ReportsPage() {
  const { can } = useSession();
  const [report, setReport] = useState("trial-balance");
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(today());
  const path = report === "balance-sheet" ? `/accounting/reports/balance-sheet?as_of=${end}` : `/accounting/reports/${report}?start=${start}&end=${end}`;
  const { data, error } = useFetch<Json>(path);
  return (
    <Page title="Estados financieros" actions={<>
      <select aria-label="Reporte" value={report} onChange={(e) => setReport(e.target.value)}>
        <option value="trial-balance">Balance de prueba</option><option value="income-statement">Estado de resultados</option>
        <option value="balance-sheet">Balance general</option><option value="cash-flow">Flujo de efectivo</option>
      </select>
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
  const [rows, setRows] = useState([{ account_id: "", debit: "", credit: "" }, { account_id: "", debit: "", credit: "" }]);
  const sum = (k: "debit" | "credit") => rows.reduce((s, r) => s + Number(r[k] || 0), 0);
  return (
    <Page title="Comprobantes contables" actions={can("accounting.journal.create") && <button onClick={() => setCreating(true)}>Comprobante manual</button>}>
      <DataTable rows={data?.items} columns={[{ key: "number", title: "Número" }, { key: "entry_date", title: "Fecha" },
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
  const banks = useOptions("/bank-accounts", (x) => `${x.name} (${x.currency})`);
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
      {paying && <Modal title={`${kind === "receivable" ? "Recaudo" : "Pago"} de ${paying.document}`} onClose={() => setPaying(null)}>
        <Form initial={{ payment_date: today(), amount: paying.open_amount, method: "transfer" }} fields={[
          { name: "bank_account_id", label: "Cuenta bancaria", type: "select", required: true, options: banks },
          { name: "payment_date", label: "Fecha", type: "date", required: true }, { name: "amount", label: "Valor recibido/pagado", type: "number", required: true },
          { name: "method", label: "Medio", type: "select", options: ["transfer", "cash", "check", "card", "mobile_payment"].map((v) => ({ value: v, label: v })) },
          { name: "reference", label: "Referencia" }]}
          onSubmit={async (d) => { await post("/accounting/payments", { ...d, kind: kind === "receivable" ? "receipt" : "disbursement", party_id: paying.party_id,
            currency: paying.currency, idempotency_key: `ui-${paying.open_item_id}-${Date.now()}`,
            allocations: [{ open_item_id: paying.open_item_id, amount: d.amount }] }); setPaying(null); aging.reload(); }} />
        <p className="muted">Para registrar retenciones practicadas por el cliente use la API de pagos (campo withholdings).</p>
      </Modal>}
    </Page>
  );
}

export function PeriodsPage() {
  const { can } = useSession();
  const year = new Date().getFullYear();
  const { data, reload } = useFetch<Json[]>(`/accounting/periods?year=${year}`);
  return (
    <Page title={`Periodos contables ${year}`}>
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


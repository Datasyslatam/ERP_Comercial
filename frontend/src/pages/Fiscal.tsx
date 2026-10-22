import { useState } from "react";
import { ActionButton, Alert, DataTable, Page } from "../components/ui";
import { download, Json } from "../lib/api";
import { fmtDate, fmtMoney } from "../lib/format";
import { useFetch } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => today().slice(0, 8) + "01";

function Tabs({ tabs, current, onChange }: { tabs: [string, string][]; current: string; onChange: (k: string) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={current === k} className={current === k ? "tab active" : "tab"}
                onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  );
}

const money = (k: string, title: string) => ({ key: k, title, align: "right" as const, render: (r: Json) => fmtMoney(r[k]) });

/** Libros y reportes fiscales: Venezuela (libros de IVA, retenciones y TXT SENIAT) y Colombia (auxiliar de IVA y
 * certificados de retención). */
export function FiscalPage() {
  const { company, can } = useSession();
  const ve = company?.country === "VE";
  const [tab, setTab] = useState(ve ? "sales" : "vat");
  const [start, setStart] = useState(monthStart());
  const [end, setEnd] = useState(today());
  const exporter = can("accounting.tax_reports.export");
  const period = `start=${start}&end=${end}`;
  const tabs: [string, string][] = ve
    ? [["sales", "Libro de ventas"], ["purchases", "Libro de compras"], ["withholdings", "Retenciones de IVA"]]
    : [["vat", "Auxiliar de IVA"], ["certificates", "Certificados de retención"]];
  // Al cambiar de empresa (otro país) la pestaña elegida puede no existir: se vuelve a la primera.
  const current = tabs.some(([k]) => k === tab) ? tab : tabs[0][0];
  return (
    <Page title="Libros y reportes fiscales" subtitle={ve
      ? "Libros de compras y ventas, comprobantes de retención de IVA y archivo TXT para el SENIAT"
      : "Auxiliar de IVA y certificados de retención por tercero"} actions={<>
      <input type="date" aria-label="Desde" value={start} onChange={(e) => setStart(e.target.value)} />
      <input type="date" aria-label="Hasta" value={end} onChange={(e) => setEnd(e.target.value)} />
    </>}>
      <Tabs tabs={tabs} current={current} onChange={setTab} />
      <div key={company?.id}>
        {current === "sales" && <VatBook kind="sales" period={period} exporter={exporter} />}
        {current === "purchases" && <VatBook kind="purchases" period={period} exporter={exporter} />}
        {current === "withholdings" && <VatWithholdings period={period} start={start} exporter={exporter} />}
        {current === "vat" && <VatAuxiliary period={period} exporter={exporter} />}
        {current === "certificates" && <Certificates period={period} />}
      </div>
      <p className="muted">Los reportes se generan con la información registrada en el ERP y en la moneda funcional.
        Valídelos con el contador antes de presentarlos ante la autoridad tributaria.</p>
    </Page>
  );
}

function VatBook({ kind, period, exporter }: { kind: "sales" | "purchases"; period: string; exporter: boolean }) {
  const path = kind === "sales" ? "/fiscal/ve/sales-book" : "/fiscal/ve/purchase-book";
  const { data, error } = useFetch<Json>(`${path}?${period}`);
  const docNumber = (r: Json) => r.invoice_number ?? r.debit_note ?? r.credit_note ?? "—";
  return (
    <>
      <Alert>{error}</Alert>
      {data?.warnings?.length > 0 && <Alert kind="warning">
        {data.warnings.length} observación(es) antes de presentar el libro:
        <ul>{data.warnings.slice(0, 8).map((w: string) => <li key={w}>{w}</li>)}</ul></Alert>}
      {exporter && <p className="row"><ActionButton className="secondary" onClick={() => download(`${path}.xlsx?${period}`,
        kind === "sales" ? "libro_ventas.xlsx" : "libro_compras.xlsx")}>Exportar a Excel</ActionButton></p>}
      <DataTable rows={data?.rows} empty="Sin operaciones en el periodo" columns={[
        { key: "n", title: "N.º" }, { key: "date", title: "Fecha", render: (r) => fmtDate(r.date) },
        { key: "rif", title: "RIF" }, { key: "name", title: kind === "sales" ? "Cliente" : "Proveedor" },
        { key: "doc", title: "Documento", render: (r) => r.kind === "withholding" ? `Retención · ${r.affected ?? ""}`
          : `${{ invoice: "Factura", credit_note: "NC", debit_note: "ND" }[r.kind as string] ?? ""} ${docNumber(r)}` },
        { key: "control_number", title: "N.º control", render: (r) => r.control_number ?? "—" },
        money("total", "Total con IVA"), money("exempt", "Exento"), money("general_base", "Base 16 %"),
        money("general_tax", "IVA 16 %"), money("reduced_base", "Base 8 %"), money("reduced_tax", "IVA 8 %"),
        money("withheld", "IVA retenido"), { key: "certificate", title: "Comprobante", render: (r) => r.certificate ?? "—" }]} />
      {data && <p className="totals">Débito/crédito fiscal: alícuota general {fmtMoney(data.totals.general_tax)} · reducida{" "}
        {fmtMoney(data.totals.reduced_tax)} · adicional {fmtMoney(data.totals.additional_tax)} · IVA retenido{" "}
        <strong>{fmtMoney(data.totals.withheld)}</strong> {data.currency}</p>}
    </>
  );
}

function VatWithholdings({ period, start, exporter }: { period: string; start: string; exporter: boolean }) {
  const { data, error } = useFetch<Json[]>(`/fiscal/ve/vat-withholdings?${period}`);
  const [year, month] = start.split("-").map(Number);
  const [half, setHalf] = useState(new Date().getDate() <= 15 ? "1" : "2");
  return (
    <>
      <Alert>{error}</Alert>
      {exporter && <p className="row">Archivo TXT para el portal del SENIAT de {String(month).padStart(2, "0")}/{year}:
        <select aria-label="Quincena" value={half} onChange={(e) => setHalf(e.target.value)}>
          <option value="1">Primera quincena (1 al 15)</option><option value="2">Segunda quincena (16 al fin de mes)</option>
          <option value="0">Mes completo</option></select>
        <ActionButton className="secondary" onClick={() => download(`/fiscal/ve/vat-withholdings.txt?year=${year}&month=${month}&half=${half}`,
          `retenciones_iva_${year}${String(month).padStart(2, "0")}_q${half}.txt`)}>Descargar TXT</ActionButton></p>}
      <DataTable rows={data} empty="Sin retenciones de IVA en el periodo" columns={[
        { key: "certificate", title: "Comprobante" }, { key: "date", title: "Fecha", render: (r) => fmtDate(r.date) },
        { key: "supplier", title: "Proveedor" }, { key: "rif", title: "RIF" },
        { key: "invoice_number", title: "Factura" }, { key: "control_number", title: "N.º control", render: (r) => r.control_number ?? "—" },
        money("vat", "IVA"), { key: "rate", title: "% retención", align: "right", render: (r) => `${Number(r.rate)} %` },
        money("withheld", "Retenido"),
        { key: "status", title: "Estado", render: (r) => r.status === "voided" ? "Anulado" : "Vigente" },
        { key: "pdf", title: "", render: (r) => r.certificate && <ActionButton className="secondary" onClick={() =>
          download(`/fiscal/ve/vat-withholdings/${r.certificate}/pdf`, `comprobante_retencion_iva_${r.certificate}.pdf`)}>PDF</ActionButton> }]} />
    </>
  );
}

function VatAuxiliary({ period, exporter }: { period: string; exporter: boolean }) {
  const { data, error } = useFetch<Json>(`/fiscal/co/vat-auxiliary?${period}`);
  const cols = [{ key: "date", title: "Fecha", render: (r: Json) => fmtDate(r.date) }, { key: "document", title: "Documento" },
    { key: "number", title: "Número" }, { key: "nit", title: "NIT" }, { key: "name", title: "Tercero" },
    { key: "rate", title: "Tarifa", align: "right" as const, render: (r: Json) => `${Number(r.rate)} %` },
    money("base", "Base"), money("tax", "IVA")];
  const s = data?.summary;
  return (
    <>
      <Alert>{error}</Alert>
      {exporter && <p className="row"><ActionButton className="secondary" onClick={() => download(`/fiscal/co/vat-auxiliary.xlsx?${period}`,
        "auxiliar_iva.xlsx")}>Exportar a Excel</ActionButton></p>}
      {s && <p className="totals">IVA generado {fmtMoney(s.generated)} − descontable {fmtMoney(s.deductible)} = saldo{" "}
        {fmtMoney(s.balance)} · retenciones de IVA que nos practicaron {fmtMoney(s.withheld_from_us)} · saldo a pagar estimado{" "}
        <strong>{fmtMoney(s.payable)}</strong> {data.currency}</p>}
      <h3>IVA generado</h3>
      <DataTable rows={data?.generated.rows} empty="Sin ventas gravadas" columns={cols} />
      <h3>IVA descontable</h3>
      <DataTable rows={data?.deductible.rows} empty="Sin compras con IVA" columns={cols} />
      <h3>Retenciones de IVA que nos practicaron</h3>
      <DataTable rows={data?.withheld_from_us.rows} empty="Sin retenciones" columns={[
        { key: "date", title: "Fecha", render: (r) => fmtDate(r.date) }, { key: "number", title: "Recaudo" },
        { key: "name", title: "Cliente" }, { key: "certificate", title: "Certificado", render: (r) => r.certificate ?? "—" },
        money("tax", "IVA retenido")]} />
    </>
  );
}

const KINDS: [string, string][] = [["income", "Retención en la fuente"], ["vat", "Retención de IVA"], ["ica", "Retención de ICA"]];

function Certificates({ period }: { period: string }) {
  const [kind, setKind] = useState("income");
  const { data, error } = useFetch<Json[]>(`/fiscal/co/withholding-certificates?${period}&kind=${kind}`);
  return (
    <>
      <p className="row">
        <select aria-label="Tipo de certificado" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <span className="muted">Un certificado por tercero con las retenciones practicadas en el periodo elegido.</span>
      </p>
      <Alert>{error}</Alert>
      <DataTable rows={data} empty="Sin retenciones practicadas en el periodo" columns={[
        { key: "nit", title: "NIT", render: (r) => r.check_digit ? `${r.nit}-${r.check_digit}` : r.nit },
        { key: "name", title: "Tercero" },
        { key: "lines", title: "Conceptos", render: (r) => r.lines.map((l: Json) => l.code).join(", ") },
        money("base", "Base"), money("amount", "Retenido"),
        { key: "pdf", title: "", render: (r) => <ActionButton className="secondary" onClick={() =>
          download(`/fiscal/co/withholding-certificates/${r.party_id}/pdf?${period}&kind=${kind}`,
            `certificado_${kind}_${r.nit}.pdf`)}>Certificado PDF</ActionButton> }]} />
    </>
  );
}

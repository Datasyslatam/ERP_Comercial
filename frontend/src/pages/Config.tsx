import { useState } from "react";
import { ResourcePage } from "../components/ResourcePage";
import { ActionButton, Alert, Badge, DataTable, Form, Page } from "../components/ui";
import { Json, patch, post, put } from "../lib/api";
import { fmtNumber } from "../lib/format";
import { useFetch, useOptions } from "../lib/hooks";
import { useSession } from "../lib/session";

const today = () => new Date().toISOString().slice(0, 10);
const active = { key: "is_active", title: "Estado", render: (r: Json) => <Badge value={r.is_active ? "active" : "inactive"} /> };
const code = { key: "code", title: "Código" };
const name = { key: "name", title: "Nombre" };
const codeField = { name: "code", label: "Código", required: true };
const nameField = { name: "name", label: "Nombre", required: true };
const activeField = { name: "is_active", label: "Activo", type: "checkbox" as const };

const MODULES: [string, string][] = [["purchasing", "Compras"], ["inventory", "Almacén"], ["quality", "Calidad"], ["sales", "Ventas"],
  ["logistics", "Logística"], ["operations", "Operaciones"], ["einvoicing", "Facturación electrónica"]];

const SOD: [string, string][] = [["sod_requisition_self_approval", "Solicitudes de compra"], ["sod_po_self_approval", "Órdenes de compra"],
  ["sod_adjustment_self_approval", "Ajustes y bajas"], ["sod_journal_self_post", "Comprobantes manuales"], ["sod_opening_balance_self_approval", "Saldos iniciales"]];

/** Datos de la empresa activa: condición fiscal, módulos y políticas operativas. Crear empresas sigue siendo una tarea técnica. */
export function CompanyPage() {
  const { can } = useSession();
  const admin = can("admin.company.admin");
  const { data: c, reload } = useFetch<Json>("/company");
  const [saved, setSaved] = useState<string | null>(null);
  if (!c) return <Page title="Empresa"><p className="muted">Cargando…</p></Page>;
  const settings = c.settings ?? {};
  return (
    <Page title="Empresa" subtitle={`${c.code} · ${c.legal_name} · ${c.tax_id} · moneda ${c.functional_currency}`}>
      {saved && <Alert kind="ok">{saved}</Alert>}
      <h3>Condición fiscal</h3>
      {admin && <Form key={`f${c.is_withholding_agent}${c.is_special_taxpayer}`} initial={c} fields={[
        { name: "is_withholding_agent", label: "Agente de retención", type: "checkbox" },
        { name: "is_special_taxpayer", label: "Gran contribuyente / contribuyente especial", type: "checkbox" }]}
        onSubmit={async (d) => { await patch("/company/fiscal", d); setSaved("Condición fiscal actualizada."); reload(); }} />}
      <p className="muted">Confírmela con el contador: determina qué retenciones puede practicar la empresa.</p>
      <h3>Módulos</h3>
      <DataTable rows={MODULES.map(([k, l]) => ({ id: k, label: l, enabled: c.modules?.[k] ?? true }))} columns={[{ key: "label", title: "Módulo" },
        { key: "enabled", title: "Estado", render: (r) => <Badge value={r.enabled ? "active" : "inactive"} /> },
        { key: "a", title: "", render: (r) => admin && <ActionButton className="secondary"
          confirm={`¿${r.enabled ? "Desactivar" : "Activar"} ${r.label}? Cambia el menú de todos los usuarios de la empresa.`}
          onClick={async () => { await put(`/company/modules/${r.id}`, { enabled: !r.enabled }); setSaved("Módulo actualizado. Recargue la página para ver el menú."); reload(); }}>
          {r.enabled ? "Desactivar" : "Activar"}</ActionButton> }]} />
      <h3>Políticas</h3>
      {admin && <Form key={JSON.stringify(settings)} initial={settings} fields={[
        { name: "receipt_over_tolerance_pct", label: "Tolerancia al recibir de más (%)", type: "number" },
        { name: "invoice_price_tolerance_pct", label: "Tolerancia de precio en factura (%)", type: "number" },
        { name: "invoice_qty_tolerance_pct", label: "Tolerancia de cantidad en factura (%)", type: "number" },
        { name: "purchase_budget_control", label: "Si la orden supera el presupuesto", type: "select", options: [{ value: "warn", label: "Advertir" }, { value: "block", label: "Impedir aprobar" }] }]}
        onSubmit={async (d) => { await patch("/company/settings", { settings: Object.fromEntries(Object.entries(d).map(([k, v]) => [k, String(v)])) }); setSaved("Políticas actualizadas."); reload(); }} />}
      <h3>Segregación de funciones</h3>
      <p className="muted">Quien crea el documento no puede aprobarlo. Este control no se cambia desde la pantalla.</p>
      <DataTable rows={SOD.map(([k, l]) => ({ id: k, label: l, on: !settings[k] }))} columns={[{ key: "label", title: "Documento" },
        { key: "on", title: "Control", render: (r) => <Badge value={r.on ? "active" : "inactive"} /> }]} />
    </Page>
  );
}

export function SitesPage() {
  return <ResourcePage title="Sedes" path="/sites" writePerm="admin.company.admin" columns={[code, name, { key: "city", title: "Ciudad" }, active]}
    fields={[codeField, nameField, { name: "address", label: "Dirección" }, { name: "city", label: "Ciudad" }, activeField]} />;
}

export function BusinessUnitsPage() {
  return <ResourcePage title="Unidades de negocio" path="/business-units" writePerm="admin.company.admin" columns={[code, name, active]}
    fields={[codeField, nameField, activeField]} />;
}

export function CostCentersPage() {
  const units = useOptions("/business-units", (x) => `${x.code} ${x.name}`);
  const sites = useOptions("/sites", (x) => x.name);
  return <ResourcePage title="Centros de costo" path="/cost-centers" writePerm="masters.config.admin" columns={[code, name, active]}
    subtitle="Se usan en consumos internos, presupuestos y cuentas que exigen centro de costo"
    fields={[codeField, nameField, { name: "business_unit_id", label: "Unidad de negocio", type: "select", options: units },
      { name: "site_id", label: "Sede", type: "select", options: sites }, activeField]} />;
}

export function PaymentTermsPage() {
  return <ResourcePage title="Condiciones de pago" path="/payment-terms" writePerm="masters.config.admin"
    columns={[code, name, { key: "days", title: "Días", align: "right" }]}
    fields={[codeField, nameField, { name: "days", label: "Días", type: "number", required: true }]} />;
}

export function CategoriesPage() {
  const accounts = useOptions("/accounts?limit=500", (x) => `${x.code} ${x.name}`);
  const account = (field: string, label: string) => ({ name: field, label, type: "select" as const, options: accounts });
  return <ResourcePage title="Categorías de artículos" path="/item-categories" writePerm="masters.items.create" columns={[code, name]}
    fields={[codeField, nameField, account("inventory_account_id", "Cuenta de inventario"), account("revenue_account_id", "Cuenta de ingresos"),
      account("cogs_account_id", "Cuenta de costo de ventas"), account("expense_account_id", "Cuenta de gasto")]} />;
}

export function BankAccountsPage() {
  const accounts = useOptions("/accounts?limit=500", (x) => `${x.code} ${x.name}`);
  return <ResourcePage title="Cuentas bancarias" path="/bank-accounts" writePerm="accounting.accounts.admin"
    subtitle="Compruebe que cada banco quede asociado a su cuenta contable correcta"
    columns={[name, { key: "bank_name", title: "Banco" }, { key: "account_number_masked", title: "Número" }, { key: "currency", title: "Moneda" }, active]}
    fields={[nameField, { name: "bank_name", label: "Banco", required: true },
      { name: "account_number_masked", label: "Número (solo los últimos dígitos)", required: true, placeholder: "****1234" },
      { name: "currency", label: "Moneda", required: true, placeholder: "COP" },
      { name: "gl_account_id", label: "Cuenta contable", type: "select", required: true, options: accounts }, activeField]} />;
}

export function SequencesPage() {
  return <ResourcePage title="Secuencias de documentos" path="/document-sequences" writePerm="masters.config.admin"
    subtitle="El consecutivo lo administra el sistema y no se edita aquí"
    columns={[{ key: "doc_type", title: "Documento" }, { key: "prefix", title: "Prefijo" }, { key: "next_number", title: "Siguiente", align: "right" }, { key: "padding", title: "Dígitos", align: "right" }]}
    fields={[{ name: "doc_type", label: "Documento", required: true }, { name: "prefix", label: "Prefijo", required: true }, { name: "padding", label: "Dígitos", type: "number" }]} />;
}

export function UomsPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json[]>("/uoms");
  const options = (data ?? []).map((u) => ({ value: u.id as number, label: `${u.code} ${u.name}` }));
  const items = useOptions("/items?limit=500", (x) => `${x.sku} · ${x.name}`);
  const write = can("masters.config.admin");
  const [saved, setSaved] = useState(false);
  return (
    <Page title="Unidades de medida" subtitle="Son comunes a todas las empresas">
      {write && <Form key={data?.length} fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
        { name: "category", label: "Categoría", type: "select", required: true, options: [["unit", "Unidad"], ["weight", "Peso"], ["volume", "Volumen"], ["length", "Longitud"], ["time", "Tiempo"], ["area", "Área"]].map(([v, l]) => ({ value: v, label: l })) }]}
        submitLabel="Agregar unidad" onSubmit={async (d) => { await post("/uoms", d); reload(); }} />}
      <DataTable rows={data} columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" }, { key: "category", title: "Categoría" }]} />
      <h3>Conversiones</h3>
      {saved && <Alert kind="ok">Conversión registrada.</Alert>}
      {write && <Form fields={[{ name: "from_uom_id", label: "De", type: "select", required: true, options }, { name: "to_uom_id", label: "A", type: "select", required: true, options },
        { name: "factor", label: "Factor", type: "number", required: true }, { name: "item_id", label: "Solo para el artículo", type: "select", options: items }]}
        submitLabel="Agregar conversión" onSubmit={async (d) => { await post("/uom-conversions", d); setSaved(true); }} />}
    </Page>
  );
}

export function ExchangeRatesPage() {
  const { can, company } = useSession();
  const { data, reload } = useFetch<Json[]>("/exchange-rates");
  return (
    <Page title="Tasas de cambio" subtitle="Base de los documentos en moneda extranjera. Registre la tasa de cada día con su fuente">
      {can("masters.config.admin") && <Form key={data?.length} initial={{ rate_date: today(), to_currency: company?.currency ?? "" }} fields={[
        { name: "from_currency", label: "De (moneda)", required: true, placeholder: "USD" }, { name: "to_currency", label: "A (moneda)", required: true },
        { name: "rate_date", label: "Fecha", type: "date", required: true }, { name: "rate", label: "Tasa", type: "number", required: true },
        { name: "source", label: "Fuente", required: true, placeholder: "TRM, BCV…" }]}
        submitLabel="Agregar tasa" onSubmit={async (d) => { await post("/exchange-rates", d); reload(); }} />}
      <DataTable rows={data} empty="Sin tasas registradas" columns={[{ key: "date", title: "Fecha" }, { key: "from", title: "De" }, { key: "to", title: "A" },
        { key: "rate", title: "Tasa", align: "right", render: (r) => fmtNumber(r.rate) }, { key: "source", title: "Fuente" }]} />
    </Page>
  );
}

export function PostingAccountsPage() {
  const { can } = useSession();
  const { data, reload } = useFetch<Json[]>("/posting-accounts");
  const accounts = useOptions("/accounts?limit=500", (x) => `${x.code} ${x.name}`);
  const [error, setError] = useState<string | null>(null);
  return (
    <Page title="Cuentas de contabilización" subtitle="Cuentas que usan los comprobantes automáticos. Cambiarlas afecta los registros siguientes: valídelo con el contador">
      <Alert>{error}</Alert>
      <DataTable rows={data} columns={[{ key: "key", title: "Concepto" }, { key: "account_id", title: "Cuenta", render: (r) => (
        <select aria-label={`Cuenta de ${r.key}`} disabled={!can("accounting.accounts.admin")} value={r.account_id ?? ""}
          onChange={async (e) => { setError(null); try { await put("/posting-accounts", { key: r.key, account_id: Number(e.target.value) }); reload(); } catch (err) { setError((err as Error).message); } }}>
          <option value="">—</option>{accounts.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}</select>) }]} />
    </Page>
  );
}

export function PartyWithholdingsPage() {
  const parties = useOptions("/parties?limit=500", (x) => x.legal_name);
  const taxes = useFetch<{ items: Json[] }>("/taxes?active=true&limit=200");
  const [party, setParty] = useState("");
  const current = useFetch<Json>(party ? `/parties/${party}/withholdings` : null);
  const rows = (taxes.data?.items ?? []).filter((t) => String(t.kind).startsWith("withholding"));
  const [saved, setSaved] = useState(false);
  return (
    <Page title="Retenciones por tercero" subtitle="El sistema las sugiere al causar y al pagar. Valídelas con el contador">
      <label>Tercero <select aria-label="Tercero" value={party} onChange={(e) => { setParty(e.target.value); setSaved(false); }}>
        <option value="">—</option>{parties.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
      {saved && <Alert kind="ok">Retenciones guardadas.</Alert>}
      {party && current.data && <Form key={`${party}-${current.data.tax_ids.join()}`}
        initial={Object.fromEntries((current.data.tax_ids as number[]).map((id) => [`t${id}`, true]))}
        fields={rows.map((t) => ({ name: `t${t.id}`, label: `${t.code} · ${t.name}`, type: "checkbox" as const }))}
        onSubmit={async (d) => {
          await put(`/parties/${party}/withholdings`, { tax_ids: rows.filter((t) => d[`t${t.id}`]).map((t) => t.id) });
          setSaved(true); current.reload();
        }} />}
    </Page>
  );
}

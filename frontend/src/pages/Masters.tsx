import { ResourcePage } from "../components/ResourcePage";
import { Badge, Field } from "../components/ui";
import { Json } from "../lib/api";
import { fmtMoney, fmtNumber } from "../lib/format";
import { useOptions } from "../lib/hooks";

const active = { key: "is_active", title: "Estado", render: (r: Json) => <Badge value={r.is_active ? "active" : "inactive"} /> };
const yes = (v: boolean) => (v ? "Sí" : "No");

export function PartiesPage() {
  const terms = useOptions("/payment-terms", (x) => x.name);
  const fields: Field[] = [
    { name: "code", label: "Código", required: true }, { name: "legal_name", label: "Razón social", required: true },
    { name: "trade_name", label: "Nombre comercial" },
    { name: "id_type", label: "Tipo de identificación", type: "select", required: true,
      options: ["NIT", "CC", "CE", "PAS", "RIF", "CI", "EXT"].map((v) => ({ value: v, label: v })) },
    { name: "tax_id", label: "Número (sin dígito verificador)", required: true },
    { name: "check_digit", label: "Dígito verificador" },
    { name: "person_type", label: "Tipo de persona", type: "select",
      options: [{ value: "organization", label: "Jurídica" }, { value: "person", label: "Natural" }] },
    { name: "is_customer", label: "Cliente", type: "checkbox" }, { name: "is_supplier", label: "Proveedor", type: "checkbox" },
    { name: "is_carrier", label: "Transportista", type: "checkbox" },
    { name: "is_withholding_agent", label: "Agente de retención", type: "checkbox" },
    { name: "is_special_taxpayer", label: "Gran contribuyente / contribuyente especial", type: "checkbox" },
    { name: "fiscal_regime", label: "Régimen fiscal" }, { name: "email", label: "Correo de facturación", type: "email" },
    { name: "phone", label: "Teléfono" }, { name: "address", label: "Dirección" }, { name: "city", label: "Ciudad" },
    { name: "city_code", label: "Código municipio (DANE)" },
    { name: "country_code", label: "País", type: "select", options: [{ value: "CO", label: "Colombia" }, { value: "VE", label: "Venezuela" }] },
    { name: "payment_term_id", label: "Condición de pago", type: "select", options: terms },
    { name: "credit_limit", label: "Cupo de crédito", type: "number" }, { name: "is_active", label: "Activo", type: "checkbox" },
  ];
  return <ResourcePage title="Terceros" path="/parties" writePerm="masters.parties.create" exportPerm="masters.parties.export"
    subtitle="Maestro único de clientes, proveedores y transportistas" fields={fields} columns={[
      { key: "code", title: "Código" }, { key: "legal_name", title: "Razón social" },
      { key: "tax_id", title: "Identificación", render: (r) => `${r.id_type} ${r.tax_id}${r.check_digit ? "-" + r.check_digit : ""}` },
      { key: "roles", title: "Roles", render: (r) => [r.is_customer && "Cliente", r.is_supplier && "Proveedor", r.is_carrier && "Transportista"].filter(Boolean).join(", ") },
      { key: "credit_limit", title: "Cupo", align: "right", render: (r) => fmtMoney(r.credit_limit) }, active]} />;
}

export function ItemsPage() {
  const uoms = useOptions("/uoms", (x) => x.code);
  const cats = useOptions("/item-categories", (x) => x.name);
  const taxes = useOptions("/taxes", (x) => x.code);
  const fields: Field[] = [
    { name: "sku", label: "SKU", required: true }, { name: "name", label: "Descripción", required: true },
    { name: "item_type", label: "Tipo", type: "select", required: true, options: [
      ["merchandise", "Mercancía"], ["raw_material", "Materia prima"], ["supply", "Insumo"], ["wip", "Producto en proceso"],
      ["finished_good", "Producto terminado"], ["service", "Servicio"]].map(([v, l]) => ({ value: v, label: l })) },
    { name: "category_id", label: "Categoría", type: "select", options: cats },
    { name: "base_uom_id", label: "Unidad base", type: "select", required: true, options: uoms },
    { name: "barcode", label: "Código de barras" },
    { name: "sales_tax_id", label: "Impuesto en ventas", type: "select", options: taxes },
    { name: "purchase_tax_id", label: "Impuesto en compras", type: "select", options: taxes },
    { name: "list_price", label: "Precio de lista", type: "number" },
    { name: "min_stock", label: "Existencia mínima", type: "number" }, { name: "max_stock", label: "Existencia máxima", type: "number" },
    { name: "is_stocked", label: "Inventariable", type: "checkbox" }, { name: "track_lots", label: "Maneja lotes", type: "checkbox" },
    { name: "track_expiry", label: "Controla vencimiento", type: "checkbox" }, { name: "track_serials", label: "Maneja series", type: "checkbox" },
    { name: "requires_inspection", label: "Requiere inspección de recepción", type: "checkbox" },
    { name: "is_active", label: "Activo", type: "checkbox" },
  ];
  return <ResourcePage title="Artículos" path="/items" writePerm="masters.items.create" exportPerm="masters.items.export"
    fields={fields} columns={[{ key: "sku", title: "SKU" }, { key: "name", title: "Descripción" }, { key: "item_type", title: "Tipo" },
      { key: "list_price", title: "Precio", align: "right", render: (r) => fmtMoney(r.list_price) },
      { key: "min_stock", title: "Mín / Máx", align: "right", render: (r) => `${fmtNumber(r.min_stock)} / ${fmtNumber(r.max_stock)}` },
      { key: "flags", title: "Control", render: (r) => [r.track_lots && "Lote", r.track_expiry && "Venc.", r.requires_inspection && "Inspección"].filter(Boolean).join(" · ") },
      active]} />;
}

export function TaxesPage() {
  const accounts = useOptions("/accounts?limit=500", (x) => `${x.code} ${x.name}`);
  return <ResourcePage title="Impuestos y retenciones" path="/taxes" writePerm="masters.taxes.admin"
    subtitle="Tarifas parametrizables: deben ser validadas por el contador o revisor fiscal antes de producción"
    fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
      { name: "kind", label: "Clase", type: "select", required: true, options: [["vat", "IVA"], ["consumption", "Impoconsumo"],
        ["withholding_income", "Retención renta/ISLR"], ["withholding_vat", "Retención IVA"], ["withholding_ica", "Retención ICA"],
        ["igtf", "IGTF"]].map(([v, l]) => ({ value: v, label: l })) },
      { name: "rate", label: "Tarifa %", type: "number", required: true },
      { name: "base", label: "Base", type: "select", options: [{ value: "subtotal", label: "Subtotal" }, { value: "vat", label: "Valor del IVA" }] },
      { name: "min_base_amount", label: "Base mínima", type: "number" },
      { name: "applies_to", label: "Aplica a", type: "select", options: [["both", "Ventas y compras"], ["sales", "Ventas"], ["purchases", "Compras"]].map(([v, l]) => ({ value: v, label: l })) },
      { name: "electronic_code", label: "Código documento electrónico" },
      { name: "sales_account_id", label: "Cuenta en ventas", type: "select", options: accounts },
      { name: "purchase_account_id", label: "Cuenta en compras", type: "select", options: accounts },
      { name: "is_active", label: "Activo", type: "checkbox" }]}
    columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" }, { key: "kind", title: "Clase" },
      { key: "rate", title: "Tarifa %", align: "right", render: (r) => fmtNumber(r.rate, 4) }, { key: "base", title: "Base" }, active]} />;
}

export function AccountsPage() {
  return <ResourcePage title="Plan de cuentas" path="/accounts" writePerm="accounting.accounts.admin" exportPerm="accounting.reports.export"
    fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
      { name: "account_type", label: "Tipo", type: "select", required: true, options: [["asset", "Activo"], ["liability", "Pasivo"],
        ["equity", "Patrimonio"], ["revenue", "Ingreso"], ["expense", "Gasto"], ["cost", "Costo"]].map(([v, l]) => ({ value: v, label: l })) },
      { name: "normal_balance", label: "Naturaleza", type: "select", required: true, options: [{ value: "debit", label: "Débito" }, { value: "credit", label: "Crédito" }] },
      { name: "parent_id", label: "Cuenta padre (id)", type: "number" },
      { name: "is_postable", label: "De movimiento", type: "checkbox" }, { name: "requires_party", label: "Exige tercero", type: "checkbox" },
      { name: "requires_cost_center", label: "Exige centro de costo", type: "checkbox" }, { name: "is_cash", label: "Caja/bancos", type: "checkbox" },
      { name: "is_active", label: "Activa", type: "checkbox" }]}
    columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" }, { key: "account_type", title: "Tipo" },
      { key: "is_postable", title: "Movimiento", render: (r) => yes(r.is_postable) }, active]} />;
}

export function WarehousesPage() {
  const sites = useOptions("/sites", (x) => x.name);
  const whs = useOptions("/warehouses", (x) => `${x.code} ${x.name}`);
  return <>
    <ResourcePage title="Bodegas" path="/warehouses" writePerm="inventory.config.admin"
      fields={[{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true },
        { name: "site_id", label: "Sede", type: "select", required: true, options: sites }, { name: "is_active", label: "Activa", type: "checkbox" }]}
      columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" }, active]} />
    <ResourcePage title="Ubicaciones" path="/locations" writePerm="inventory.config.admin"
      fields={[{ name: "warehouse_id", label: "Bodega", type: "select", required: true, options: whs },
        { name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true }, { name: "zone", label: "Zona" },
        { name: "location_type", label: "Tipo", type: "select", options: ["receiving", "storage", "quality", "dispatch", "production", "scrap", "transit"].map((v) => ({ value: v, label: v })) },
        { name: "is_active", label: "Activa", type: "checkbox" }]}
      columns={[{ key: "code", title: "Código" }, { key: "name", title: "Nombre" }, { key: "zone", title: "Zona" },
        { key: "location_type", title: "Tipo" }, active]} />
  </>;
}

export function NumberingPage() {
  return <ResourcePage title="Numeración autorizada" path="/einvoicing/numbering-ranges" writePerm="einvoicing.numbering.admin"
    subtitle="Resoluciones DIAN / asignaciones de imprenta digital. La clave técnica viaja por HTTPS y la API nunca la devuelve en consultas."
    fields={[{ name: "doc_type", label: "Documento", type: "select", required: true, options: [["invoice", "Factura"], ["credit_note", "Nota crédito"], ["debit_note", "Nota débito"]].map(([v, l]) => ({ value: v, label: l })) },
      { name: "prefix", label: "Prefijo", required: true }, { name: "range_from", label: "Desde", type: "number", required: true },
      { name: "range_to", label: "Hasta", type: "number", required: true }, { name: "next_number", label: "Siguiente", type: "number", required: true },
      { name: "valid_from", label: "Vigente desde", type: "date", required: true }, { name: "valid_to", label: "Vigente hasta", type: "date", required: true },
      { name: "authorization_number", label: "Número de resolución/autorización", required: true },
      { name: "technical_key", label: "Clave técnica (solo escritura)" },
      { name: "environment", label: "Ambiente", type: "select", options: [{ value: "sandbox", label: "Pruebas" }, { value: "production", label: "Producción" }] },
      { name: "is_active", label: "Activa", type: "checkbox" }]}
    columns={[{ key: "doc_type", title: "Documento" }, { key: "prefix", title: "Prefijo" },
      { key: "range", title: "Rango", render: (r) => `${r.range_from} – ${r.range_to}` }, { key: "next_number", title: "Siguiente" },
      { key: "valid_to", title: "Vence" }, { key: "environment", title: "Ambiente", render: (r) => <Badge value={r.environment === "sandbox" ? "warning" : "ok"} /> }, active]} />;
}

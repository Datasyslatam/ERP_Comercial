import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useSession } from "../lib/session";

interface NavItem { to: string; label: string; perm: string; module?: string }

export const NAV: { section: string; items: NavItem[] }[] = [
  { section: "Gerencia", items: [
    { to: "/", label: "Dashboard ejecutivo", perm: "kpi.dashboard.read" },
    { to: "/gerencia/alertas", label: "Alertas", perm: "kpi.alerts.read" },
    { to: "/gerencia/metas", label: "Metas y presupuestos", perm: "accounting.budget.read" },
  ] },
  { section: "Compras", items: [
    { to: "/compras/solicitudes", label: "Solicitudes", perm: "purchasing.requisition.read", module: "purchasing" },
    { to: "/compras/ordenes", label: "Órdenes de compra", perm: "purchasing.order.read", module: "purchasing" },
    { to: "/compras/facturas", label: "Facturas de proveedor", perm: "purchasing.invoice.read", module: "purchasing" },
  ] },
  { section: "Almacén", items: [
    { to: "/inventario/existencias", label: "Existencias y kardex", perm: "inventory.stock.read", module: "inventory" },
    { to: "/inventario/documentos", label: "Movimientos y ajustes", perm: "inventory.document.read", module: "inventory" },
    { to: "/inventario/conteos", label: "Conteos físicos", perm: "inventory.count.read", module: "inventory" },
  ] },
  { section: "Calidad", items: [
    { to: "/calidad/inspecciones", label: "Inspecciones", perm: "quality.inspection.read", module: "quality" },
    { to: "/calidad/no-conformidades", label: "No conformidades", perm: "quality.nonconformity.read", module: "quality" },
  ] },
  { section: "Ventas y logística", items: [
    { to: "/ventas/pedidos", label: "Pedidos de venta", perm: "sales.order.read", module: "sales" },
    { to: "/logistica/despachos", label: "Despachos", perm: "logistics.dispatch.read", module: "logistics" },
    { to: "/facturacion", label: "Facturación electrónica", perm: "einvoicing.invoice.read", module: "einvoicing" },
  ] },
  { section: "Operaciones", items: [
    { to: "/operaciones/ordenes", label: "Órdenes de trabajo", perm: "operations.work_order.read", module: "operations" },
  ] },
  { section: "Contabilidad", items: [
    { to: "/contabilidad/reportes", label: "Estados financieros", perm: "accounting.reports.read" },
    { to: "/contabilidad/comprobantes", label: "Comprobantes", perm: "accounting.journal.read" },
    { to: "/contabilidad/cartera", label: "Cartera y pagos", perm: "accounting.payments.read" },
    { to: "/contabilidad/periodos", label: "Periodos contables", perm: "accounting.period.read" },
  ] },
  { section: "Datos maestros", items: [
    { to: "/maestros/terceros", label: "Terceros", perm: "masters.parties.read" },
    { to: "/maestros/articulos", label: "Artículos", perm: "masters.items.read" },
    { to: "/maestros/impuestos", label: "Impuestos", perm: "masters.taxes.read" },
    { to: "/maestros/cuentas", label: "Plan de cuentas", perm: "accounting.accounts.read" },
    { to: "/maestros/bodegas", label: "Bodegas y ubicaciones", perm: "inventory.config.read" },
    { to: "/maestros/numeracion", label: "Numeración autorizada", perm: "einvoicing.numbering.read" },
  ] },
  { section: "Administración", items: [
    { to: "/importaciones", label: "Importar datos", perm: "imports.job.read" },
    { to: "/admin/usuarios", label: "Usuarios y roles", perm: "admin.users.read" },
    { to: "/admin/auditoria", label: "Auditoría", perm: "admin.audit.read" },
  ] },
];

export function Layout() {
  const { me, company, selectCompany, logout, can, moduleOn } = useSession();
  const [open, setOpen] = useState(false);
  return (
    <div className="shell">
      <header className="topbar">
        <button className="menu-btn secondary" aria-label="Menú" onClick={() => setOpen(!open)}>☰</button>
        <strong className="brand">DATASYS ERP</strong>
        {me && me.companies.length > 0 && (
          <select aria-label="Empresa" value={company?.id ?? ""} onChange={(e) => selectCompany(Number(e.target.value))}>
            {me.companies.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.name} ({c.country})</option>)}
          </select>
        )}
        <span className="spacer" />
        <span className="muted hide-sm">{me?.full_name}</span>
        <button className="secondary" onClick={logout}>Salir</button>
      </header>
      <nav className={`sidebar ${open ? "open" : ""}`} onClick={() => setOpen(false)}>
        {NAV.map((s) => {
          const items = s.items.filter((i) => can(i.perm) && (!i.module || moduleOn(i.module)));
          if (!items.length) return null;
          return (
            <div key={s.section}>
              <h4>{s.section}</h4>
              {items.map((i) => <NavLink key={i.to} to={i.to} end={i.to === "/"}>{i.label}</NavLink>)}
            </div>
          );
        })}
      </nav>
      <main className="content">
        {!company ? <p className="alert alert-warning">Su usuario no tiene empresas asignadas.</p> : <Outlet />}
      </main>
    </div>
  );
}

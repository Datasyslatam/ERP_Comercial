import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession } from "../lib/session";
import { ChangePasswordForm } from "../pages/Admin";
import { Modal } from "./ui";
import { BrandMark, BuildingIcon, Chevron, LogoutIcon, MenuIcon, SectionIcon } from "./NavIcons";

interface NavItem { to: string; label: string; perm: string; module?: string }

export const NAV: { section: string; items: NavItem[] }[] = [
  { section: "Gerencia", items: [
    { to: "/", label: "Dashboard ejecutivo", perm: "kpi.dashboard.read" },
    { to: "/gerencia/alertas", label: "Alertas", perm: "kpi.alerts.read" },
    { to: "/gerencia/metas", label: "Metas y presupuestos", perm: "accounting.budget.read" },
    { to: "/trazabilidad", label: "Trazabilidad de documentos", perm: "kpi.dashboard.read" },
  ] },
  { section: "Compras", items: [
    { to: "/compras/solicitudes", label: "Solicitudes", perm: "purchasing.requisition.read", module: "purchasing" },
    { to: "/compras/ordenes", label: "Órdenes de compra", perm: "purchasing.order.read", module: "purchasing" },
    { to: "/compras/recepciones", label: "Recepciones", perm: "purchasing.receipt.read", module: "purchasing" },
    { to: "/compras/facturas", label: "Facturas de proveedor", perm: "purchasing.invoice.read", module: "purchasing" },
    { to: "/compras/historial-precios", label: "Historial de precios", perm: "purchasing.order.read", module: "purchasing" },
    { to: "/compras/evaluacion-proveedores", label: "Evaluación de proveedores", perm: "purchasing.supplier_eval.read", module: "purchasing" },
    { to: "/compras/presupuesto", label: "Presupuesto de compras", perm: "purchasing.order.read", module: "purchasing" },
  ] },
  { section: "Almacén", items: [
    { to: "/inventario/existencias", label: "Existencias", perm: "inventory.stock.read", module: "inventory" },
    { to: "/inventario/kardex", label: "Kardex", perm: "inventory.stock.read", module: "inventory" },
    { to: "/inventario/reabastecimiento", label: "Reabastecimiento", perm: "inventory.stock.read", module: "inventory" },
    { to: "/inventario/vencimientos", label: "Vencimientos", perm: "inventory.stock.read", module: "inventory" },
    { to: "/inventario/documentos", label: "Movimientos y ajustes", perm: "inventory.document.read", module: "inventory" },
    { to: "/inventario/conteos", label: "Conteos físicos", perm: "inventory.count.read", module: "inventory" },
  ] },
  { section: "Calidad", items: [
    { to: "/calidad/inspecciones", label: "Inspecciones", perm: "quality.inspection.read", module: "quality" },
    { to: "/calidad/no-conformidades", label: "No conformidades", perm: "quality.nonconformity.read", module: "quality" },
    { to: "/calidad/planes", label: "Planes de inspección", perm: "quality.plan.read", module: "quality" },
    { to: "/calidad/lotes", label: "Lotes e historial", perm: "quality.inspection.read", module: "quality" },
  ] },
  { section: "Ventas y logística", items: [
    { to: "/ventas/cotizaciones", label: "Cotizaciones", perm: "sales.quote.read", module: "sales" },
    { to: "/ventas/pedidos", label: "Pedidos de venta", perm: "sales.order.read", module: "sales" },
    { to: "/ventas/listas-precios", label: "Listas de precios", perm: "sales.pricing.read", module: "sales" },
    { to: "/ventas/promociones", label: "Promociones", perm: "sales.pricing.read", module: "sales" },
    { to: "/logistica/despachos", label: "Despachos", perm: "logistics.dispatch.read", module: "logistics" },
    { to: "/logistica/rutas", label: "Rutas y plan de entregas", perm: "logistics.dispatch.read", module: "logistics" },
    { to: "/logistica/incidencias", label: "Incidencias de entrega", perm: "logistics.dispatch.read", module: "logistics" },
    { to: "/logistica/devoluciones", label: "Devoluciones", perm: "logistics.return.read", module: "logistics" },
    { to: "/facturacion", label: "Facturación electrónica", perm: "einvoicing.invoice.read", module: "einvoicing" },
  ] },
  { section: "Operaciones", items: [
    { to: "/operaciones/ordenes", label: "Órdenes de trabajo", perm: "operations.work_order.read", module: "operations" },
    { to: "/operaciones/listas-materiales", label: "Listas de materiales", perm: "operations.work_order.read", module: "operations" },
  ] },
  { section: "Contabilidad", items: [
    { to: "/contabilidad/reportes", label: "Estados financieros", perm: "accounting.reports.read" },
    { to: "/contabilidad/comprobantes", label: "Comprobantes", perm: "accounting.journal.read" },
    { to: "/contabilidad/cuentas-por-cobrar", label: "Cuentas por cobrar", perm: "accounting.payments.read" },
    { to: "/contabilidad/cuentas-por-pagar", label: "Cuentas por pagar", perm: "accounting.payments.read" },
    { to: "/contabilidad/pagos", label: "Pagos y recaudos", perm: "accounting.payments.read" },
    { to: "/contabilidad/conciliacion", label: "Conciliación bancaria", perm: "accounting.bank.read" },
    { to: "/contabilidad/fiscal", label: "Libros y reportes fiscales", perm: "accounting.tax_reports.read" },
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
    { to: "/admin/usuarios", label: "Usuarios", perm: "admin.users.read" },
    { to: "/admin/roles", label: "Roles y permisos", perm: "admin.roles.read" },
    { to: "/admin/auditoria", label: "Auditoría", perm: "admin.audit.read" },
  ] },
];

/** Sección del menú a la que pertenece la ruta actual (para desplegarla al navegar). */
export function sectionOf(pathname: string): string | undefined {
  return NAV.find((s) => s.items.some((i) => (i.to === "/" ? pathname === "/" : pathname.startsWith(i.to))))?.section;
}

/** Opción del menú que corresponde a la ruta actual (la más específica), para la ruta de navegación. */
/** Opción del menú que corresponde a la ruta (la más específica), con su sección. */
function navItemOf(pathname: string): (NavItem & { section: string }) | undefined {
  let best: (NavItem & { section: string }) | undefined;
  for (const s of NAV) for (const i of s.items) {
    const hit = i.to === "/" ? pathname === "/" : pathname === i.to || pathname.startsWith(`${i.to}/`);
    if (hit && (!best || i.to.length > best.to.length)) best = { ...i, section: s.section };
  }
  return best;
}

export function pageOf(pathname: string): { section: string; label: string } | undefined {
  const item = navItemOf(pathname);
  return item && { section: item.section, label: item.label };
}

const COUNTRY: Record<string, string> = { CO: "Colombia", VE: "Venezuela" };

function initials(name?: string) {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export function Layout() {
  const { me, company, selectCompany, logout, can, moduleOn } = useSession();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const page = pageOf(pathname);
  // Una dirección escrita a mano puede apuntar a un módulo desactivado o sin permiso: se avisa en lugar de
  // dejar la pantalla esperando datos que la API rechaza.
  const target = navItemOf(pathname);
  const blocked = !target ? null
    : target.module && !moduleOn(target.module) ? `«${target.label}» pertenece a un módulo que no está activo para esta empresa.`
    : !can(target.perm) ? "Su rol no tiene acceso a esta pantalla." : null;
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set([sectionOf(pathname) ?? NAV[0].section]));
  useEffect(() => {
    const current = sectionOf(pathname);
    if (current) setExpanded((prev) => (prev.has(current) ? prev : new Set(prev).add(current)));
  }, [pathname]);
  const toggle = (section: string) => setExpanded((prev) => {
    const next = new Set(prev);
    if (!next.delete(section)) next.add(section);
    return next;
  });
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-brand">
          <button className="menu-btn icon-btn" aria-label="Menú" aria-expanded={open} onClick={() => setOpen(!open)}>
            <MenuIcon />
          </button>
          <BrandMark />
          <div className="brand-text">
            <strong>DATASYS</strong>
            <span>LATAM GROUP · ERP</span>
          </div>
        </div>
        {page && (
          <nav className="crumbs hide-sm" aria-label="Ruta de navegación">
            <span>{page.section}</span>
            <Chevron />
            <span aria-current="page">{page.label}</span>
          </nav>
        )}
        <span className="spacer" />
        {me && me.companies.length > 0 && (
          <label className="company-switch" title="Empresa activa">
            <BuildingIcon />
            <select aria-label="Empresa" value={company?.id ?? ""} onChange={(e) => selectCompany(Number(e.target.value))}>
              {me.companies.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.name} ({c.country})</option>)}
            </select>
            {company && <span className="country-tag" title={COUNTRY[company.country] ?? company.country}>{company.country}</span>}
          </label>
        )}
        {me && (
          <button type="button" className="user-chip" title={me.sso ? me.email : `${me.email} · Cambiar contraseña`}
                  disabled={me.sso} onClick={() => setChangingPassword(true)}>
            <span className="avatar" aria-hidden="true">{initials(me.full_name)}</span>
            <span className="user-meta hide-sm">
              <strong>{me.full_name}</strong>
              <small>{me.email}</small>
            </span>
          </button>
        )}
        <button className="logout-btn" onClick={logout} aria-label="Salir" title="Cerrar sesión">
          <LogoutIcon /><span className="hide-sm">Salir</span>
        </button>
      </header>
      <nav className={`sidebar ${open ? "open" : ""}`} aria-label="Menú principal">
        {NAV.map((s) => {
          const items = s.items.filter((i) => can(i.perm) && (!i.module || moduleOn(i.module)));
          if (!items.length) return null;
          const isOpen = expanded.has(s.section);
          const id = `nav-${s.section.normalize("NFD").replace(/[^a-zA-Z]+/g, "-").toLowerCase()}`;
          return (
            <div key={s.section} className={`nav-section ${isOpen ? "expanded" : ""}`}>
              <button type="button" className="nav-section-btn" aria-expanded={isOpen} aria-controls={id}
                onClick={() => toggle(s.section)}>
                <SectionIcon section={s.section} />
                <span className="nav-section-label">{s.section}</span>
                <Chevron />
              </button>
              <div id={id} className="nav-items" aria-hidden={!isOpen}>
                <div>
                  {items.map((i) => (
                    <NavLink key={i.to} to={i.to} end={i.to === "/"} tabIndex={isOpen ? undefined : -1}
                      onClick={() => setOpen(false)}>
                      <Chevron className="nav-pointer" />{i.label}
                    </NavLink>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </nav>
      <main className="content">
        {!company ? <p className="alert alert-warning">Su usuario no tiene empresas asignadas.</p>
          : blocked ? <p className="alert alert-warning" role="alert">{blocked}</p> : <Outlet />}
      </main>
      {changingPassword && <Modal title="Cambiar contraseña" onClose={() => setChangingPassword(false)}>
        <ChangePasswordForm onDone={() => setChangingPassword(false)} />
      </Modal>}
    </div>
  );
}

import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AlertsPage, BankReconciliationPage, EntriesPage, GoalsBudgetsPage, PaymentsPage, PeriodsPage, ReceivablesPage,
  ReportsPage } from "./pages/Accounting";
import { Dashboard } from "./pages/Dashboard";
import { CountsPage, ExpiringPage, InventoryDocumentsPage, KardexPage, ReplenishmentPage, StockPage } from "./pages/Inventory";
import { Login } from "./pages/Login";
import { AccountsPage, ItemsPage, NumberingPage, PartiesPage, TaxesPage, WarehousesPage } from "./pages/Masters";
import { AuditPage, ChangePasswordForm, RolesPage, UsersPage } from "./pages/Admin";
import { ImportsPage, WorkOrdersPage } from "./pages/Other";
import { OrderDetailPage, OrdersPage, PriceHistoryPage, PurchaseBudgetPage, ReceiptsPage, RequisitionsPage, SupplierEvaluationPage,
  SupplierInvoicesPage } from "./pages/Purchasing";
import { InspectionPlansPage, InspectionsPage, LotsQualityPage, NonConformitiesPage } from "./pages/Quality";
import { DispatchesPage, QuotesPage, SalesOrderDetailPage, SalesOrdersPage } from "./pages/Sales";
import { TracePage } from "./pages/Trace";
import { DispatchDetailPage, IncidentsPage, ReturnsPage, RoutesPlanPage } from "./pages/Logistics";
import { InvoicingPage } from "./pages/Invoicing";
import { BomsPage } from "./pages/Production";
import { SessionProvider, useSession } from "./lib/session";

function Routed() {
  const { me, loading } = useSession();
  if (loading) return <p className="muted center">Cargando…</p>;
  if (!me) return <Login />;
  if (me.must_change_password) return <ForcedPasswordChange />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="gerencia/alertas" element={<AlertsPage />} />
        <Route path="gerencia/metas" element={<GoalsBudgetsPage />} />
        <Route path="gerencia/presupuestos" element={<GoalsBudgetsPage />} />
        <Route path="compras/solicitudes" element={<RequisitionsPage />} />
        <Route path="compras/ordenes" element={<OrdersPage />} />
        <Route path="compras/ordenes/:id" element={<OrderDetailPage />} />
        <Route path="compras/recepciones" element={<ReceiptsPage />} />
        <Route path="compras/facturas" element={<SupplierInvoicesPage />} />
        <Route path="compras/proveedores" element={<PartiesPage />} />
        <Route path="compras/historial-precios" element={<PriceHistoryPage />} />
        <Route path="compras/evaluacion-proveedores" element={<SupplierEvaluationPage />} />
        <Route path="compras/presupuesto" element={<PurchaseBudgetPage />} />
        <Route path="inventario/existencias" element={<StockPage />} />
        <Route path="inventario/kardex" element={<KardexPage />} />
        <Route path="inventario/reabastecimiento" element={<ReplenishmentPage />} />
        <Route path="inventario/vencimientos" element={<ExpiringPage />} />
        <Route path="inventario/documentos" element={<InventoryDocumentsPage />} />
        <Route path="inventario/conteos" element={<CountsPage />} />
        <Route path="calidad/inspecciones" element={<InspectionsPage />} />
        <Route path="calidad/no-conformidades" element={<NonConformitiesPage />} />
        <Route path="calidad/planes" element={<InspectionPlansPage />} />
        <Route path="calidad/lotes" element={<LotsQualityPage />} />
        <Route path="ventas/cotizaciones" element={<QuotesPage />} />
        <Route path="ventas/pedidos" element={<SalesOrdersPage />} />
        <Route path="ventas/pedidos/:id" element={<SalesOrderDetailPage />} />
        <Route path="trazabilidad" element={<TracePage />} />
        <Route path="logistica/despachos" element={<DispatchesPage />} />
        <Route path="logistica/despachos/:id" element={<DispatchDetailPage />} />
        <Route path="logistica/incidencias" element={<IncidentsPage />} />
        <Route path="logistica/devoluciones" element={<ReturnsPage />} />
        <Route path="logistica/rutas" element={<RoutesPlanPage />} />
        <Route path="facturacion" element={<InvoicingPage />} />
        <Route path="operaciones/ordenes" element={<WorkOrdersPage />} />
        <Route path="operaciones/listas-materiales" element={<BomsPage />} />
        <Route path="contabilidad/reportes" element={<ReportsPage />} />
        <Route path="contabilidad/estado-resultados" element={<ReportsPage />} />
        <Route path="contabilidad/flujo-efectivo" element={<ReportsPage />} />
        <Route path="contabilidad/comprobantes" element={<EntriesPage />} />
        <Route path="contabilidad/cartera" element={<ReceivablesPage />} />
        <Route path="contabilidad/pagos" element={<PaymentsPage />} />
        <Route path="contabilidad/conciliacion" element={<BankReconciliationPage />} />
        <Route path="contabilidad/periodos" element={<PeriodsPage />} />
        <Route path="maestros/terceros" element={<PartiesPage />} />
        <Route path="maestros/articulos" element={<ItemsPage />} />
        <Route path="maestros/impuestos" element={<TaxesPage />} />
        <Route path="maestros/cuentas" element={<AccountsPage />} />
        <Route path="maestros/bodegas" element={<WarehousesPage />} />
        <Route path="maestros/numeracion" element={<NumberingPage />} />
        <Route path="importaciones" element={<ImportsPage />} />
        <Route path="admin/usuarios" element={<UsersPage />} />
        <Route path="admin/roles" element={<RolesPage />} />
        <Route path="admin/auditoria" element={<AuditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

/** Contraseña asignada por un administrador: se exige cambiarla antes de usar el ERP. */
function ForcedPasswordChange() {
  const { me, logout } = useSession();
  return (
    <div className="login">
      <main className="login-main">
        <div className="login-card">
          <h1>Cambie su contraseña</h1>
          <p className="muted">{me?.full_name} · {me?.email}</p>
          <ChangePasswordForm forced onDone={() => undefined} />
          <button className="secondary" onClick={logout}>Salir</button>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routed />
      </BrowserRouter>
    </SessionProvider>
  );
}

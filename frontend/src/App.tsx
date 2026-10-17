import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AlertsPage, EntriesPage, GoalsBudgetsPage, PeriodsPage, ReceivablesPage, ReportsPage } from "./pages/Accounting";
import { Dashboard } from "./pages/Dashboard";
import { CountsPage, InventoryDocumentsPage, StockPage } from "./pages/Inventory";
import { Login } from "./pages/Login";
import { AccountsPage, ItemsPage, NumberingPage, PartiesPage, TaxesPage, WarehousesPage } from "./pages/Masters";
import { AuditPage, ImportsPage, UsersPage, WorkOrdersPage } from "./pages/Other";
import { OrderDetailPage, OrdersPage, RequisitionsPage, SupplierInvoicesPage } from "./pages/Purchasing";
import { InspectionsPage, NonConformitiesPage } from "./pages/Quality";
import { DispatchesPage, SalesOrdersPage } from "./pages/Sales";
import { DispatchDetailPage, IncidentsPage, ReturnsPage, RoutesPlanPage } from "./pages/Logistics";
import { InvoicingPage } from "./pages/Invoicing";
import { BomsPage } from "./pages/Production";
import { SessionProvider, useSession } from "./lib/session";

function Routed() {
  const { me, loading } = useSession();
  if (loading) return <p className="muted center">Cargando…</p>;
  if (!me) return <Login />;
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
        <Route path="compras/recepciones" element={<OrdersPage />} />
        <Route path="compras/facturas" element={<SupplierInvoicesPage />} />
        <Route path="compras/proveedores" element={<PartiesPage />} />
        <Route path="compras/historial-precios" element={<OrdersPage />} />
        <Route path="inventario/existencias" element={<StockPage />} />
        <Route path="inventario/kardex" element={<StockPage />} />
        <Route path="inventario/reabastecimiento" element={<StockPage />} />
        <Route path="inventario/vencimientos" element={<StockPage />} />
        <Route path="inventario/documentos" element={<InventoryDocumentsPage />} />
        <Route path="inventario/conteos" element={<CountsPage />} />
        <Route path="calidad/inspecciones" element={<InspectionsPage />} />
        <Route path="calidad/no-conformidades" element={<NonConformitiesPage />} />
        <Route path="ventas/pedidos" element={<SalesOrdersPage />} />
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
        <Route path="contabilidad/periodos" element={<PeriodsPage />} />
        <Route path="maestros/terceros" element={<PartiesPage />} />
        <Route path="maestros/articulos" element={<ItemsPage />} />
        <Route path="maestros/impuestos" element={<TaxesPage />} />
        <Route path="maestros/cuentas" element={<AccountsPage />} />
        <Route path="maestros/bodegas" element={<WarehousesPage />} />
        <Route path="maestros/numeracion" element={<NumberingPage />} />
        <Route path="importaciones" element={<ImportsPage />} />
        <Route path="admin/usuarios" element={<UsersPage />} />
        <Route path="admin/auditoria" element={<AuditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
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

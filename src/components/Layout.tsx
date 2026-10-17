import { useState } from 'react';
import { store } from '../store';
import type { User } from '../types';
import {
  LayoutDashboard, ShoppingCart, Package, Factory, Calculator,
  FileText, Shield, Truck, Users, BarChart3, Settings, LogOut,
  Menu, X, ChevronDown, Bell, Search, Database, AlertTriangle,
  ClipboardCheck
} from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
  currentUser: User;
  onLogout: () => void;
  currentModule: string;
  onNavigate: (module: string) => void;
}

const menuItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'purchasing', label: 'Compras', icon: ShoppingCart },
  { id: 'inventory', label: 'Inventario', icon: Package },
  { id: 'production', label: 'Producción', icon: Factory },
  { id: 'accounting', label: 'Contabilidad', icon: Calculator },
  { id: 'invoicing', label: 'Facturación', icon: FileText },
  { id: 'quality', label: 'Calidad', icon: Shield },
  { id: 'logistics', label: 'Logística', icon: Truck },
  { id: 'users', label: 'Usuarios', icon: Users },
  { id: 'reports', label: 'Reportes', icon: BarChart3 },
  { id: 'import', label: 'Importar Datos', icon: Database },
  { id: 'settings', label: 'Configuración', icon: Settings },
];

export default function Layout({ children, currentUser, onLogout, currentModule, onNavigate }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const company = store.getCompany();

  const pendingApprovals = store.getPurchaseRequests().filter(pr => pr.status === 'pending_approval').length;
  const lowStockItems = store.getStockBalances().filter(b => {
    const art = store.getArticle(b.articleId);
    return art && b.available <= art.reorderPoint;
  }).length;
  const openNC = store.getNonConformances().filter(nc => nc.status !== 'closed').length;
  const totalAlerts = pendingApprovals + lowStockItems + openNC;

  const handleLogout = () => {
    store.addAuditLog({
      userId: currentUser.id, action: 'LOGOUT', module: 'auth',
      entityId: currentUser.id, entityType: 'user',
      details: 'Cierre de sesión', timestamp: new Date().toISOString(), ipAddress: '192.168.1.100'
    });
    setUserMenuOpen(false);
    onLogout();
  };

  const handleNav = (moduleId: string) => {
    onNavigate(moduleId);
    setMobileMenuOpen(false);
    setUserMenuOpen(false);
    setNotifOpen(false);
  };

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar Desktop */}
      <aside className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-slate-900 text-white flex flex-col transition-all duration-300 flex-shrink-0 hidden lg:flex`}>
        <div className="p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-sm flex-shrink-0">
              DS
            </div>
            {sidebarOpen && (
              <div className="overflow-hidden">
                <h1 className="font-bold text-sm truncate">DATASYS LATAM</h1>
                <p className="text-xs text-slate-400 truncate">ERP Enterprise</p>
              </div>
            )}
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto py-4">
          {menuItems.map(item => {
            const isActive = currentModule === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNav(item.id)}
                className={`flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg mb-1 transition-colors w-[calc(100%-1rem)] text-left ${
                  isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <item.icon size={20} className="flex-shrink-0" />
                {sidebarOpen && <span className="text-sm truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-700">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors w-full"
          >
            <Menu size={18} />
            {sidebarOpen && <span className="text-sm">Colapsar</span>}
          </button>
        </div>
      </aside>

      {/* Mobile sidebar */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-slate-900 text-white flex flex-col">
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-sm">DS</div>
                <div>
                  <h1 className="font-bold text-sm">DATASYS LATAM</h1>
                  <p className="text-xs text-slate-400">ERP Enterprise</p>
                </div>
              </div>
              <button onClick={() => setMobileMenuOpen(false)}><X size={20} /></button>
            </div>
            <nav className="flex-1 overflow-y-auto py-4">
              {menuItems.map(item => {
                const isActive = currentModule === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleNav(item.id)}
                    className={`flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg mb-1 transition-colors w-[calc(100%-1rem)] text-left ${
                      isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                    }`}
                  >
                    <item.icon size={20} />
                    <span className="text-sm">{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 lg:px-6 py-3 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-4">
            <button className="lg:hidden" onClick={() => setMobileMenuOpen(true)}>
              <Menu size={24} className="text-gray-600" />
            </button>
            <div className="hidden md:flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2">
              <Search size={16} className="text-gray-400" />
              <input
                type="text"
                placeholder="Buscar en el sistema..."
                className="bg-transparent border-none outline-none text-sm w-48 lg:w-64"
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Alerts */}
            <div className="relative">
              <button
                onClick={() => { setNotifOpen(!notifOpen); setUserMenuOpen(false); }}
                className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <Bell size={20} className="text-gray-600" />
                {totalAlerts > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                    {totalAlerts}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-12 w-80 bg-white rounded-xl shadow-xl border border-gray-200 z-50 overflow-hidden">
                  <div className="p-3 border-b border-gray-100 bg-gray-50">
                    <h3 className="font-semibold text-sm">Alertas del Sistema</h3>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {pendingApprovals > 0 && (
                      <button onClick={() => handleNav('purchasing')} className="flex items-start gap-3 p-3 hover:bg-gray-50 border-b border-gray-50 w-full text-left">
                        <AlertTriangle size={16} className="text-amber-500 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="text-sm font-medium">{pendingApprovals} solicitud(es) de compra pendiente(s) de aprobación</p>
                          <p className="text-xs text-gray-500">Módulo de Compras</p>
                        </div>
                      </button>
                    )}
                    {lowStockItems > 0 && (
                      <button onClick={() => handleNav('inventory')} className="flex items-start gap-3 p-3 hover:bg-gray-50 border-b border-gray-50 w-full text-left">
                        <Package size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="text-sm font-medium">{lowStockItems} artículo(s) bajo punto de reorden</p>
                          <p className="text-xs text-gray-500">Módulo de Inventario</p>
                        </div>
                      </button>
                    )}
                    {openNC > 0 && (
                      <button onClick={() => handleNav('quality')} className="flex items-start gap-3 p-3 hover:bg-gray-50 w-full text-left">
                        <ClipboardCheck size={16} className="text-orange-500 mt-0.5 flex-shrink-0" />
                        <div>
                          <p className="text-sm font-medium">{openNC} no conformidad(es) abierta(s)</p>
                          <p className="text-xs text-gray-500">Módulo de Calidad</p>
                        </div>
                      </button>
                    )}
                    {totalAlerts === 0 && (
                      <div className="p-4 text-center text-sm text-gray-500">Sin alertas pendientes</div>
                    )}
                  </div>
                </div>
              )}
            </div>
            {/* User menu */}
            <div className="relative">
              <button
                onClick={() => { setUserMenuOpen(!userMenuOpen); setNotifOpen(false); }}
                className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white text-sm font-medium">
                  {currentUser.fullName.split(' ').map(n => n[0]).join('').slice(0, 2)}
                </div>
                <div className="hidden md:block text-left">
                  <p className="text-sm font-medium text-gray-700">{currentUser.fullName}</p>
                  <p className="text-xs text-gray-500 capitalize">{currentUser.role}</p>
                </div>
                <ChevronDown size={14} className="text-gray-400 hidden md:block" />
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 top-12 w-56 bg-white rounded-xl shadow-xl border border-gray-200 z-50 overflow-hidden">
                  <div className="p-3 border-b border-gray-100">
                    <p className="text-sm font-medium">{currentUser.fullName}</p>
                    <p className="text-xs text-gray-500">{currentUser.email}</p>
                    <p className="text-xs text-gray-400 mt-1">Sede: {store.getBranch(currentUser.branchId)?.name || 'N/A'}</p>
                  </div>
                  <div className="p-2">
                    <button onClick={() => handleNav('settings')} className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg w-full text-left">
                      <Settings size={16} /> Configuración
                    </button>
                    <button onClick={handleLogout} className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg w-full text-left">
                      <LogOut size={16} /> Cerrar Sesión
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Environment banner */}
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-1.5 flex items-center gap-2 flex-shrink-0">
          <AlertTriangle size={14} className="text-amber-600" />
          <span className="text-xs text-amber-700">
            <strong>AMBIENTE DE DESARROLLO</strong> — Datos sintéticos para demostración. No utilizar para operaciones reales.
            Empresa: {company.name} | Moneda: {company.currency}
          </span>
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

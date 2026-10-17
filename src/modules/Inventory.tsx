import React, { useState } from 'react';
import { store } from '../store';
import { Package, Warehouse, ArrowDownUp, AlertTriangle, TrendingDown, BarChart3, Plus, Search } from 'lucide-react';

type Tab = 'stock' | 'movements' | 'warehouses' | 'articles' | 'indicators';

export default function Inventory() {
  const [activeTab, setActiveTab] = useState<Tab>('stock');
  const [searchTerm, setSearchTerm] = useState('');
  const stockBalances = store.getStockBalances();
  const articles = store.getArticles();
  const warehouses = store.getWarehouses();
  const movements = store.getInventoryMovements();

  const tabs = [
    { id: 'stock' as Tab, label: 'Existencias', icon: Package },
    { id: 'movements' as Tab, label: 'Movimientos (Kardex)', icon: ArrowDownUp },
    { id: 'warehouses' as Tab, label: 'Bodegas', icon: Warehouse },
    { id: 'articles' as Tab, label: 'Artículos', icon: BarChart3 },
    { id: 'indicators' as Tab, label: 'Indicadores', icon: TrendingDown },
  ];

  const lowStockItems = stockBalances.filter(b => {
    const art = store.getArticle(b.articleId);
    return art && b.available <= art.reorderPoint;
  });

  const totalInventoryValue = stockBalances.reduce((sum, b) => {
    const art = store.getArticle(b.articleId);
    return sum + (b.quantity * (art?.cost || 0));
  }, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Inventario y Almacén</h1>
          <p className="text-sm text-gray-500 mt-1">Control transaccional con trazabilidad completa</p>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 text-sm">
            <ArrowDownUp size={16} /> Registrar Movimiento
          </button>
          <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
            <Plus size={16} /> Nuevo Artículo
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Package size={20} className="text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{articles.length}</p>
              <p className="text-xs text-gray-500">Artículos registrados</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
              <Warehouse size={20} className="text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{warehouses.length}</p>
              <p className="text-xs text-gray-500">Bodegas activas</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <BarChart3 size={20} className="text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">${totalInventoryValue.toLocaleString()}</p>
              <p className="text-xs text-gray-500">Valor total inventario</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <AlertTriangle size={20} className="text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-red-600">{lowStockItems.length}</p>
              <p className="text-xs text-gray-500">Bajo punto de reorden</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                activeTab === tab.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'stock' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Buscar artículo..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  className="pl-9 pr-3 py-1.5 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <select className="text-sm border border-gray-300 rounded-lg px-3 py-1.5">
                <option>Todas las bodegas</option>
                {warehouses.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Código</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Artículo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Bodega</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Existencia</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Disponible</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Costo Unit.</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Valor Total</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                </tr>
              </thead>
              <tbody>
                {stockBalances.filter(b => {
                  const art = store.getArticle(b.articleId);
                  if (!searchTerm) return true;
                  return art?.name.toLowerCase().includes(searchTerm.toLowerCase()) || art?.code.toLowerCase().includes(searchTerm.toLowerCase());
                }).map(balance => {
                  const art = store.getArticle(balance.articleId);
                  const wh = store.getWarehouse(balance.warehouseId);
                  if (!art) return null;
                  const isLow = balance.available <= art.reorderPoint;
                  return (
                    <tr key={`${balance.articleId}-${balance.warehouseId}`} className={`border-t border-gray-100 hover:bg-gray-50 ${isLow ? 'bg-red-50/50' : ''}`}>
                      <td className="px-4 py-3 font-mono text-xs">{art.code}</td>
                      <td className="px-4 py-3 font-medium">{art.name}</td>
                      <td className="px-4 py-3 text-gray-600">{wh?.name || 'N/A'}</td>
                      <td className="px-4 py-3 text-right">{balance.quantity} {art.unit}</td>
                      <td className="px-4 py-3 text-right font-medium">{balance.available} {art.unit}</td>
                      <td className="px-4 py-3 text-right">${art.cost.toFixed(2)}</td>
                      <td className="px-4 py-3 text-right font-medium">${(balance.quantity * art.cost).toLocaleString()}</td>
                      <td className="px-4 py-3 text-center">
                        {isLow ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                            <AlertTriangle size={10} /> Bajo mínimo
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">Normal</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'movements' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Kardex de Movimientos</h2>
            <p className="text-xs text-gray-500 mt-1">Trazabilidad completa de entradas, salidas y transferencias</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Fecha</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Tipo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Artículo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Bodega</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Cantidad</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Costo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Referencia</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Motivo</th>
                </tr>
              </thead>
              <tbody>
                {movements.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()).map(mov => {
                  const art = store.getArticle(mov.articleId);
                  const wh = store.getWarehouse(mov.warehouseId);
                  return (
                    <tr key={mov.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-600">{new Date(mov.timestamp).toLocaleString()}</td>
                      <td className="px-4 py-3 text-center">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          mov.type === 'in' ? 'bg-emerald-100 text-emerald-700' :
                          mov.type === 'out' ? 'bg-red-100 text-red-700' :
                          mov.type === 'transfer' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'
                        }`}>
                          {mov.type === 'in' ? '↑ Entrada' : mov.type === 'out' ? '↓ Salida' : mov.type === 'transfer' ? '↔ Transfer.' : '⚙ Ajuste'}
                        </span>
                      </td>
                      <td className="px-4 py-3">{art?.name || 'N/A'}</td>
                      <td className="px-4 py-3 text-gray-600">{wh?.name || 'N/A'}</td>
                      <td className="px-4 py-3 text-right font-medium">{mov.quantity} {art?.unit}</td>
                      <td className="px-4 py-3 text-right">${mov.cost.toLocaleString()}</td>
                      <td className="px-4 py-3 font-mono text-xs">{mov.reference}</td>
                      <td className="px-4 py-3 text-gray-600">{mov.reason}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'warehouses' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {warehouses.map(wh => {
            const branch = store.getBranch(wh.branchId);
            return (
              <div key={wh.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Warehouse size={20} className="text-blue-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{wh.name}</h3>
                      <p className="text-xs text-gray-500">{wh.code} • {branch?.name}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${wh.active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-700'}`}>
                    {wh.active ? 'Activa' : 'Inactiva'}
                  </span>
                </div>
                <div className="text-sm text-gray-600 mb-2">
                  <span className="font-medium">Tipo:</span> {wh.type === 'raw_materials' ? 'Materias Primas' : wh.type === 'finished' ? 'Productos Terminados' : wh.type === 'wip' ? 'En Proceso' : 'General'}
                </div>
                <div className="mt-3">
                  <p className="text-xs text-gray-500 mb-1">Zonas:</p>
                  <div className="flex flex-wrap gap-1">
                    {wh.zones.map(z => (
                      <span key={z.id} className="px-2 py-0.5 bg-gray-100 rounded text-xs">{z.code} - {z.name}</span>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'articles' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Código</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Nombre</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Tipo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Categoría</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Unidad</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Mín</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Máx</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Costo</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Método</th>
                </tr>
              </thead>
              <tbody>
                {articles.map(art => (
                  <tr key={art.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{art.code}</td>
                    <td className="px-4 py-3 font-medium">{art.name}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        art.type === 'raw_material' ? 'bg-blue-100 text-blue-700' :
                        art.type === 'finished' ? 'bg-emerald-100 text-emerald-700' :
                        art.type === 'wip' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-700'
                      }`}>
                        {art.type === 'raw_material' ? 'Mat. Prima' : art.type === 'finished' ? 'Terminado' : art.type === 'wip' ? 'En Proceso' : art.type === 'supply' ? 'Suministro' : 'Servicio'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{art.category}</td>
                    <td className="px-4 py-3 text-center">{art.unit}</td>
                    <td className="px-4 py-3 text-right">{art.minStock}</td>
                    <td className="px-4 py-3 text-right">{art.maxStock}</td>
                    <td className="px-4 py-3 text-right">${art.cost.toFixed(2)}</td>
                    <td className="px-4 py-3 text-center text-xs">{art.costMethod === 'fifo' ? 'FIFO' : art.costMethod === 'weighted_avg' ? 'Prom.Pond.' : 'Estándar'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'indicators' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Valoración del inventario', value: `$${totalInventoryValue.toLocaleString()}`, formula: 'SUM(cantidad × costo_unitario)', unit: 'USD' },
            { name: 'Rotación de inventarios', value: '4.2 veces', target: '6 veces', formula: 'Costo ventas / Inventario promedio', status: 'warning' },
            { name: 'Días de inventario', value: '87 días', target: '60 días', formula: '365 / Rotación', status: 'warning' },
            { name: 'Artículos bajo mínimo', value: `${lowStockItems.length}`, target: '0', formula: 'COUNT WHERE disponible < punto_reorden', status: lowStockItems.length > 0 ? 'critical' : 'good' },
            { name: 'Exactitud de inventario', value: '96.5%', target: '98%', formula: 'Líneas exactas / Total líneas × 100', status: 'warning' },
            { name: 'Materiales inmovilizados', value: '$2,340', target: '< $1,000', formula: 'Valor artículos sin movimiento > 90 días', status: 'warning' },
          ].map((kpi, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="text-sm font-medium text-gray-700 mb-2">{kpi.name}</h3>
              <p className="text-2xl font-bold text-gray-900">{kpi.value}</p>
              {kpi.target && <p className="text-xs text-gray-500 mt-1">Meta: {kpi.target}</p>}
              <p className="text-xs text-gray-400 mt-2 italic">Fórmula: {kpi.formula}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

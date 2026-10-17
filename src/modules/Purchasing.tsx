import { useState } from 'react';
import { store } from '../store';
import { ShoppingCart, Users, FileText, CheckCircle, Clock, AlertCircle, Plus, Eye } from 'lucide-react';

type Tab = 'orders' | 'requests' | 'suppliers' | 'indicators';

export default function Purchasing() {
  const [activeTab, setActiveTab] = useState<Tab>('orders');
  const [showDetail, setShowDetail] = useState<string | null>(null);
  const purchaseOrders = store.getPurchaseOrders();
  const purchaseRequests = store.getPurchaseRequests();
  const suppliers = store.getSuppliers();

  const tabs = [
    { id: 'orders' as Tab, label: 'Órdenes de Compra', icon: ShoppingCart, count: purchaseOrders.length },
    { id: 'requests' as Tab, label: 'Solicitudes', icon: FileText, count: purchaseRequests.length },
    { id: 'suppliers' as Tab, label: 'Proveedores', icon: Users, count: suppliers.length },
    { id: 'indicators' as Tab, label: 'Indicadores', icon: AlertCircle, count: 0 },
  ];

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-700',
      sent: 'bg-blue-100 text-blue-700',
      partial: 'bg-amber-100 text-amber-700',
      received: 'bg-emerald-100 text-emerald-700',
      cancelled: 'bg-red-100 text-red-700',
      pending_approval: 'bg-amber-100 text-amber-700',
      approved: 'bg-emerald-100 text-emerald-700',
      rejected: 'bg-red-100 text-red-700',
      converted: 'bg-blue-100 text-blue-700',
    };
    const labels: Record<string, string> = {
      draft: 'Borrador', sent: 'Enviada', partial: 'Parcial', received: 'Recibida',
      cancelled: 'Cancelada', pending_approval: 'Pendiente Aprob.', approved: 'Aprobada',
      rejected: 'Rechazada', converted: 'Convertida',
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>{labels[status] || status}</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Compras y Proveedores</h1>
          <p className="text-sm text-gray-500 mt-1">Gestión del ciclo completo de abastecimiento</p>
        </div>
        <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm">
          <Plus size={16} /> Nueva Orden de Compra
        </button>
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
              {tab.count > 0 && <span className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full text-xs">{tab.count}</span>}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'orders' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Órdenes de Compra</h2>
            <div className="flex items-center gap-2">
              <select className="text-sm border border-gray-300 rounded-lg px-3 py-1.5">
                <option>Todos los estados</option>
                <option>Borrador</option>
                <option>Enviada</option>
                <option>Parcial</option>
                <option>Recibida</option>
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Número</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Proveedor</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Fecha</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Entrega</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Total</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {purchaseOrders.map(po => {
                  const supplier = store.getSupplier(po.supplierId);
                  return (
                    <tr key={po.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-blue-600">{po.number}</td>
                      <td className="px-4 py-3">{supplier?.name || 'N/A'}</td>
                      <td className="px-4 py-3">{new Date(po.createdAt).toLocaleDateString()}</td>
                      <td className="px-4 py-3">{new Date(po.deliveryDate).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-right font-medium">${po.total.toLocaleString()}</td>
                      <td className="px-4 py-3 text-center">{getStatusBadge(po.status)}</td>
                      <td className="px-4 py-3 text-center">
                        <button onClick={() => setShowDetail(po.id)} className="text-blue-600 hover:text-blue-800">
                          <Eye size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {showDetail && (() => {
            const po = store.getPurchaseOrder(showDetail);
            if (!po) return null;
            const supplier = store.getSupplier(po.supplierId);
            return (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowDetail(null)}>
                <div className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                  <div className="p-6 border-b border-gray-200">
                    <h3 className="text-lg font-bold">Orden de Compra {po.number}</h3>
                    <p className="text-sm text-gray-500">Proveedor: {supplier?.name}</p>
                  </div>
                  <div className="p-6 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div><p className="text-xs text-gray-500">Estado</p><div className="mt-1">{getStatusBadge(po.status)}</div></div>
                      <div><p className="text-xs text-gray-500">Fecha entrega</p><p className="font-medium">{new Date(po.deliveryDate).toLocaleDateString()}</p></div>
                      <div><p className="text-xs text-gray-500">Subtotal</p><p className="font-medium">${po.subtotal.toLocaleString()}</p></div>
                      <div><p className="text-xs text-gray-500">Impuesto (12%)</p><p className="font-medium">${po.tax.toLocaleString()}</p></div>
                      <div><p className="text-xs text-gray-500">Total</p><p className="font-bold text-lg">${po.total.toLocaleString()}</p></div>
                      <div><p className="text-xs text-gray-500">Plazo pago</p><p className="font-medium">{po.paymentTerms} días</p></div>
                    </div>
                    <div>
                      <h4 className="font-medium text-sm mb-2">Detalle de Items</h4>
                      <table className="w-full text-sm">
                        <thead><tr className="border-b"><th className="text-left py-1">Artículo</th><th className="text-right py-1">Cant.</th><th className="text-right py-1">Recibido</th><th className="text-right py-1">P. Unit.</th><th className="text-right py-1">Total</th></tr></thead>
                        <tbody>
                          {po.items.map(item => {
                            const art = store.getArticle(item.articleId);
                            return (
                              <tr key={item.id} className="border-b border-gray-50">
                                <td className="py-1">{art?.name || item.articleId}</td>
                                <td className="py-1 text-right">{item.quantity}</td>
                                <td className="py-1 text-right">{item.receivedQuantity}</td>
                                <td className="py-1 text-right">${item.unitPrice.toFixed(2)}</td>
                                <td className="py-1 text-right font-medium">${item.total.toLocaleString()}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="p-4 border-t border-gray-200 flex justify-end">
                    <button onClick={() => setShowDetail(null)} className="px-4 py-2 bg-gray-100 rounded-lg text-sm hover:bg-gray-200">Cerrar</button>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {activeTab === 'requests' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold text-gray-900">Solicitudes de Compra</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Número</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Solicitante</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Prioridad</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Fecha</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Justificación</th>
                </tr>
              </thead>
              <tbody>
                {purchaseRequests.map(pr => {
                  const user = store.getUser(pr.requestedBy);
                  return (
                    <tr key={pr.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 font-medium text-blue-600">{pr.number}</td>
                      <td className="px-4 py-3">{user?.fullName || 'N/A'}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          pr.priority === 'urgent' ? 'bg-red-100 text-red-700' :
                          pr.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                          pr.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-700'
                        }`}>{pr.priority}</span>
                      </td>
                      <td className="px-4 py-3">{new Date(pr.createdAt).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-center">{getStatusBadge(pr.status)}</td>
                      <td className="px-4 py-3 text-gray-600 max-w-xs truncate">{pr.justification}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'suppliers' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Directorio de Proveedores</h2>
            <button className="flex items-center gap-2 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-sm hover:bg-blue-700">
              <Plus size={14} /> Nuevo
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Nombre</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">RUC/ID</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Contacto</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Categoría</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Rating</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Plazo Pago</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map(sup => (
                  <tr key={sup.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium">{sup.name}</td>
                    <td className="px-4 py-3 text-gray-600">{sup.taxId}</td>
                    <td className="px-4 py-3">
                      <div className="text-gray-700">{sup.contactName}</div>
                      <div className="text-xs text-gray-500">{sup.email}</div>
                    </td>
                    <td className="px-4 py-3">{sup.category}</td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {[1, 2, 3, 4, 5].map(i => (
                          <div key={i} className={`w-2 h-2 rounded-full ${i <= Math.round(sup.rating) ? 'bg-amber-400' : 'bg-gray-200'}`} />
                        ))}
                        <span className="ml-1 text-xs text-gray-500">{sup.rating}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">{sup.paymentTerms} días</td>
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
            { name: 'Tiempo promedio ciclo de compra', value: '14 días', target: '10 días', status: 'warning', formula: 'AVG(días solicitud → recepción)' },
            { name: 'Variación precio vs. anterior', value: '+2.3%', target: '< 5%', status: 'good', formula: '(Precio actual - Precio anterior) / Precio anterior × 100' },
            { name: 'Cumplimiento entregas proveedor', value: '88%', target: '95%', status: 'warning', formula: 'Entregas a tiempo / Total entregas × 100' },
            { name: 'Recepciones conformes', value: '96.8%', target: '98%', status: 'warning', formula: 'Recepciones aceptadas / Total recepciones × 100' },
            { name: 'Compras vs. presupuesto', value: '78%', target: '100%', status: 'good', formula: 'Total compras / Presupuesto compras × 100' },
            { name: 'Órdenes pendientes', value: '2', target: '0', status: 'warning', formula: 'COUNT(OC) WHERE status IN (sent, partial)' },
          ].map((kpi, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-gray-700">{kpi.name}</h3>
                <span className={`w-2 h-2 rounded-full ${kpi.status === 'good' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
              </div>
              <p className="text-2xl font-bold text-gray-900">{kpi.value}</p>
              <p className="text-xs text-gray-500 mt-1">Meta: {kpi.target}</p>
              <p className="text-xs text-gray-400 mt-2 italic">Fórmula: {kpi.formula}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

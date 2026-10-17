import { useState } from 'react';
import { store } from '../store';
import { Truck, Package, MapPin, Clock, CheckCircle, AlertCircle, Plus } from 'lucide-react';

type Tab = 'shipments' | 'carriers' | 'indicators';

export default function Logistics() {
  const [activeTab, setActiveTab] = useState<Tab>('shipments');
  const shipments = store.getShipmentOrders();
  const carriers = store.getCarriers();

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-gray-100 text-gray-700', reserved: 'bg-blue-100 text-blue-700',
      picking: 'bg-indigo-100 text-indigo-700', packed: 'bg-purple-100 text-purple-700',
      in_transit: 'bg-amber-100 text-amber-700', delivered: 'bg-emerald-100 text-emerald-700',
      returned: 'bg-red-100 text-red-700',
    };
    const labels: Record<string, string> = {
      pending: 'Pendiente', reserved: 'Reservado', picking: 'Picking',
      packed: 'Empacado', in_transit: 'En Tránsito', delivered: 'Entregado', returned: 'Devuelto',
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>{labels[status] || status}</span>;
  };

  const tabs = [
    { id: 'shipments' as Tab, label: 'Despachos', icon: Truck, count: shipments.length },
    { id: 'carriers' as Tab, label: 'Transportistas', icon: MapPin, count: carriers.length },
    { id: 'indicators' as Tab, label: 'Indicadores', icon: AlertCircle },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Logística y Despacho</h1>
          <p className="text-sm text-gray-500 mt-1">Preparación de pedidos, picking, packing y seguimiento de entregas</p>
        </div>
        <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> Nuevo Despacho
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center"><Package size={20} className="text-gray-600" /></div>
            <div><p className="text-2xl font-bold">{shipments.filter(s => s.status === 'pending').length}</p><p className="text-xs text-gray-500">Pendientes</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center"><Truck size={20} className="text-amber-600" /></div>
            <div><p className="text-2xl font-bold">{shipments.filter(s => s.status === 'in_transit').length}</p><p className="text-xs text-gray-500">En tránsito</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center"><CheckCircle size={20} className="text-emerald-600" /></div>
            <div><p className="text-2xl font-bold">{shipments.filter(s => s.status === 'delivered').length}</p><p className="text-xs text-gray-500">Entregados</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"><Clock size={20} className="text-blue-600" /></div>
            <div><p className="text-2xl font-bold">92%</p><p className="text-xs text-gray-500">Entregas a tiempo</p></div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors ${
                activeTab === tab.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              <tab.icon size={16} />{tab.label}
              {(tab.count ?? 0) > 0 && <span className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full text-xs">{tab.count}</span>}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'shipments' && (
        <div className="space-y-4">
          {shipments.map(ship => {
            const customer = store.getCustomer(ship.customerId);
            const carrier = ship.carrierId ? store.getCarriers().find(c => c.id === ship.carrierId) : null;
            return (
              <div key={ship.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{ship.number}</h3>
                      {getStatusBadge(ship.status)}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">Cliente: {customer?.name}</p>
                    {carrier && <p className="text-xs text-gray-500">Transportista: {carrier.name} | Tracking: {ship.trackingNumber || 'N/A'}</p>}
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500">Fecha planificada</p>
                    <p className="text-sm font-medium">{new Date(ship.plannedDate).toLocaleDateString()}</p>
                    {ship.actualDeliveryDate && <p className="text-xs text-emerald-600">Entregado: {new Date(ship.actualDeliveryDate).toLocaleDateString()}</p>}
                  </div>
                </div>
                <div className="border-t border-gray-100 pt-3">
                  <table className="w-full text-sm">
                    <thead><tr className="text-xs text-gray-500"><th className="text-left py-1">Artículo</th><th className="text-right py-1">Solicitado</th><th className="text-right py-1">Picked</th><th className="text-right py-1">Entregado</th></tr></thead>
                    <tbody>
                      {ship.items.map(item => {
                        const art = store.getArticle(item.articleId);
                        return (
                          <tr key={item.id} className="border-t border-gray-50">
                            <td className="py-1">{art?.name || 'N/A'}</td>
                            <td className="py-1 text-right">{item.requestedQuantity}</td>
                            <td className="py-1 text-right">{item.pickedQuantity}</td>
                            <td className="py-1 text-right font-medium">{item.deliveredQuantity}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {/* Progress bar */}
                <div className="mt-3">
                  <div className="flex items-center gap-1">
                    {['pending', 'reserved', 'picking', 'packed', 'in_transit', 'delivered'].map((step, i) => {
                      const steps = ['pending', 'reserved', 'picking', 'packed', 'in_transit', 'delivered'];
                      const currentIdx = steps.indexOf(ship.status);
                      const isComplete = i <= currentIdx;
                      return (
                        <div key={step} className="flex-1 flex flex-col items-center">
                          <div className={`w-full h-1.5 rounded ${isComplete ? 'bg-blue-600' : 'bg-gray-200'}`} />
                          <span className="text-[9px] text-gray-500 mt-1">{step === 'pending' ? 'Pend.' : step === 'reserved' ? 'Res.' : step === 'picking' ? 'Pick' : step === 'packed' ? 'Pack' : step === 'in_transit' ? 'Trán.' : 'Ent.'}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'carriers' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {carriers.map(carrier => (
            <div key={carrier.id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"><Truck size={20} className="text-blue-600" /></div>
                <div>
                  <h3 className="font-semibold">{carrier.name}</h3>
                  <p className="text-xs text-gray-500">{carrier.contactName} | {carrier.phone}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {carrier.coverageZones.map(zone => (
                  <span key={zone} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{zone}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'indicators' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Entregas a tiempo y completas (OTIF)', value: '92%', target: '95%', formula: 'Entregas completas a tiempo / Total × 100', status: 'warning' },
            { name: 'Tiempo pedido → despacho', value: '1.2 días', target: '< 1 día', formula: 'AVG(despacho - pedido)', status: 'warning' },
            { name: 'Tiempo total de entrega', value: '3.5 días', target: '< 3 días', formula: 'AVG(entrega - pedido)', status: 'warning' },
            { name: 'Pedidos pendientes', value: `${shipments.filter(s => s.status === 'pending').length}`, target: '0', formula: 'COUNT WHERE status = pending', status: 'warning' },
            { name: 'Costo logístico por pedido', value: '$18.50', target: '< $15', formula: 'Total costo logístico / Total pedidos', status: 'warning' },
            { name: 'Devoluciones', value: '2.1%', target: '< 2%', formula: 'Despachos devueltos / Total × 100', status: 'warning' },
          ].map((kpi, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${kpi.status === 'good' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                <h3 className="text-sm font-medium text-gray-700">{kpi.name}</h3>
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

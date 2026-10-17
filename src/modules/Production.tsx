import { useState } from 'react';
import { store } from '../store';
import { Factory, Clock, CheckCircle, AlertCircle, Plus, Play, Pause } from 'lucide-react';

type Tab = 'orders' | 'indicators';

export default function Production() {
  const [activeTab, setActiveTab] = useState<Tab>('orders');
  const workOrders = store.getWorkOrders();

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      planned: 'bg-gray-100 text-gray-700', in_progress: 'bg-blue-100 text-blue-700',
      completed: 'bg-emerald-100 text-emerald-700', cancelled: 'bg-red-100 text-red-700',
      on_hold: 'bg-amber-100 text-amber-700',
    };
    const labels: Record<string, string> = {
      planned: 'Planificada', in_progress: 'En Progreso', completed: 'Completada',
      cancelled: 'Cancelada', on_hold: 'En Pausa',
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>{labels[status] || status}</span>;
  };

  const tabs = [
    { id: 'orders' as Tab, label: 'Órdenes de Trabajo', icon: Factory, count: workOrders.length },
    { id: 'indicators' as Tab, label: 'Indicadores', icon: AlertCircle },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Operaciones y Producción</h1>
          <p className="text-sm text-gray-500 mt-1">Órdenes de trabajo, planificación y control de avances</p>
        </div>
        <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> Nueva Orden de Trabajo
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"><Factory size={20} className="text-blue-600" /></div>
            <div><p className="text-2xl font-bold">{workOrders.filter(w => w.status === 'in_progress').length}</p><p className="text-xs text-gray-500">En progreso</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center"><CheckCircle size={20} className="text-emerald-600" /></div>
            <div><p className="text-2xl font-bold">{workOrders.filter(w => w.status === 'completed').length}</p><p className="text-xs text-gray-500">Completadas</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center"><Clock size={20} className="text-gray-600" /></div>
            <div><p className="text-2xl font-bold">{workOrders.filter(w => w.status === 'planned').length}</p><p className="text-xs text-gray-500">Planificadas</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center"><CheckCircle size={20} className="text-purple-600" /></div>
            <div><p className="text-2xl font-bold">85%</p><p className="text-xs text-gray-500">Cumplimiento plan</p></div>
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

      {activeTab === 'orders' && (
        <div className="space-y-4">
          {workOrders.map(wo => {
            const product = store.getArticle(wo.productArticleId);
            const progress = wo.plannedQuantity > 0 ? (wo.completedQuantity / wo.plannedQuantity) * 100 : 0;
            return (
              <div key={wo.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-lg">{wo.number}</h3>
                      {getStatusBadge(wo.status)}
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        wo.priority === 'high' ? 'bg-red-100 text-red-700' :
                        wo.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-700'
                      }`}>{wo.priority}</span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">Producto: {product?.name} | Cantidad planificada: {wo.plannedQuantity} {product?.unit}</p>
                  </div>
                  <div className="flex gap-2">
                    {wo.status === 'planned' && <button className="p-2 bg-blue-100 text-blue-600 rounded-lg hover:bg-blue-200"><Play size={16} /></button>}
                    {wo.status === 'in_progress' && <button className="p-2 bg-amber-100 text-amber-600 rounded-lg hover:bg-amber-200"><Pause size={16} /></button>}
                  </div>
                </div>

                {/* Progress */}
                <div className="mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600">Avance</span>
                    <span className="font-medium">{wo.completedQuantity} / {wo.plannedQuantity} ({progress.toFixed(0)}%)</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div className={`h-2.5 rounded-full ${progress >= 100 ? 'bg-emerald-500' : progress > 50 ? 'bg-blue-500' : 'bg-amber-500'}`} style={{ width: `${Math.min(progress, 100)}%` }} />
                  </div>
                </div>

                {/* BOM & Dates */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1">Insumos requeridos (BOM)</p>
                    {wo.bomItems.map(bom => {
                      const art = store.getArticle(bom.articleId);
                      return (
                        <div key={bom.id} className="flex justify-between py-0.5">
                          <span className="text-gray-600">{art?.name || bom.articleId}</span>
                          <span className="font-medium">{bom.quantityRequired} {bom.unit}</span>
                        </div>
                      );
                    })}
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1">Fechas</p>
                    <p>Inicio: {new Date(wo.startDate).toLocaleDateString()}</p>
                    <p>Fin: {wo.endDate ? new Date(wo.endDate).toLocaleDateString() : 'Pendiente'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 font-medium mb-1">Información</p>
                    <p>Creado por: {store.getUser(wo.createdBy)?.fullName}</p>
                    <p>Sede: {store.getBranch(wo.branchId)?.name}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'indicators' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Cumplimiento plan operativo', value: '85%', target: '90%', formula: 'OTs completadas a tiempo / Total × 100', status: 'warning' },
            { name: 'Productividad', value: '92%', target: '95%', formula: 'Unidades producidas / Unidades planificadas × 100', status: 'warning' },
            { name: 'Tiempo de ciclo promedio', value: '12 días', target: '10 días', formula: 'AVG(fin - inicio) de OTs', status: 'warning' },
            { name: 'Costo real vs. presupuestado', value: '+5.2%', target: '< 3%', formula: '(Costo real - Costo estándar) / Costo estándar × 100', status: 'warning' },
            { name: 'Porcentaje de reproceso', value: '1.8%', target: '< 2%', formula: 'Unidades reprocesadas / Total × 100', status: 'good' },
            { name: 'Utilización de recursos', value: '78%', target: '85%', formula: 'Horas productivas / Horas disponibles × 100', status: 'warning' },
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

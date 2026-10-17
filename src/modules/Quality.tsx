import React, { useState } from 'react';
import { store } from '../store';
import { Shield, ClipboardCheck, AlertTriangle, CheckCircle, XCircle, Plus, Eye } from 'lucide-react';

type Tab = 'inspections' | 'nonconformances' | 'plans' | 'indicators';

export default function Quality() {
  const [activeTab, setActiveTab] = useState<Tab>('inspections');
  const inspections = store.getQualityInspections();
  const nonConformances = store.getNonConformances();

  const tabs = [
    { id: 'inspections' as Tab, label: 'Inspecciones', icon: ClipboardCheck, count: inspections.length },
    { id: 'nonconformances' as Tab, label: 'No Conformidades', icon: AlertTriangle, count: nonConformances.filter(nc => nc.status !== 'closed').length },
    { id: 'plans' as Tab, label: 'Planes de Inspección', icon: Shield },
    { id: 'indicators' as Tab, label: 'Indicadores', icon: CheckCircle },
  ];

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: 'bg-gray-100 text-gray-700', in_progress: 'bg-blue-100 text-blue-700',
      conforming: 'bg-emerald-100 text-emerald-700', non_conforming: 'bg-red-100 text-red-700',
      conditional: 'bg-amber-100 text-amber-700', open: 'bg-red-100 text-red-700',
      investigating: 'bg-amber-100 text-amber-700', action_planned: 'bg-blue-100 text-blue-700',
      closed: 'bg-emerald-100 text-emerald-700',
    };
    const labels: Record<string, string> = {
      pending: 'Pendiente', in_progress: 'En Progreso', conforming: 'Conforme',
      non_conforming: 'No Conforme', conditional: 'Condicional', open: 'Abierta',
      investigating: 'Investigando', action_planned: 'Acción Planificada', closed: 'Cerrada',
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>{labels[status] || status}</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Control de Calidad</h1>
          <p className="text-sm text-gray-500 mt-1">Inspecciones, no conformidades y acciones correctivas/preventivas</p>
        </div>
        <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> Nueva Inspección
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center"><CheckCircle size={20} className="text-emerald-600" /></div>
            <div><p className="text-2xl font-bold">{inspections.filter(i => i.status === 'conforming').length}</p><p className="text-xs text-gray-500">Conformes</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center"><AlertTriangle size={20} className="text-amber-600" /></div>
            <div><p className="text-2xl font-bold">{inspections.filter(i => i.status === 'conditional').length}</p><p className="text-xs text-gray-500">Condicionales</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center"><XCircle size={20} className="text-red-600" /></div>
            <div><p className="text-2xl font-bold">{nonConformances.filter(nc => nc.status !== 'closed').length}</p><p className="text-xs text-gray-500">NC Abiertas</p></div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"><Shield size={20} className="text-blue-600" /></div>
            <div><p className="text-2xl font-bold">${nonConformances.reduce((s, nc) => s + nc.cost, 0).toLocaleString()}</p><p className="text-xs text-gray-500">Costo NC total</p></div>
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

      {activeTab === 'inspections' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Número</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Tipo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Artículo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Lote</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Inspeccionado</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Conforme</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">No Conforme</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Inspector</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Fecha</th>
                </tr>
              </thead>
              <tbody>
                {inspections.map(insp => {
                  const art = store.getArticle(insp.articleId);
                  const inspector = store.getUser(insp.inspectorId);
                  return (
                    <tr key={insp.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs font-medium">{insp.number}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs ${
                          insp.type === 'reception' ? 'bg-blue-100 text-blue-700' :
                          insp.type === 'process' ? 'bg-amber-100 text-amber-700' : 'bg-purple-100 text-purple-700'
                        }`}>{insp.type === 'reception' ? 'Recepción' : insp.type === 'process' ? 'Proceso' : 'Final'}</span>
                      </td>
                      <td className="px-4 py-3">{art?.name || 'N/A'}</td>
                      <td className="px-4 py-3 font-mono text-xs">{insp.lotNumber || '—'}</td>
                      <td className="px-4 py-3 text-right">{insp.inspectedQuantity}</td>
                      <td className="px-4 py-3 text-right text-emerald-600 font-medium">{insp.conformingQuantity}</td>
                      <td className="px-4 py-3 text-right text-red-600 font-medium">{insp.nonConformingQuantity}</td>
                      <td className="px-4 py-3 text-center">{getStatusBadge(insp.status)}</td>
                      <td className="px-4 py-3">{inspector?.fullName || 'N/A'}</td>
                      <td className="px-4 py-3">{new Date(insp.inspectionDate).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'nonconformances' && (
        <div className="space-y-4">
          {nonConformances.map(nc => {
            const art = store.getArticle(nc.articleId);
            const opener = store.getUser(nc.openedBy);
            return (
              <div key={nc.id} className="bg-white rounded-xl border border-gray-200 p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{nc.number}</h3>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        nc.severity === 'critical' ? 'bg-red-100 text-red-700' :
                        nc.severity === 'major' ? 'bg-orange-100 text-orange-700' : 'bg-amber-100 text-amber-700'
                      }`}>{nc.severity}</span>
                      {getStatusBadge(nc.status)}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">{nc.description}</p>
                    <p className="text-xs text-gray-500 mt-1">Artículo: {art?.name} | Aperturada por: {opener?.fullName} el {new Date(nc.openedDate).toLocaleDateString()}</p>
                  </div>
                  <p className="text-sm font-medium text-red-600">${nc.cost.toLocaleString()}</p>
                </div>
                {(nc.rootCause || nc.correctiveAction) && (
                  <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    {nc.rootCause && <div><p className="text-xs text-gray-500 font-medium">Causa raíz:</p><p className="text-gray-700">{nc.rootCause}</p></div>}
                    {nc.correctiveAction && <div><p className="text-xs text-gray-500 font-medium">Acción correctiva:</p><p className="text-gray-700">{nc.correctiveAction}</p></div>}
                    {nc.preventiveAction && <div><p className="text-xs text-gray-500 font-medium">Acción preventiva:</p><p className="text-gray-700">{nc.preventiveAction}</p></div>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'plans' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold mb-4">Planes de Inspección Configurados</h3>
          <div className="space-y-3">
            {[
              { name: 'Inspección Recepción Materias Primas', type: 'Recepción', criteria: 4, sample: '√n + 1' },
              { name: 'Control de Proceso - Línea 1', type: 'Proceso', criteria: 3, sample: '100%' },
              { name: 'Inspección Final Producto Terminado', type: 'Final', criteria: 5, sample: 'Nivel II AQL 2.5' },
            ].map((plan, i) => (
              <div key={i} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <h4 className="font-medium text-sm">{plan.name}</h4>
                  <p className="text-xs text-gray-500">Tipo: {plan.type} | Criterios: {plan.criteria} | Muestreo: {plan.sample}</p>
                </div>
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs font-medium">Activo</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'indicators' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Tasa de no conformidad', value: '3.2%', target: '< 2%', formula: 'NC / Total inspecciones × 100', status: 'warning' },
            { name: 'Lotes rechazados', value: '1.1%', target: '< 1%', formula: 'Lotes rechazados / Total lotes × 100', status: 'warning' },
            { name: 'Tiempo resolución NC', value: '8 días', target: '< 5 días', formula: 'AVG(días apertura → cierre)', status: 'warning' },
            { name: 'Costo de reprocesos', value: '$487.50', target: '< $200', formula: 'SUM(costo NC cerradas)', status: 'critical' },
            { name: 'Cumplimiento inspecciones', value: '100%', target: '100%', formula: 'Inspecciones realizadas / Planificadas × 100', status: 'good' },
            { name: 'NC recurrentes', value: '0', target: '0', formula: 'NC con misma causa raíz > 2 veces', status: 'good' },
          ].map((kpi, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${kpi.status === 'good' ? 'bg-emerald-500' : kpi.status === 'warning' ? 'bg-amber-500' : 'bg-red-500'}`} />
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

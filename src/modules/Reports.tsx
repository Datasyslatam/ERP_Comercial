import React, { useState } from 'react';
import { store } from '../store';
import { BarChart3, Download, Filter, Calendar, FileSpreadsheet, FileText, Printer } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';

export default function Reports() {
  const [selectedReport, setSelectedReport] = useState('financial');

  const reportCategories = [
    { id: 'financial', label: 'Financieros', icon: BarChart3 },
    { id: 'purchasing', label: 'Compras', icon: FileText },
    { id: 'inventory', label: 'Inventario', icon: FileSpreadsheet },
    { id: 'production', label: 'Producción', icon: FileText },
    { id: 'quality', label: 'Calidad', icon: FileText },
    { id: 'logistics', label: 'Logística', icon: FileText },
  ];

  const monthlyData = [
    { mes: 'Jul', ingresos: 15200, gastos: 11800, utilidad: 3400 },
    { mes: 'Ago', ingresos: 18500, gastos: 13200, utilidad: 5300 },
    { mes: 'Sep', ingresos: 16800, gastos: 12500, utilidad: 4300 },
    { mes: 'Oct', ingresos: 21000, gastos: 14800, utilidad: 6200 },
    { mes: 'Nov', ingresos: 21840, gastos: 15200, utilidad: 6640 },
  ];

  const supplierPerformance = [
    { name: 'Dist. Industrial SA', entregas: 12, aTiempo: 11, calidad: 98 },
    { name: 'Tecnología y Suministros', entregas: 8, aTiempo: 7, calidad: 95 },
    { name: 'Químicos del Pacífico', entregas: 6, aTiempo: 4, calidad: 88 },
    { name: 'Embalajes Modernos', entregas: 10, aTiempo: 9, calidad: 97 },
  ];

  const inventoryAging = [
    { name: '0-30 días', value: 52000, color: '#10B981' },
    { name: '31-60 días', value: 25000, color: '#3B82F6' },
    { name: '61-90 días', value: 12000, color: '#F59E0B' },
    { name: '>90 días', value: 9000, color: '#EF4444' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reportes e Indicadores</h1>
          <p className="text-sm text-gray-500 mt-1">Analítica empresarial, reportes exportables y tendencias</p>
        </div>
        <div className="flex gap-2">
          <select className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white">
            <option>Noviembre 2024</option>
            <option>Octubre 2024</option>
            <option>Q4 2024</option>
          </select>
          <button className="flex items-center gap-2 bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 text-sm">
            <Download size={16} /> Exportar
          </button>
        </div>
      </div>

      {/* Report Categories */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {reportCategories.map(cat => (
          <button
            key={cat.id}
            onClick={() => setSelectedReport(cat.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              selectedReport === cat.id ? 'bg-blue-600 text-white' : 'bg-white border border-gray-200 text-gray-600 hover:bg-gray-50'
            }`}
          >
            <cat.icon size={16} />
            {cat.label}
          </button>
        ))}
      </div>

      {/* Financial Reports */}
      {selectedReport === 'financial' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Tendencia de Ingresos, Gastos y Utilidad</h3>
              <div className="flex gap-2">
                <button className="p-2 hover:bg-gray-100 rounded"><Printer size={16} className="text-gray-500" /></button>
                <button className="p-2 hover:bg-gray-100 rounded"><Download size={16} className="text-gray-500" /></button>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={monthlyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="mes" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                <Line type="monotone" dataKey="ingresos" stroke="#3B82F6" strokeWidth={2} name="Ingresos" dot={{ r: 4 }} />
                <Line type="monotone" dataKey="gastos" stroke="#EF4444" strokeWidth={2} name="Gastos" dot={{ r: 4 }} />
                <Line type="monotone" dataKey="utilidad" stroke="#10B981" strokeWidth={2} name="Utilidad" dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Estado de Resultados Resumido</h3>
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-gray-100"><td className="py-2 font-medium">Ingresos por Ventas</td><td className="py-2 text-right">$93,340</td></tr>
                  <tr className="border-b border-gray-100"><td className="py-2 pl-4 text-gray-600">(-) Costo de Ventas</td><td className="py-2 text-right text-red-600">($53,672)</td></tr>
                  <tr className="border-b border-gray-200 bg-blue-50"><td className="py-2 font-bold">= Utilidad Bruta</td><td className="py-2 text-right font-bold">$39,668</td></tr>
                  <tr className="border-b border-gray-100"><td className="py-2 pl-4 text-gray-600">(-) Gastos Operativos</td><td className="py-2 text-right text-red-600">($22,500)</td></tr>
                  <tr className="border-b border-gray-100"><td className="py-2 pl-4 text-gray-600">(-) Depreciación</td><td className="py-2 text-right text-red-600">($3,200)</td></tr>
                  <tr className="bg-emerald-50"><td className="py-2 font-bold">= Utilidad Neta</td><td className="py-2 text-right font-bold text-emerald-700">$13,968</td></tr>
                </tbody>
              </table>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Balance General Resumido</h3>
              <table className="w-full text-sm">
                <thead><tr className="border-b"><th className="text-left py-2 font-medium text-gray-500" colSpan={2}>ACTIVO</th></tr></thead>
                <tbody>
                  <tr className="border-b border-gray-50"><td className="py-1.5 pl-2">Activo Corriente</td><td className="py-1.5 text-right">$165,040</td></tr>
                  <tr className="border-b border-gray-50"><td className="py-1.5 pl-2">Activo No Corriente</td><td className="py-1.5 text-right">$150,000</td></tr>
                  <tr className="border-b border-gray-200 bg-blue-50"><td className="py-1.5 font-bold">Total Activo</td><td className="py-1.5 text-right font-bold">$315,040</td></tr>
                </tbody>
                <thead><tr className="border-b mt-2"><th className="text-left py-2 font-medium text-gray-500" colSpan={2}>PASIVO Y PATRIMONIO</th></tr></thead>
                <tbody>
                  <tr className="border-b border-gray-50"><td className="py-1.5 pl-2">Pasivo Corriente</td><td className="py-1.5 text-right">$9,968</td></tr>
                  <tr className="border-b border-gray-50"><td className="py-1.5 pl-2">Patrimonio</td><td className="py-1.5 text-right">$305,072</td></tr>
                  <tr className="bg-emerald-50"><td className="py-1.5 font-bold">Total Pasivo + Patrimonio</td><td className="py-1.5 text-right font-bold">$315,040</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {selectedReport === 'purchasing' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold mb-4">Desempeño de Proveedores</h3>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-2 font-medium text-gray-500">Proveedor</th>
                  <th className="text-center px-4 py-2 font-medium text-gray-500">Entregas</th>
                  <th className="text-center px-4 py-2 font-medium text-gray-500">A Tiempo</th>
                  <th className="text-center px-4 py-2 font-medium text-gray-500">% Puntualidad</th>
                  <th className="text-center px-4 py-2 font-medium text-gray-500">% Calidad</th>
                  <th className="text-center px-4 py-2 font-medium text-gray-500">Rating</th>
                </tr>
              </thead>
              <tbody>
                {supplierPerformance.map((sp, i) => (
                  <tr key={i} className="border-t border-gray-100">
                    <td className="px-4 py-3 font-medium">{sp.name}</td>
                    <td className="px-4 py-3 text-center">{sp.entregas}</td>
                    <td className="px-4 py-3 text-center">{sp.aTiempo}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-medium ${sp.aTiempo / sp.entregas >= 0.9 ? 'text-emerald-600' : 'text-amber-600'}`}>
                        {((sp.aTiempo / sp.entregas) * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`font-medium ${sp.calidad >= 95 ? 'text-emerald-600' : 'text-amber-600'}`}>{sp.calidad}%</span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center gap-0.5">
                        {[1,2,3,4,5].map(s => <div key={s} className={`w-2 h-2 rounded-full ${s <= Math.round(sp.calidad / 20) ? 'bg-amber-400' : 'bg-gray-200'}`} />)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedReport === 'inventory' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Antigüedad de Inventario</h3>
              <div className="flex items-center gap-6">
                <ResponsiveContainer width="50%" height={200}>
                  <PieChart>
                    <Pie data={inventoryAging} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                      {inventoryAging.map((entry, index) => <Cell key={index} fill={entry.color} />)}
                    </Pie>
                    <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2">
                  {inventoryAging.map(item => (
                    <div key={item.name} className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                      <span className="text-sm">{item.name}: ${item.value.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Resumen de Existencias</h3>
              <div className="space-y-3">
                {store.getArticles().slice(0, 5).map(art => {
                  const balance = store.getStockBalances().find(b => b.articleId === art.id);
                  return (
                    <div key={art.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div>
                        <p className="text-sm font-medium">{art.name}</p>
                        <p className="text-xs text-gray-500">{art.code}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold">{balance?.available || 0} {art.unit}</p>
                        <p className="text-xs text-gray-500">Mín: {art.minStock} | Máx: {art.maxStock}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {(selectedReport === 'production' || selectedReport === 'quality' || selectedReport === 'logistics') && (
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <BarChart3 size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-semibold text-gray-700">Reportes de {selectedReport === 'production' ? 'Producción' : selectedReport === 'quality' ? 'Calidad' : 'Logística'}</h3>
          <p className="text-sm text-gray-500 mt-2">Los indicadores específicos de este módulo están disponibles en la sección de indicadores del módulo correspondiente.</p>
          <p className="text-xs text-gray-400 mt-4">Para reportes personalizados, utilice el generador de reportes o exporte los datos desde el módulo.</p>
        </div>
      )}
    </div>
  );
}

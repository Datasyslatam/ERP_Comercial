import { store } from '../store';
import {
  TrendingUp, DollarSign, Package, Truck, Shield,
  AlertTriangle, CheckCircle, Clock, Users, ArrowUpRight, ArrowDownRight,
  Activity, FileText
} from 'lucide-react';

// Simple SVG Bar Chart component
function SimpleBarChart({ data, colors }: { data: { label: string; values: number[] }[]; colors: string[] }) {
  const maxVal = Math.max(...data.flatMap(d => d.values));
  const barWidth = 40;
  const gap = 20;
  const chartHeight = 180;
  const chartWidth = data.length * (barWidth * 2 + gap * 2);

  return (
    <svg viewBox={`0 0 ${chartWidth + 40} ${chartHeight + 40}`} className="w-full h-48">
      {data.map((d, i) => {
        const x = i * (barWidth * 2 + gap * 2) + 20;
        return (
          <g key={i}>
            {d.values.map((v, j) => {
              const h = (v / maxVal) * chartHeight;
              return (
                <rect
                  key={j}
                  x={x + j * barWidth}
                  y={chartHeight - h + 10}
                  width={barWidth - 4}
                  height={h}
                  fill={colors[j]}
                  rx={3}
                  opacity={0.85}
                />
              );
            })}
            <text x={x + barWidth - 2} y={chartHeight + 28} textAnchor="middle" className="text-[10px] fill-gray-500">{d.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

function SimpleLineChart({ data, lines }: { data: { label: string; values: number[] }[]; lines: { color: string; name: string }[] }) {
  const allValues = data.flatMap(d => d.values);
  const maxVal = Math.max(...allValues);
  const chartWidth = 400;
  const chartHeight = 180;
  const padding = 30;

  return (
    <svg viewBox={`0 0 ${chartWidth + padding * 2} ${chartHeight + padding * 2}`} className="w-full h-48">
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => (
        <line key={i} x1={padding} y1={padding + chartHeight * (1 - pct)} x2={chartWidth + padding} y2={padding + chartHeight * (1 - pct)} stroke="#f0f0f0" strokeWidth={1} />
      ))}
      {/* Lines */}
      {lines.map((line, li) => {
        const points = data.map((d, i) => {
          const x = padding + (i / (data.length - 1)) * chartWidth;
          const y = padding + chartHeight - (d.values[li] / maxVal) * chartHeight;
          return `${x},${y}`;
        }).join(' ');
        return (
          <g key={li}>
            <polyline points={points} fill="none" stroke={line.color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
            {data.map((d, i) => {
              const x = padding + (i / (data.length - 1)) * chartWidth;
              const y = padding + chartHeight - (d.values[li] / maxVal) * chartHeight;
              return <circle key={i} cx={x} cy={y} r={3} fill={line.color} />;
            })}
          </g>
        );
      })}
      {/* Labels */}
      {data.map((d, i) => {
        const x = padding + (i / (data.length - 1)) * chartWidth;
        return <text key={i} x={x} y={chartHeight + padding + 18} textAnchor="middle" className="text-[10px] fill-gray-500">{d.label}</text>;
      })}
    </svg>
  );
}

export default function Dashboard() {
  const kpis = store.getKPIs();
  const invoices = store.getInvoices();
  const purchaseOrders = store.getPurchaseOrders();
  const shipmentOrders = store.getShipmentOrders();
  const workOrders = store.getWorkOrders();
  const nonConformances = store.getNonConformances();
  const accountsReceivable = store.getAccountsReceivable();
  const accountsPayable = store.getAccountsPayable();
  const stockBalances = store.getStockBalances();

  const totalRevenue = invoices.filter(i => i.status === 'accepted').reduce((s, i) => s + i.total, 0);
  const totalAR = accountsReceivable.reduce((s, ar) => s + (ar.amount - ar.paidAmount), 0);
  const pendingShipments = shipmentOrders.filter(s => s.status === 'pending' || s.status === 'in_transit').length;
  const openNCs = nonConformances.filter(nc => nc.status !== 'closed').length;

  const monthlyRevenue = [
    { label: 'Jul', values: [15200, 11800] },
    { label: 'Ago', values: [18500, 13200] },
    { label: 'Sep', values: [16800, 12500] },
    { label: 'Oct', values: [21000, 14800] },
    { label: 'Nov', values: [totalRevenue, 15200] },
  ];

  const inventoryByType = [
    { name: 'Materias Primas', value: 32500, color: '#3B82F6' },
    { name: 'Productos Terminados', value: 45000, color: '#10B981' },
    { name: 'En Proceso', value: 12000, color: '#F59E0B' },
    { name: 'Suministros', value: 8500, color: '#8B5CF6' },
  ];
  const totalInv = inventoryByType.reduce((s, i) => s + i.value, 0);

  const productionData = [
    { label: 'Sem 1', values: [50, 48] },
    { label: 'Sem 2', values: [60, 55] },
    { label: 'Sem 3', values: [45, 45] },
    { label: 'Sem 4', values: [55, 50] },
  ];

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good': return 'text-emerald-600 bg-emerald-50 border-emerald-200';
      case 'warning': return 'text-amber-600 bg-amber-50 border-amber-200';
      case 'critical': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'good': return <CheckCircle size={14} />;
      case 'warning': return <Clock size={14} />;
      case 'critical': return <AlertTriangle size={14} />;
      default: return <Activity size={14} />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard Ejecutivo</h1>
          <p className="text-sm text-gray-500 mt-1">Vista consolidada de indicadores empresariales — Período: Noviembre 2024</p>
        </div>
        <div className="flex items-center gap-2">
          <select className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white">
            <option>Noviembre 2024</option>
            <option>Octubre 2024</option>
            <option>Q4 2024</option>
          </select>
          <select className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white">
            <option>Todas las sedes</option>
            <option>Casa Matriz Quito</option>
            <option>Sucursal Guayaquil</option>
          </select>
        </div>
      </div>

      {/* KPI Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center"><DollarSign size={20} className="text-blue-600" /></div>
            <span className="flex items-center text-xs text-emerald-600 font-medium"><ArrowUpRight size={14} /> 12.5%</span>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">${totalRevenue.toLocaleString()}</p>
          <p className="text-sm text-gray-500">Ingresos del período</p>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
            <div className="bg-blue-600 h-1.5 rounded-full" style={{ width: `${(totalRevenue / 62500) * 100}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-1">Meta: $62,500 ({((totalRevenue / 62500) * 100).toFixed(0)}%)</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center"><TrendingUp size={20} className="text-emerald-600" /></div>
            <span className="flex items-center text-xs text-emerald-600 font-medium"><ArrowUpRight size={14} /> 2.5%</span>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">42.5%</p>
          <p className="text-sm text-gray-500">Margen bruto</p>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
            <div className="bg-emerald-600 h-1.5 rounded-full" style={{ width: '42.5%' }} />
          </div>
          <p className="text-xs text-gray-400 mt-1">Meta: 45%</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center"><Users size={20} className="text-amber-600" /></div>
            <span className="flex items-center text-xs text-red-500 font-medium"><ArrowDownRight size={14} /> 8%</span>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">${totalAR.toLocaleString()}</p>
          <p className="text-sm text-gray-500">Cuentas por cobrar</p>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
            <div className="bg-amber-500 h-1.5 rounded-full" style={{ width: `${Math.min((totalAR / 30000) * 100, 100)}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-1">Límite alerta: $30,000</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center"><Package size={20} className="text-purple-600" /></div>
            <span className="flex items-center text-xs text-emerald-600 font-medium"><ArrowUpRight size={14} /> 5%</span>
          </div>
          <p className="mt-3 text-2xl font-bold text-gray-900">4.2x</p>
          <p className="text-sm text-gray-500">Rotación de inventarios</p>
          <div className="mt-2 w-full bg-gray-200 rounded-full h-1.5">
            <div className="bg-purple-600 h-1.5 rounded-full" style={{ width: '70%' }} />
          </div>
          <p className="text-xs text-gray-400 mt-1">Meta: 6x</p>
        </div>
      </div>

      {/* KPI Grid */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Indicadores por Módulo</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          {kpis.map(kpi => (
            <div key={kpi.id} className={`rounded-lg border p-3 ${getStatusColor(kpi.status)}`}>
              <div className="flex items-center gap-1.5 mb-1">
                {getStatusIcon(kpi.status)}
                <span className="text-xs font-medium truncate">{kpi.name}</span>
              </div>
              <p className="text-xl font-bold">{kpi.value}</p>
              <p className="text-xs opacity-75">
                {kpi.unit === 'USD' ? `$${kpi.value?.toLocaleString()}` : `${kpi.value} ${kpi.unit}`}
                {' '}| Meta: {kpi.target}{kpi.unit}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-2">Ingresos vs Gastos (5 meses)</h3>
          <div className="flex items-center gap-4 mb-2">
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-blue-500" /><span className="text-xs text-gray-500">Ingresos</span></div>
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-red-500" /><span className="text-xs text-gray-500">Gastos</span></div>
          </div>
          <SimpleLineChart data={monthlyRevenue} lines={[{ color: '#3B82F6', name: 'Ingresos' }, { color: '#EF4444', name: 'Gastos' }]} />
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Valor del Inventario por Tipo</h3>
          <div className="flex items-center gap-6">
            <svg viewBox="0 0 120 120" className="w-40 h-40">
              {(() => {
                let cumulative = 0;
                return inventoryByType.map((item, i) => {
                  const pct = item.value / totalInv;
                  const startAngle = cumulative * 2 * Math.PI - Math.PI / 2;
                  cumulative += pct;
                  const endAngle = cumulative * 2 * Math.PI - Math.PI / 2;
                  const largeArc = pct > 0.5 ? 1 : 0;
                  const x1 = 60 + 50 * Math.cos(startAngle);
                  const y1 = 60 + 50 * Math.sin(startAngle);
                  const x2 = 60 + 50 * Math.cos(endAngle);
                  const y2 = 60 + 50 * Math.sin(endAngle);
                  const ix1 = 60 + 30 * Math.cos(startAngle);
                  const iy1 = 60 + 30 * Math.sin(startAngle);
                  const ix2 = 60 + 30 * Math.cos(endAngle);
                  const iy2 = 60 + 30 * Math.sin(endAngle);
                  return (
                    <path key={i} d={`M ${x1} ${y1} A 50 50 0 ${largeArc} 1 ${x2} ${y2} L ${ix2} ${iy2} A 30 30 0 ${largeArc} 0 ${ix1} ${iy1} Z`} fill={item.color} opacity={0.85} />
                  );
                });
              })()}
            </svg>
            <div className="flex-1 space-y-2">
              {inventoryByType.map(item => (
                <div key={item.name} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="text-sm text-gray-600">{item.name}</span>
                  </div>
                  <span className="text-sm font-medium">${item.value.toLocaleString()}</span>
                </div>
              ))}
              <div className="pt-2 border-t border-gray-200 flex justify-between">
                <span className="text-sm font-semibold">Total</span>
                <span className="text-sm font-bold">${totalInv.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Second Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-2">Ejecución Presupuestaria</h3>
          <div className="flex items-center gap-4 mb-2">
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-gray-300" /><span className="text-xs text-gray-500">Presupuesto</span></div>
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-blue-500" /><span className="text-xs text-gray-500">Ejecutado</span></div>
          </div>
          <SimpleBarChart
            data={[
              { label: 'Ventas', values: [62500, 48750] },
              { label: 'Compras', values: [30000, 23400] },
              { label: 'Gastos Op.', values: [20000, 15600] },
            ]}
            colors={['#CBD5E1', '#3B82F6']}
          />
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-2">Producción: Plan vs Real</h3>
          <div className="flex items-center gap-4 mb-2">
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-gray-300" /><span className="text-xs text-gray-500">Planificado</span></div>
            <div className="flex items-center gap-1"><div className="w-3 h-3 rounded bg-emerald-500" /><span className="text-xs text-gray-500">Producido</span></div>
          </div>
          <SimpleBarChart data={productionData} colors={['#CBD5E1', '#10B981']} />
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Resumen Operativo</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
              <div className="flex items-center gap-2"><FileText size={16} className="text-blue-600" /><span className="text-sm">Órdenes de compra activas</span></div>
              <span className="font-bold text-blue-600">{purchaseOrders.filter(po => po.status !== 'cancelled').length}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-emerald-50 rounded-lg">
              <div className="flex items-center gap-2"><Truck size={16} className="text-emerald-600" /><span className="text-sm">Despachos en tránsito</span></div>
              <span className="font-bold text-emerald-600">{pendingShipments}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-purple-50 rounded-lg">
              <div className="flex items-center gap-2"><Package size={16} className="text-purple-600" /><span className="text-sm">Órdenes de trabajo activas</span></div>
              <span className="font-bold text-purple-600">{workOrders.filter(wo => wo.status === 'in_progress').length}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-amber-50 rounded-lg">
              <div className="flex items-center gap-2"><Shield size={16} className="text-amber-600" /><span className="text-sm">No conformidades abiertas</span></div>
              <span className="font-bold text-amber-600">{openNCs}</span>
            </div>
            <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
              <div className="flex items-center gap-2"><AlertTriangle size={16} className="text-red-600" /><span className="text-sm">Stock bajo mínimo</span></div>
              <span className="font-bold text-red-600">{stockBalances.filter(b => { const a = store.getArticle(b.articleId); return a && b.available <= a.reorderPoint; }).length}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Accounts Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Cuentas por Cobrar</h3>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-200"><th className="text-left py-2 text-gray-500 font-medium">Cliente</th><th className="text-right py-2 text-gray-500 font-medium">Monto</th><th className="text-right py-2 text-gray-500 font-medium">Vence</th><th className="text-center py-2 text-gray-500 font-medium">Estado</th></tr></thead>
            <tbody>
              {accountsReceivable.map(ar => {
                const customer = store.getCustomer(ar.customerId);
                const isOverdue = new Date(ar.dueDate) < new Date();
                return (
                  <tr key={ar.id} className="border-b border-gray-50">
                    <td className="py-2">{customer?.name || 'N/A'}</td>
                    <td className="py-2 text-right font-medium">${ar.amount.toLocaleString()}</td>
                    <td className="py-2 text-right">{new Date(ar.dueDate).toLocaleDateString()}</td>
                    <td className="py-2 text-center">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${isOverdue ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                        {isOverdue ? 'Vencida' : 'Al día'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Cuentas por Pagar</h3>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-200"><th className="text-left py-2 text-gray-500 font-medium">Proveedor</th><th className="text-right py-2 text-gray-500 font-medium">Monto</th><th className="text-right py-2 text-gray-500 font-medium">Vence</th><th className="text-center py-2 text-gray-500 font-medium">Estado</th></tr></thead>
            <tbody>
              {accountsPayable.map(ap => {
                const supplier = store.getSupplier(ap.supplierId);
                return (
                  <tr key={ap.id} className="border-b border-gray-50">
                    <td className="py-2">{supplier?.name || 'N/A'}</td>
                    <td className="py-2 text-right font-medium">${ap.amount.toLocaleString()}</td>
                    <td className="py-2 text-right">{new Date(ap.dueDate).toLocaleDateString()}</td>
                    <td className="py-2 text-center">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${ap.status === 'paid' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                        {ap.status === 'paid' ? 'Pagada' : 'Pendiente'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

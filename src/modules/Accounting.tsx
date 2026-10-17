import React, { useState } from 'react';
import { store } from '../store';
import { Calculator, BookOpen, FileText, DollarSign, Building2, TrendingUp, Plus } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

type Tab = 'entries' | 'chart' | 'periods' | 'receivable' | 'payable' | 'reports';

export default function Accounting() {
  const [activeTab, setActiveTab] = useState<Tab>('entries');
  const journalEntries = store.getJournalEntries();
  const chartOfAccounts = store.getChartOfAccounts();
  const periods = store.getAccountingPeriods();
  const costCenters = store.getCostCenters();
  const ar = store.getAccountsReceivable();
  const ap = store.getAccountsPayable();

  const totalDebits = journalEntries.filter(je => je.status === 'posted').reduce((s, je) => s + je.lines.reduce((ls, l) => ls + l.debit, 0), 0);
  const totalCredits = journalEntries.filter(je => je.status === 'posted').reduce((s, je) => s + je.lines.reduce((ls, l) => ls + l.credit, 0), 0);

  const incomeData = [
    { mes: 'Jul', ingresos: 15200, gastos: 11800 },
    { mes: 'Ago', ingresos: 18500, gastos: 13200 },
    { mes: 'Sep', ingresos: 16800, gastos: 12500 },
    { mes: 'Oct', ingresos: 21000, gastos: 14800 },
    { mes: 'Nov', ingresos: 21840, gastos: 15200 },
  ];

  const tabs = [
    { id: 'entries' as Tab, label: 'Asientos Contables', icon: BookOpen },
    { id: 'chart' as Tab, label: 'Plan de Cuentas', icon: Calculator },
    { id: 'periods' as Tab, label: 'Períodos', icon: FileText },
    { id: 'receivable' as Tab, label: 'CxC', icon: DollarSign },
    { id: 'payable' as Tab, label: 'CxP', icon: Building2 },
    { id: 'reports' as Tab, label: 'Estados Financieros', icon: TrendingUp },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Contabilidad y Finanzas</h1>
          <p className="text-sm text-gray-500 mt-1">Partida doble • Trazabilidad completa • Periodos controlados</p>
        </div>
        <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> Nuevo Asiento
        </button>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500">Total Débitos (Período)</p>
          <p className="text-xl font-bold text-gray-900 mt-1">${totalDebits.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500">Total Créditos (Período)</p>
          <p className="text-xl font-bold text-gray-900 mt-1">${totalCredits.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500">Balance Verificación</p>
          <p className={`text-xl font-bold mt-1 ${totalDebits === totalCredits ? 'text-emerald-600' : 'text-red-600'}`}>
            {totalDebits === totalCredits ? '✓ Cuadrado' : '✗ Descuadre'}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500">Período Activo</p>
          <p className="text-xl font-bold text-gray-900 mt-1">Noviembre 2024</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4 overflow-x-auto">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors whitespace-nowrap ${
                activeTab === tab.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'entries' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Número</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Fecha</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Referencia</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Descripción</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Débito</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Crédito</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                </tr>
              </thead>
              <tbody>
                {journalEntries.map(je => {
                  const totalDebit = je.lines.reduce((s, l) => s + l.debit, 0);
                  const totalCredit = je.lines.reduce((s, l) => s + l.credit, 0);
                  return (
                    <React.Fragment key={je.id}>
                      <tr className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-3 font-mono text-xs font-medium">{je.number}</td>
                        <td className="px-4 py-3">{new Date(je.date).toLocaleDateString()}</td>
                        <td className="px-4 py-3 font-mono text-xs">{je.reference}</td>
                        <td className="px-4 py-3">{je.description}</td>
                        <td className="px-4 py-3 text-right font-medium">${totalDebit.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right font-medium">${totalCredit.toLocaleString()}</td>
                        <td className="px-4 py-3 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            je.status === 'posted' ? 'bg-emerald-100 text-emerald-700' :
                            je.status === 'draft' ? 'bg-gray-100 text-gray-700' : 'bg-red-100 text-red-700'
                          }`}>
                            {je.status === 'posted' ? 'Contabilizado' : je.status === 'draft' ? 'Borrador' : 'Reversado'}
                          </span>
                        </td>
                      </tr>
                      {je.lines.map(line => {
                        const account = chartOfAccounts.find(a => a.id === line.accountId);
                        return (
                          <tr key={line.id} className="bg-gray-50/50">
                            <td className="px-4 py-1.5"></td>
                            <td className="px-4 py-1.5 text-xs text-gray-500" colSpan={2}>{account?.code} - {account?.name}</td>
                            <td className="px-4 py-1.5 text-xs text-gray-600">{line.description}</td>
                            <td className="px-4 py-1.5 text-right text-xs">{line.debit > 0 ? `$${line.debit.toLocaleString()}` : ''}</td>
                            <td className="px-4 py-1.5 text-right text-xs">{line.credit > 0 ? `$${line.credit.toLocaleString()}` : ''}</td>
                            <td></td>
                          </tr>
                        );
                      })}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'chart' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Código</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Nombre</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Tipo</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Nivel</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Permite Movimiento</th>
              </tr>
            </thead>
            <tbody>
              {chartOfAccounts.map(account => (
                <tr key={account.id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs font-medium" style={{ paddingLeft: `${(account.level - 1) * 16 + 16}px` }}>
                    {account.code}
                  </td>
                  <td className="px-4 py-3">{account.name}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${
                      account.type === 'asset' ? 'bg-blue-100 text-blue-700' :
                      account.type === 'liability' ? 'bg-red-100 text-red-700' :
                      account.type === 'equity' ? 'bg-purple-100 text-purple-700' :
                      account.type === 'income' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {account.type === 'asset' ? 'Activo' : account.type === 'liability' ? 'Pasivo' : account.type === 'equity' ? 'Patrimonio' : account.type === 'income' ? 'Ingreso' : 'Gasto'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">{account.level}</td>
                  <td className="px-4 py-3 text-center">
                    {account.allowsMovement ? <span className="text-emerald-600">✓</span> : <span className="text-gray-400">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'periods' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {periods.map(p => (
            <div key={p.id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold">{p.year} - Mes {p.month}</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  p.status === 'open' ? 'bg-emerald-100 text-emerald-700' :
                  p.status === 'closed' ? 'bg-gray-100 text-gray-700' : 'bg-red-100 text-red-700'
                }`}>
                  {p.status === 'open' ? 'Abierto' : p.status === 'closed' ? 'Cerrado' : 'Bloqueado'}
                </span>
              </div>
              {p.closedBy && (
                <p className="text-xs text-gray-500">Cerrado por: {store.getUser(p.closedBy)?.fullName} el {new Date(p.closedAt!).toLocaleDateString()}</p>
              )}
              <div className="mt-3 flex gap-2">
                {p.status === 'open' && <button className="text-xs bg-amber-100 text-amber-700 px-3 py-1 rounded-lg hover:bg-amber-200">Cerrar Período</button>}
                <button className="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded-lg hover:bg-gray-200">Ver Movimientos</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'receivable' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold">Cuentas por Cobrar</h2>
            <p className="text-sm text-gray-500">Total pendiente: ${ar.reduce((s, a) => s + (a.amount - a.paidAmount), 0).toLocaleString()}</p>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Cliente</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Factura</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Monto</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Pagado</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Pendiente</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Vence</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
              </tr>
            </thead>
            <tbody>
              {ar.map(item => {
                const customer = store.getCustomer(item.customerId);
                const isOverdue = new Date(item.dueDate) < new Date();
                return (
                  <tr key={item.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3">{customer?.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{item.invoiceId}</td>
                    <td className="px-4 py-3 text-right">${item.amount.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">${item.paidAmount.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right font-medium">${(item.amount - item.paidAmount).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">{new Date(item.dueDate).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${isOverdue ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        {isOverdue ? 'Vencida' : 'Al día'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'payable' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100">
            <h2 className="font-semibold">Cuentas por Pagar</h2>
            <p className="text-sm text-gray-500">Total pendiente: ${ap.reduce((s, a) => s + (a.amount - a.paidAmount), 0).toLocaleString()}</p>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Proveedor</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Documento</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Monto</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Pagado</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Pendiente</th>
                <th className="text-right px-4 py-3 font-medium text-gray-500">Vence</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
              </tr>
            </thead>
            <tbody>
              {ap.map(item => {
                const supplier = store.getSupplier(item.supplierId);
                return (
                  <tr key={item.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3">{supplier?.name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{item.invoiceId}</td>
                    <td className="px-4 py-3 text-right">${item.amount.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">${item.paidAmount.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right font-medium">${(item.amount - item.paidAmount).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">{new Date(item.dueDate).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        item.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {item.status === 'paid' ? 'Pagada' : 'Pendiente'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'reports' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold mb-4">Estado de Resultados (Acumulado)</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={incomeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="mes" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(v: number) => `$${v.toLocaleString()}`} />
                <Bar dataKey="ingresos" fill="#3B82F6" name="Ingresos" radius={[4, 4, 0, 0]} />
                <Bar dataKey="gastos" fill="#EF4444" name="Gastos" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Balance de Comprobación</h3>
              <table className="w-full text-sm">
                <thead><tr className="border-b"><th className="text-left py-2">Cuenta</th><th className="text-right py-2">Débito</th><th className="text-right py-2">Crédito</th></tr></thead>
                <tbody>
                  <tr className="border-b border-gray-50"><td className="py-2">Caja y Bancos</td><td className="text-right">$45,200</td><td className="text-right"></td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Cuentas por Cobrar</td><td className="text-right">$21,840</td><td className="text-right"></td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Inventarios</td><td className="text-right">$98,000</td><td className="text-right"></td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Propiedad Planta y Equipo</td><td className="text-right">$150,000</td><td className="text-right"></td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Cuentas por Pagar</td><td className="text-right"></td><td className="text-right">$9,968</td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Capital Social</td><td className="text-right"></td><td className="text-right">$200,000</td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Ingresos por Ventas</td><td className="text-right"></td><td className="text-right">$93,380</td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Costo de Ventas</td><td className="text-right">$53,672</td><td className="text-right"></td></tr>
                  <tr className="border-b border-gray-50"><td className="py-2">Gastos Operativos</td><td className="text-right">$34,636</td><td className="text-right"></td></tr>
                  <tr className="font-bold"><td className="py-2">TOTALES</td><td className="text-right">$303,348</td><td className="text-right">$303,348</td></tr>
                </tbody>
              </table>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Centros de Costo</h3>
              <div className="space-y-3">
                {costCenters.map(cc => (
                  <div key={cc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="text-sm font-medium">{cc.name}</p>
                      <p className="text-xs text-gray-500">{cc.code}</p>
                    </div>
                    <span className="text-sm font-medium text-gray-700">${(Math.random() * 20000 + 5000).toFixed(0)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

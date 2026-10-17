import { useState } from 'react';
import { store } from '../store';
import { FileText, Send, CheckCircle, XCircle, Clock, AlertCircle, Plus, Eye, Printer } from 'lucide-react';

type Tab = 'invoices' | 'create' | 'adapter' | 'indicators';

export default function Invoicing() {
  const [activeTab, setActiveTab] = useState<Tab>('invoices');
  const invoices = store.getInvoices();
  const customers = store.getCustomers();

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-700',
      pending_send: 'bg-amber-100 text-amber-700',
      sent: 'bg-blue-100 text-blue-700',
      accepted: 'bg-emerald-100 text-emerald-700',
      rejected: 'bg-red-100 text-red-700',
      error: 'bg-red-100 text-red-700',
      cancelled: 'bg-gray-100 text-gray-500',
    };
    const labels: Record<string, string> = {
      draft: 'Borrador', pending_send: 'Pendiente Envío', sent: 'Enviado',
      accepted: 'Autorizado', rejected: 'Rechazado', error: 'Error', cancelled: 'Anulado',
    };
    return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100'}`}>{labels[status] || status}</span>;
  };

  const tabs = [
    { id: 'invoices' as Tab, label: 'Facturas Emitidas', icon: FileText },
    { id: 'create' as Tab, label: 'Nueva Factura', icon: Plus },
    { id: 'adapter' as Tab, label: 'Adaptador SRI', icon: Send },
    { id: 'indicators' as Tab, label: 'Indicadores', icon: AlertCircle },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Facturación Electrónica</h1>
          <p className="text-sm text-gray-500 mt-1">Emisión, validación y seguimiento de documentos electrónicos</p>
        </div>
        <button onClick={() => setActiveTab('create')} className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> Nueva Factura
        </button>
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
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'invoices' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <div className="flex gap-2">
              <select className="text-sm border border-gray-300 rounded-lg px-3 py-1.5">
                <option>Todos los estados</option>
                <option>Borrador</option>
                <option>Autorizado</option>
                <option>Rechazado</option>
              </select>
              <select className="text-sm border border-gray-300 rounded-lg px-3 py-1.5">
                <option>Todos los clientes</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Número</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Cliente</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Fecha Emisión</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-500">Vence</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Subtotal</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">IVA</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-500">Total</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Estado SRI</th>
                  <th className="text-center px-4 py-3 font-medium text-gray-500">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map(inv => {
                  const customer = store.getCustomer(inv.customerId);
                  return (
                    <tr key={inv.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono text-xs font-medium">{inv.number}</td>
                      <td className="px-4 py-3">{customer?.name}</td>
                      <td className="px-4 py-3">{new Date(inv.issueDate).toLocaleDateString()}</td>
                      <td className="px-4 py-3">{new Date(inv.dueDate).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-right">${inv.subtotal.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right">${inv.taxAmount.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right font-bold">${inv.total.toLocaleString()}</td>
                      <td className="px-4 py-3 text-center">{getStatusBadge(inv.status)}</td>
                      <td className="px-4 py-3 text-center">
                        {inv.electronicStatus ? (
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            inv.electronicStatus === 'AUTORIZADO' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
                          }`}>{inv.electronicStatus}</span>
                        ) : <span className="text-gray-400 text-xs">—</span>}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <button className="p-1 text-blue-600 hover:bg-blue-50 rounded"><Eye size={14} /></button>
                          <button className="p-1 text-gray-600 hover:bg-gray-50 rounded"><Printer size={14} /></button>
                          {inv.status === 'draft' && <button className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"><Send size={14} /></button>}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'create' && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold mb-6">Crear Nueva Factura Electrónica</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Cliente</label>
              <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option value="">Seleccionar cliente...</option>
                {customers.filter(c => c.active).map(c => <option key={c.id} value={c.id}>{c.name} ({c.taxId})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Fecha de Emisión</label>
              <input type="date" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" defaultValue="2024-11-26" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Forma de Pago</label>
              <select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                <option>Efectivo</option>
                <option>Transferencia</option>
                <option>Crédito</option>
                <option>Cheque</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Plazo (días)</label>
              <input type="number" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" defaultValue="0" />
            </div>
          </div>

          <div className="mt-6">
            <h3 className="text-sm font-semibold mb-3">Detalle de Productos/Servicios</h3>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Artículo</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-500">Descripción</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500">Cantidad</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500">P. Unitario</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500">Descuento</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500">IVA</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-500">Total</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-gray-100">
                  <td className="px-3 py-2">
                    <select className="border border-gray-300 rounded px-2 py-1 text-xs w-full">
                      <option>PT-001 - Producto Terminado Alfa</option>
                      <option>PT-002 - Producto Terminado Beta</option>
                    </select>
                  </td>
                  <td className="px-3 py-2"><input type="text" className="border border-gray-300 rounded px-2 py-1 text-xs w-full" defaultValue="Producto Terminado Alfa" /></td>
                  <td className="px-3 py-2"><input type="number" className="border border-gray-300 rounded px-2 py-1 text-xs w-16 text-right" defaultValue="10" /></td>
                  <td className="px-3 py-2"><input type="number" className="border border-gray-300 rounded px-2 py-1 text-xs w-20 text-right" defaultValue="180.00" /></td>
                  <td className="px-3 py-2"><input type="number" className="border border-gray-300 rounded px-2 py-1 text-xs w-16 text-right" defaultValue="0" /></td>
                  <td className="px-3 py-2 text-right text-xs">12%</td>
                  <td className="px-3 py-2 text-right font-medium text-xs">$2,016.00</td>
                </tr>
              </tbody>
            </table>
            <button className="mt-2 text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1">
              <Plus size={14} /> Agregar línea
            </button>
          </div>

          <div className="mt-6 flex justify-end">
            <div className="w-64 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-gray-500">Subtotal:</span><span>$1,800.00</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Descuento:</span><span>$0.00</span></div>
              <div className="flex justify-between"><span className="text-gray-500">IVA 12%:</span><span>$216.00</span></div>
              <div className="flex justify-between font-bold text-lg border-t pt-2"><span>Total:</span><span>$2,016.00</span></div>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button className="px-4 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">Guardar Borrador</button>
            <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 flex items-center gap-2">
              <Send size={14} /> Emitir y Enviar al SRI
            </button>
          </div>
        </div>
      )}

      {activeTab === 'adapter' && (
        <div className="space-y-6">
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="text-amber-600 mt-0.5" />
              <div>
                <h3 className="font-semibold text-amber-800">Adaptador de Facturación Electrónica — ENTORNO DE PRUEBAS</h3>
                <p className="text-sm text-amber-700 mt-1">
                  Este módulo implementa una interfaz intercambiable para integración con proveedores tecnológicos de facturación electrónica.
                  Actualmente configurado con un <strong>adaptador de pruebas (mock)</strong> claramente identificado.
                  No emite documentos legalmente válidos. Para producción, configurar las credenciales del proveedor tecnológico autorizado.
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Configuración del Adaptador</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm">Proveedor tecnológico:</span>
                  <span className="text-sm font-medium text-amber-600">Mock Adapter (Pruebas)</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm">Ambiente:</span>
                  <span className="text-sm font-medium text-amber-600">⚠ Pruebas (no producción)</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm">País:</span>
                  <span className="text-sm font-medium">Ecuador</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm">Autoridad tributaria:</span>
                  <span className="text-sm font-medium">SRI (Servicio de Rentas Internas)</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm">Última comunicación:</span>
                  <span className="text-sm font-medium text-emerald-600">OK — 2024-11-26 10:30</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                  <span className="text-sm">Documentos procesados:</span>
                  <span className="text-sm font-medium">2 autorizados, 0 rechazados</span>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold mb-4">Estados del Documento Electrónico</h3>
              <div className="space-y-2">
                {[
                  { state: 'Borrador', desc: 'Documento creado, no enviado', color: 'bg-gray-200' },
                  { state: 'Pendiente de envío', desc: 'Validado localmente, listo para transmitir', color: 'bg-amber-200' },
                  { state: 'Enviado', desc: 'Transmitido al proveedor tecnológico', color: 'bg-blue-200' },
                  { state: 'Autorizado', desc: 'Aceptado por la autoridad tributaria', color: 'bg-emerald-200' },
                  { state: 'Rechazado', desc: 'Rechazado con errores de validación', color: 'bg-red-200' },
                  { state: 'Error', desc: 'Fallo en comunicación o proceso', color: 'bg-orange-200' },
                ].map(s => (
                  <div key={s.state} className="flex items-center gap-3 p-2 rounded">
                    <div className={`w-3 h-3 rounded-full ${s.color}`} />
                    <div>
                      <p className="text-sm font-medium">{s.state}</p>
                      <p className="text-xs text-gray-500">{s.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold mb-4">Requisitos para Producción</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="space-y-2">
                <p className="font-medium text-gray-700">Información requerida:</p>
                <ul className="space-y-1 text-gray-600">
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Definir proveedor tecnológico de F.E.</li>
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Credenciales del SRI (certificado digital)</li>
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Numeración autorizada vigente</li>
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Ambiente de producción del SRI</li>
                </ul>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-gray-700">Configuración pendiente:</p>
                <ul className="space-y-1 text-gray-600">
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> URL del Web Service del proveedor</li>
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Token/API Key de autenticación</li>
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Mapeo de impuestos y códigos</li>
                  <li className="flex items-center gap-2"><XCircle size={12} className="text-red-500" /> Pruebas de integración validadas</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'indicators' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Facturas emitidas (mes)', value: '3', formula: 'COUNT(facturas) WHERE mes actual' },
            { name: 'Tasa de autorización', value: '100%', target: '> 98%', formula: 'Autorizadas / Enviadas × 100' },
            { name: 'Tiempo promedio autorización', value: '2.3 seg', target: '< 10 seg', formula: 'AVG(tiempo respuesta SRI)' },
            { name: 'Valor facturado (mes)', value: '$22,932', formula: 'SUM(total) WHERE status = accepted' },
            { name: 'Notas de crédito emitidas', value: '0', formula: 'COUNT(créditos) WHERE mes actual' },
            { name: 'Documentos en error', value: '0', formula: 'COUNT WHERE status = error' },
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

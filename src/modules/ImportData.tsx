import React, { useState } from 'react';
import { Database, Upload, FileSpreadsheet, CheckCircle, XCircle, AlertCircle, Download } from 'lucide-react';

export default function ImportData() {
  const [selectedModule, setSelectedModule] = useState('');
  const [importStatus, setImportStatus] = useState<'idle' | 'validating' | 'importing' | 'completed'>('idle');

  const modules = [
    { id: 'customers', label: 'Clientes', fields: ['nombre', 'ruc', 'email', 'teléfono', 'dirección', 'tipo', 'régimen'] },
    { id: 'suppliers', label: 'Proveedores', fields: ['nombre', 'ruc', 'contacto', 'email', 'teléfono', 'categoría', 'plazo_pago'] },
    { id: 'articles', label: 'Artículos', fields: ['código', 'nombre', 'descripción', 'categoría', 'tipo', 'unidad', 'costo', 'stock_mín', 'stock_máx'] },
    { id: 'inventory', label: 'Saldos de Inventario', fields: ['código_artículo', 'bodega', 'cantidad', 'lote', 'costo_unitario', 'fecha_vencimiento'] },
    { id: 'chart_of_accounts', label: 'Plan de Cuentas', fields: ['código', 'nombre', 'tipo', 'nivel', 'padre', 'permite_movimiento'] },
    { id: 'opening_balances', label: 'Saldos Iniciales', fields: ['código_cuenta', 'débito', 'crédito', 'fecha_corte'] },
    { id: 'budgets', label: 'Presupuestos', fields: ['nombre', 'año', 'período', 'cuenta', 'centro_costo', 'monto'] },
  ];

  const importHistory = [
    { id: 'imp-001', fileName: 'clientes_noviembre.xlsx', module: 'Clientes', total: 150, accepted: 148, rejected: 2, date: '2024-11-20', user: 'admin' },
    { id: 'imp-002', fileName: 'saldos_inventario.csv', module: 'Inventario', total: 320, accepted: 320, rejected: 0, date: '2024-11-15', user: 'amartinez' },
    { id: 'imp-003', fileName: 'plan_cuentas_2024.xlsx', module: 'Plan de Cuentas', total: 85, accepted: 85, rejected: 0, date: '2024-10-01', user: 'llopez' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Importación de Datos</h1>
        <p className="text-sm text-gray-500 mt-1">Carga masiva de información desde archivos Excel/CSV con validación y conciliación</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Import Panel */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold mb-4">Nueva Importación</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Módulo destino</label>
                <select value={selectedModule} onChange={e => setSelectedModule(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
                  <option value="">Seleccionar módulo...</option>
                  {modules.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </div>

              {selectedModule && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Campos esperados</label>
                    <div className="flex flex-wrap gap-1">
                      {modules.find(m => m.id === selectedModule)?.fields.map(f => (
                        <span key={f} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{f}</span>
                      ))}
                    </div>
                  </div>

                  <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors cursor-pointer">
                    <Upload size={32} className="mx-auto text-gray-400 mb-3" />
                    <p className="text-sm text-gray-600">Arrastra tu archivo aquí o <span className="text-blue-600 font-medium">haz clic para seleccionar</span></p>
                    <p className="text-xs text-gray-400 mt-1">Formatos aceptados: .xlsx, .xls, .csv — Máximo 10MB</p>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setImportStatus('validating')}
                      disabled={!selectedModule}
                      className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                    >
                      <CheckCircle size={16} /> Validar Archivo
                    </button>
                    <button className="flex items-center gap-2 border border-gray-300 px-4 py-2 rounded-lg text-sm hover:bg-gray-50">
                      <Download size={16} /> Descargar Plantilla
                    </button>
                  </div>

                  {importStatus !== 'idle' && (
                    <div className={`p-4 rounded-lg ${importStatus === 'completed' ? 'bg-emerald-50 border border-emerald-200' : 'bg-blue-50 border border-blue-200'}`}>
                      {importStatus === 'validating' && (
                        <div className="flex items-center gap-3">
                          <div className="animate-spin w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full" />
                          <p className="text-sm text-blue-700">Validando archivo... Verificando formatos, referencias y duplicados.</p>
                        </div>
                      )}
                      {importStatus === 'importing' && (
                        <div className="flex items-center gap-3">
                          <div className="animate-spin w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full" />
                          <p className="text-sm text-blue-700">Importando registros...</p>
                        </div>
                      )}
                      {importStatus === 'completed' && (
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <CheckCircle size={18} className="text-emerald-600" />
                            <p className="text-sm font-medium text-emerald-700">Importación completada</p>
                          </div>
                          <div className="grid grid-cols-3 gap-3 mt-3">
                            <div className="text-center p-2 bg-white rounded">
                              <p className="text-lg font-bold text-gray-900">148</p>
                              <p className="text-xs text-gray-500">Aceptadas</p>
                            </div>
                            <div className="text-center p-2 bg-white rounded">
                              <p className="text-lg font-bold text-red-600">2</p>
                              <p className="text-xs text-gray-500">Rechazadas</p>
                            </div>
                            <div className="text-center p-2 bg-white rounded">
                              <p className="text-lg font-bold text-gray-900">150</p>
                              <p className="text-xs text-gray-500">Total</p>
                            </div>
                          </div>
                          <p className="text-xs text-gray-500 mt-2">Importado por: admin | Fecha: {new Date().toLocaleString()}</p>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Validation Rules */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-semibold mb-4">Reglas de Validación Aplicadas</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                'Formato de campos (texto, número, fecha)',
                'Longitud máxima de campos',
                'Valores únicos (detección de duplicados)',
                'Referencias a maestros existentes',
                'Rangos válidos y valores permitidos',
                'Campos obligatorios no vacíos',
                'Validación de RUC/cédula según país',
                'Consistencia entre campos relacionados',
              ].map((rule, i) => (
                <div key={i} className="flex items-center gap-2 p-2 bg-gray-50 rounded">
                  <CheckCircle size={14} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-sm text-gray-700">{rule}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* History */}
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold mb-4">Historial de Importaciones</h3>
            <div className="space-y-3">
              {importHistory.map(imp => (
                <div key={imp.id} className="p-3 border border-gray-100 rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-sm font-medium">{imp.fileName}</p>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${imp.rejected > 0 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                      {imp.rejected > 0 ? 'Con errores' : 'OK'}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">{imp.module} | {imp.total} registros</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-emerald-600">✓ {imp.accepted}</span>
                    {imp.rejected > 0 && <span className="text-xs text-red-600">✗ {imp.rejected}</span>}
                    <span className="text-xs text-gray-400 ml-auto">{imp.date}</span>
                  </div>
                  <p className="text-xs text-gray-400">Por: {imp.user}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <div className="flex items-start gap-2">
              <AlertCircle size={16} className="text-amber-600 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-800">Nota sobre saldos iniciales</p>
                <p className="text-xs text-amber-700 mt-1">
                  Los saldos iniciales no se cargan como movimientos ordinarios. Requieren documentar fecha de corte, 
                  responsable de aprobación y origen de los datos. Se registran en un asiento especial de apertura.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

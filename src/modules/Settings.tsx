import React from 'react';
import { store } from '../store';
import { Settings as SettingsIcon, Building2, MapPin, DollarSign, Database, RefreshCw, AlertTriangle } from 'lucide-react';

export default function Settings() {
  const company = store.getCompany();
  const branches = store.getBranches();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Configuración del Sistema</h1>
        <p className="text-sm text-gray-500 mt-1">Parámetros generales de la empresa, sedes y sistema</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Company Info */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold mb-4 flex items-center gap-2"><Building2 size={18} /> Datos de la Empresa</h2>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-gray-500">Razón Social</label><input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1" defaultValue={company.name} /></div>
              <div><label className="text-xs text-gray-500">RUC / ID Tributario</label><input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1" defaultValue={company.taxId} /></div>
              <div><label className="text-xs text-gray-500">País</label><select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1"><option>Ecuador</option><option>Colombia</option><option>Perú</option></select></div>
              <div><label className="text-xs text-gray-500">Moneda</label><select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1"><option>USD - Dólar</option><option>EUR - Euro</option></select></div>
              <div><label className="text-xs text-gray-500">Régimen Fiscal</label><select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1"><option>General</option><option>RIMPE</option><option>Especial</option></select></div>
              <div><label className="text-xs text-gray-500">IVA</label><select className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1"><option>12%</option><option>15%</option><option>0%</option></select></div>
            </div>
            <div><label className="text-xs text-gray-500">Dirección</label><input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1" defaultValue={company.address} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-xs text-gray-500">Teléfono</label><input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1" defaultValue={company.phone} /></div>
              <div><label className="text-xs text-gray-500">Email</label><input type="text" className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mt-1" defaultValue={company.email} /></div>
            </div>
            <button className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 mt-2">Guardar Cambios</button>
          </div>
        </div>

        {/* Branches */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold mb-4 flex items-center gap-2"><MapPin size={18} /> Sedes / Sucursales</h2>
          <div className="space-y-3">
            {branches.map(branch => (
              <div key={branch.id} className="p-3 border border-gray-200 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">{branch.name}</p>
                    <p className="text-xs text-gray-500">Código: {branch.code} | {branch.address}</p>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${branch.active ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-700'}`}>
                    {branch.active ? 'Activa' : 'Inactiva'}
                  </span>
                </div>
              </div>
            ))}
            <button className="w-full border-2 border-dashed border-gray-300 rounded-lg p-3 text-sm text-gray-500 hover:border-blue-400 hover:text-blue-600">+ Agregar sede</button>
          </div>
        </div>

        {/* System Parameters */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold mb-4 flex items-center gap-2"><SettingsIcon size={18} /> Parámetros del Sistema</h2>
          <div className="space-y-3">
            {[
              { label: 'Permitir inventario negativo', value: false, desc: 'Si está activo, permite existencias negativas bajo política autorizada' },
              { label: 'Aprobación de compras > $5,000', value: true, desc: 'Requiere aprobación de gerente para compras mayores al umbral' },
              { label: 'Contabilización automática', value: true, desc: 'Genera asientos contables automáticamente al facturar' },
              { label: 'Bloqueo de períodos cerrados', value: true, desc: 'Impide modificar documentos de períodos ya cerrados' },
              { label: 'Validación de segregación de funciones', value: true, desc: 'Un usuario no puede aprobar sus propias operaciones' },
              { label: 'Notificaciones por email', value: true, desc: 'Enviar alertas y notificaciones al correo del usuario' },
            ].map((param, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <p className="text-sm font-medium">{param.label}</p>
                  <p className="text-xs text-gray-500">{param.desc}</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" className="sr-only peer" defaultChecked={param.value} />
                  <div className="w-9 h-5 bg-gray-300 peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                </label>
              </div>
            ))}
          </div>
        </div>

        {/* Data Management */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold mb-4 flex items-center gap-2"><Database size={18} /> Gestión de Datos</h2>
          <div className="space-y-3">
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Base de datos</p>
                  <p className="text-xs text-gray-500">PostgreSQL 15 | Tamaño: 245 MB</p>
                </div>
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs">Conectada</span>
              </div>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">Último backup</p>
                  <p className="text-xs text-gray-500">2024-11-26 03:00 AM | Tamaño: 180 MB</p>
                </div>
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-xs">OK</span>
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button className="flex items-center gap-2 bg-blue-600 text-white px-3 py-2 rounded-lg text-sm hover:bg-blue-700">
                <Database size={14} /> Backup Manual
              </button>
              <button className="flex items-center gap-2 border border-gray-300 px-3 py-2 rounded-lg text-sm hover:bg-gray-50">
                <RefreshCw size={14} /> Verificar Integridad
              </button>
            </div>
          </div>

          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertTriangle size={14} className="text-amber-600 mt-0.5" />
              <p className="text-xs text-amber-700">
                <strong>Ambiente de desarrollo:</strong> Los datos son sintéticos y se almacenan en localStorage del navegador.
                Para producción, configurar PostgreSQL y el backend FastAPI según la documentación de despliegue.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

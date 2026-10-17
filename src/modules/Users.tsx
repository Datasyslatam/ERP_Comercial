import { store } from '../store';
import { Users, Shield, Key, Clock, Plus, Edit, Lock } from 'lucide-react';

export default function UsersModule() {
  const users = store.getUsers();
  const auditLogs = store.getAuditLogs();

  const roleLabels: Record<string, string> = {
    admin: 'Administrador', manager: 'Gerente', accountant: 'Contador',
    warehouse: 'Almacén', purchasing: 'Compras', quality: 'Calidad',
    logistics: 'Logística', production: 'Producción', viewer: 'Consulta',
  };

  const rolePermissions: Record<string, string[]> = {
    admin: ['Todos los permisos'],
    manager: ['Dashboard', 'Reportes', 'Aprobaciones', 'Consulta todos los módulos'],
    accountant: ['Contabilidad', 'Facturación', 'CxC', 'CxP', 'Reportes financieros'],
    warehouse: ['Inventario', 'Movimientos', 'Recepciones', 'Despachos'],
    purchasing: ['Compras', 'Proveedores', 'Solicitudes', 'Órdenes de compra'],
    quality: ['Inspecciones', 'No conformidades', 'Planes de calidad'],
    logistics: ['Despachos', 'Transportistas', 'Seguimiento'],
    production: ['Órdenes de trabajo', 'Consumos', 'Avance de producción'],
    viewer: ['Consulta (solo lectura) en todos los módulos'],
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Administración de Usuarios y Seguridad</h1>
          <p className="text-sm text-gray-500 mt-1">Roles, permisos, segregación de funciones y auditoría</p>
        </div>
        <button className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm">
          <Plus size={16} /> Nuevo Usuario
        </button>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Usuarios del Sistema</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Usuario</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Nombre Completo</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Email</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Rol</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Sede</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Estado</th>
                <th className="text-left px-4 py-3 font-medium text-gray-500">Último Acceso</th>
                <th className="text-center px-4 py-3 font-medium text-gray-500">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map(user => {
                const branch = store.getBranch(user.branchId);
                return (
                  <tr key={user.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{user.username}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 bg-blue-100 rounded-full flex items-center justify-center text-xs font-medium text-blue-600">
                          {user.fullName.split(' ').map(n => n[0]).join('').slice(0, 2)}
                        </div>
                        {user.fullName}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">{roleLabels[user.role]}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{branch?.name || 'N/A'}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${user.active ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {user.active ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{user.lastLogin ? new Date(user.lastLogin).toLocaleString() : 'Nunca'}</td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button className="p-1 text-blue-600 hover:bg-blue-50 rounded"><Edit size={14} /></button>
                        <button className="p-1 text-amber-600 hover:bg-amber-50 rounded"><Key size={14} /></button>
                        <button className="p-1 text-red-600 hover:bg-red-50 rounded"><Lock size={14} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Roles & Permissions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold mb-4 flex items-center gap-2"><Shield size={18} /> Matriz de Roles y Permisos</h3>
          <div className="space-y-2">
            {Object.entries(rolePermissions).map(([role, perms]) => (
              <div key={role} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">{roleLabels[role]}</span>
                </div>
                <p className="text-xs text-gray-600">{perms.join(' • ')}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Audit Log */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold mb-4 flex items-center gap-2"><Clock size={18} /> Registro de Auditoría (Últimos eventos)</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {auditLogs.slice(0, 15).map(log => {
              const user = store.getUser(log.userId);
              return (
                <div key={log.id} className="p-2 border-b border-gray-50 last:border-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-700">{user?.fullName || log.userId}</span>
                    <span className="text-xs text-gray-400">{new Date(log.timestamp).toLocaleString()}</span>
                  </div>
                  <p className="text-xs text-gray-600 mt-0.5">
                    <span className="px-1 bg-gray-100 rounded">{log.action}</span> en {log.module} — {log.details}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Security Policies */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-semibold mb-4">Políticas de Seguridad Implementadas</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {[
            { policy: 'Segregación de funciones', desc: 'Ningún usuario puede aprobar su propia operación', status: 'active' },
            { policy: 'Contraseñas seguras', desc: 'Mínimo 8 caracteres, complejidad requerida', status: 'active' },
            { policy: 'Sesiones con expiración', desc: 'Timeout automático después de 30 min inactividad', status: 'active' },
            { policy: 'Intentos de acceso limitados', desc: 'Bloqueo tras 5 intentos fallidos', status: 'active' },
            { policy: 'HTTPS obligatorio', desc: 'Todas las comunicaciones cifradas TLS 1.3', status: 'active' },
            { policy: 'Auditoría completa', desc: 'Registro de todas las acciones sensibles', status: 'active' },
            { policy: 'Protección CSRF', desc: 'Tokens de validación en formularios', status: 'active' },
            { policy: 'Rate limiting', desc: 'Límite de 100 requests/min por usuario', status: 'active' },
            { policy: 'Backups automáticos', desc: 'Copia diaria con retención de 30 días', status: 'active' },
          ].map((item, i) => (
            <div key={i} className="flex items-start gap-2 p-3 bg-emerald-50 rounded-lg">
              <div className="w-2 h-2 mt-1.5 bg-emerald-500 rounded-full flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-gray-700">{item.policy}</p>
                <p className="text-xs text-gray-500">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

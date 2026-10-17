import { useState } from 'react';
import { store } from '../store';
import type { User } from '../types';
import { Lock, User as UserIcon, AlertCircle } from 'lucide-react';

interface LoginProps {
  onLogin: (user: User) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    setTimeout(() => {
      const user = store.authenticate(username, password);
      if (user) {
        store.addAuditLog({
          userId: user.id, action: 'LOGIN', module: 'auth',
          entityId: user.id, entityType: 'user',
          details: 'Inicio de sesión exitoso', timestamp: new Date().toISOString(),
          ipAddress: '192.168.1.100'
        });
        onLogin(user);
      } else {
        setError('Credenciales inválidas. Verifique usuario y contraseña.');
      }
      setLoading(false);
    }, 500);
  };

  const demoUsers = store.getUsers().filter(u => u.active);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-2xl">DS</span>
          </div>
          <h1 className="text-2xl font-bold text-white">DATASYS LATAM GROUP</h1>
          <p className="text-blue-200 text-sm mt-1">ERP Enterprise System</p>
        </div>

        {/* Login Form */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-1">Iniciar Sesión</h2>
          <p className="text-sm text-gray-500 mb-6">Ingrese sus credenciales para acceder al sistema</p>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg mb-4">
              <AlertCircle size={16} className="text-red-500" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
              <div className="relative">
                <UserIcon size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  className="w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="Ingrese su usuario"
                  required
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full pl-10 pr-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="Ingrese su contraseña"
                  required
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium text-sm hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {loading ? 'Verificando...' : 'Ingresar al Sistema'}
            </button>
          </form>

          {/* Demo Users */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <p className="text-xs text-gray-500 mb-3 font-medium">Usuarios de demostración (cualquier contraseña):</p>
            <div className="grid grid-cols-2 gap-2">
              {demoUsers.slice(0, 6).map(user => (
                <button
                  key={user.id}
                  onClick={() => { setUsername(user.username); setPassword('demo'); }}
                  className="text-left p-2 rounded-lg border border-gray-200 hover:bg-blue-50 hover:border-blue-300 transition-colors"
                >
                  <p className="text-xs font-medium text-gray-700">{user.fullName}</p>
                  <p className="text-xs text-gray-500">{user.username} • {user.role}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Environment Notice */}
        <div className="mt-4 text-center">
          <p className="text-xs text-blue-200/70">
            Ambiente de desarrollo • Datos sintéticos • No usar en producción
          </p>
          <p className="text-xs text-blue-200/50 mt-1">
            DATASYS LATAM GROUP © 2024 — ERP v1.0.0-dev
          </p>
        </div>
      </div>
    </div>
  );
}

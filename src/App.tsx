import { useState, useEffect } from 'react';
import type { User } from './types';
import { store } from './store';
import Login from './components/Login';
import Layout from './components/Layout';
import Dashboard from './modules/Dashboard';
import Purchasing from './modules/Purchasing';
import Inventory from './modules/Inventory';
import Production from './modules/Production';
import Accounting from './modules/Accounting';
import Invoicing from './modules/Invoicing';
import Quality from './modules/Quality';
import Logistics from './modules/Logistics';
import UsersModule from './modules/Users';
import Reports from './modules/Reports';
import ImportData from './modules/ImportData';
import Settings from './modules/Settings';

function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [currentModule, setCurrentModule] = useState('dashboard');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedUser = localStorage.getItem('datasys_erp_session');
    if (savedUser) {
      try {
        const user = JSON.parse(savedUser);
        setCurrentUser(user);
      } catch {
        localStorage.removeItem('datasys_erp_session');
      }
    }
    setLoading(false);
  }, []);

  const handleLogin = (user: User) => {
    setCurrentUser(user);
    localStorage.setItem('datasys_erp_session', JSON.stringify(user));
  };

  const handleLogout = () => {
    setCurrentUser(null);
    localStorage.removeItem('datasys_erp_session');
    setCurrentModule('dashboard');
  };

  const handleNavigate = (module: string) => {
    setCurrentModule(module);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center mx-auto mb-4 animate-pulse">
            <span className="text-white font-bold">DS</span>
          </div>
          <p className="text-blue-200 text-sm">Cargando sistema...</p>
        </div>
      </div>
    );
  }

  const renderModule = () => {
    switch (currentModule) {
      case 'dashboard': return <Dashboard />;
      case 'purchasing': return <Purchasing />;
      case 'inventory': return <Inventory />;
      case 'production': return <Production />;
      case 'accounting': return <Accounting />;
      case 'invoicing': return <Invoicing />;
      case 'quality': return <Quality />;
      case 'logistics': return <Logistics />;
      case 'users': return <UsersModule />;
      case 'reports': return <Reports />;
      case 'import': return <ImportData />;
      case 'settings': return <Settings />;
      default: return <Dashboard />;
    }
  };

  if (!currentUser) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <Layout currentUser={currentUser} onLogout={handleLogout} currentModule={currentModule} onNavigate={handleNavigate}>
      {renderModule()}
    </Layout>
  );
}

export default App;

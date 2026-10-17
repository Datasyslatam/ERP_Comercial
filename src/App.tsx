import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing session
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

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={currentUser ? <Navigate to="/dashboard" /> : <Login onLogin={handleLogin} />} />
        
        {currentUser ? (
          <>
            <Route path="/dashboard" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Dashboard /></Layout>} />
            <Route path="/purchasing" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Purchasing /></Layout>} />
            <Route path="/inventory" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Inventory /></Layout>} />
            <Route path="/production" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Production /></Layout>} />
            <Route path="/accounting" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Accounting /></Layout>} />
            <Route path="/invoicing" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Invoicing /></Layout>} />
            <Route path="/quality" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Quality /></Layout>} />
            <Route path="/logistics" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Logistics /></Layout>} />
            <Route path="/users" element={<Layout currentUser={currentUser} onLogout={handleLogout}><UsersModule /></Layout>} />
            <Route path="/reports" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Reports /></Layout>} />
            <Route path="/import" element={<Layout currentUser={currentUser} onLogout={handleLogout}><ImportData /></Layout>} />
            <Route path="/settings" element={<Layout currentUser={currentUser} onLogout={handleLogout}><Settings /></Layout>} />
            <Route path="*" element={<Navigate to="/dashboard" />} />
          </>
        ) : (
          <Route path="*" element={<Navigate to="/login" />} />
        )}
      </Routes>
    </BrowserRouter>
  );
}

export default App;

import { useEffect, useState } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { LogOut, Trash2 } from 'lucide-react';
import { useDebate } from './context/DebateContext';
import { apiFetch } from './utils/api';
import DebateArena from './components/DebateArena';
import ControlBar from './components/ControlBar';
import ScorecardOverlay from './components/ScorecardOverlay';
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/AdminDashboard';

function Arena() {
  const { connect, connectionStatus, disconnect } = useDebate();
  const [role, setRole] = useState(sessionStorage.getItem('pitchsense_user_role') || 'customer');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const navigate = useNavigate();

  // Verify auth state from the SERVER on mount (not sessionStorage)
  useEffect(() => {
    apiFetch('/api/auth-check/')
      .then(data => {
        if (data.status === 'success') {
          const serverRole = data.user.is_admin ? 'admin' : 'customer';
          sessionStorage.setItem('pitchsense_user_role', serverRole);
          setRole(serverRole);
        } else {
          // Not authenticated — kick to login
          sessionStorage.clear();
          navigate('/');
        }
      })
      .catch(() => {
        sessionStorage.clear();
        navigate('/');
      });
  }, [navigate]);

  useEffect(() => {
    connect();
  }, [connect]);

  const handleLogout = async () => {
    try {
      await apiFetch('/api/logout/', { method: 'POST' });
    } catch (e) {
      console.error('Logout failed', e);
    }
    sessionStorage.clear();
    disconnect();
    navigate('/');
  };

  const handleDeleteAccount = async () => {
    try {
      const data = await apiFetch('/api/delete-account/', { method: 'POST' });
      if (data.status === 'success') {
        sessionStorage.clear();
        disconnect();
        navigate('/');
      }
    } catch (e) {
      console.error('Delete failed', e);
    }
  };

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden font-sans" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Header */}
      <header className="flex-none h-14 flex items-center px-5 sticky top-0 z-20"
        style={{ background: 'rgba(7,7,15,0.9)', backdropFilter: 'blur(20px)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center shadow-lg"
            style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)', boxShadow: '0 0 16px rgba(99,102,241,0.4)' }}>
            <span className="text-white text-sm font-black leading-none">P</span>
          </div>
          <h1 className="text-base font-bold tracking-tight text-white">
            Pitch<span className="text-indigo-400 font-extrabold">Sense</span>
          </h1>
          {role === 'admin' && (
            <span className="text-[9px] uppercase font-black tracking-widest px-2 py-0.5 rounded"
              style={{ background: 'rgba(244,63,94,0.15)', color: '#f87171', border: '1px solid rgba(244,63,94,0.25)' }}>
              Admin
            </span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {role === 'admin' && (
            <button onClick={() => navigate('/admin-dashboard')}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all text-gray-300 hover:text-white"
              style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}>
              Dashboard
            </button>
          )}
          <button
            onClick={() => { sessionStorage.removeItem('pitchsense_session_id'); connect(crypto.randomUUID()); }}
            className="text-xs font-bold px-3 py-1.5 rounded-lg text-white transition-all"
            style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)', boxShadow: '0 0 12px rgba(99,102,241,0.25)' }}>
            + New Pitch
          </button>
          <button onClick={handleLogout}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg transition-all"
            style={{ background: 'rgba(244,63,94,0.08)', color: '#f87171', border: '1px solid rgba(244,63,94,0.2)' }}>
            Logout
          </button>
          <div className={`flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full
            ${connectionStatus === 'connected' ? 'text-emerald-400' : connectionStatus === 'error' ? 'text-red-400' : 'text-amber-400'}`}
            style={{ background: connectionStatus === 'connected' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)' }}>
            <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${connectionStatus === 'connected' ? 'bg-emerald-400' : connectionStatus === 'error' ? 'bg-red-400' : 'bg-amber-400'}`} />
            {connectionStatus === 'connected' ? 'Live' : connectionStatus.toUpperCase()}
          </div>
        </div>
      </header>


      {/* Main Arena */}
      <DebateArena />

      {/* Bottom Controls */}
      <ControlBar />

      {/* Final Scorecard */}
      <ScorecardOverlay />

      {/* Delete Account Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-[#111118] border border-white/10 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
            <h2 className="text-xl font-black text-white mb-2">Delete Account?</h2>
            <p className="text-gray-400 text-sm mb-6">This will permanently destroy your account and all pitch transcripts. This action cannot be undone.</p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 text-white font-bold text-sm border border-white/10 hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                className="flex-1 px-4 py-2.5 rounded-xl bg-red-600 text-white font-bold text-sm hover:bg-red-500 transition-colors flex items-center justify-center gap-2"
              >
                <Trash2 size={14} />
                Delete Forever
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/login" element={<Navigate to="/" replace />} />
      <Route path="/debate" element={<Arena />} />
      <Route path="/admin-dashboard" element={<AdminDashboard />} />
      {/* Catch all to login */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

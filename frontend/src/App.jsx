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
    <div className="h-screen w-full flex flex-col bg-[var(--bg-primary)] overflow-hidden font-sans text-[var(--text-primary)]">
      {/* Header */}
      <header className="flex-none h-16 border-b border-[var(--border-default)] bg-[#0a0a0f]/80 backdrop-blur-md flex items-center px-6 sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.4)]">
            <span className="text-white text-lg font-black leading-none pb-0.5">P</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight">Pitch<span className="text-indigo-400 font-extrabold">Sense</span></h1>
          {role === 'admin' && (
            <span className="ml-2 text-[10px] uppercase font-black tracking-widest bg-red-500/20 text-red-400 px-2 py-0.5 rounded border border-red-500/30">Admin Mode</span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-3">
          {role === 'admin' && (
            <button
              onClick={() => navigate('/admin-dashboard')}
              className="text-xs font-bold px-3 py-1.5 rounded-lg bg-[#2d2d3d] hover:bg-[#3d3d4d] text-white transition-colors"
            >
              Dashboard
            </button>
          )}
          <button
            onClick={() => {
              sessionStorage.removeItem('pitchsense_session_id');
              connect(crypto.randomUUID());
            }}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
          >
            + New Pitch
          </button>
          <button
            onClick={handleLogout}
            className="text-xs font-bold px-3 py-1.5 rounded-lg bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-500/20 transition-colors flex items-center gap-1.5"
            title="Log out"
          >
            <LogOut size={14} />
            Logout
          </button>
          <span className={`text-xs font-semibold px-2 py-1 rounded-full flex items-center gap-1.5 ml-1
            ${connectionStatus === 'connected' ? 'text-emerald-400 bg-emerald-400/10' : 
              connectionStatus === 'error' ? 'text-red-400 bg-red-400/10' : 'text-amber-400 bg-amber-400/10'}`}>
            <span className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-emerald-400' : connectionStatus === 'error' ? 'bg-red-400' : 'bg-amber-400'} animate-pulse`}></span>
            {connectionStatus.toUpperCase()}
          </span>
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

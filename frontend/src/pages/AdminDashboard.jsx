import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, ArrowLeft, RefreshCw, Activity, Users, Database, LogOut } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchSessions = async () => {
    setIsLoading(true);
    try {
      const data = await apiFetch('/api/admin/sessions/');
      if (data.status === 'success') {
        setSessions(data.sessions);
      } else {
        console.error(data.message);
        if (data.message === 'Unauthorized') navigate('/');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Verify admin auth from server on mount
    apiFetch('/api/auth-check/')
      .then(data => {
        if (data.status !== 'success' || !data.user.is_admin) {
          sessionStorage.clear();
          navigate('/');
        } else {
          fetchSessions();
        }
      })
      .catch(() => {
        sessionStorage.clear();
        navigate('/');
      });
  }, []);

  const handleLogout = async () => {
    try {
      await apiFetch('/api/logout/', { method: 'POST' });
    } catch (e) {
      console.error('Logout failed', e);
    }
    sessionStorage.clear();
    navigate('/');
  };

  return (
    <div className="min-h-screen w-full bg-[#0a0a0f] text-white p-8 font-sans">
      <div className="max-w-6xl mx-auto">
        
        {/* Header */}
        <div className="flex items-center justify-between mb-12 animate-in fade-in slide-in-from-top-4">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/debate')}
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-3xl font-black tracking-tight flex items-center gap-3">
                <Shield className="text-indigo-500" />
                Admin <span className="text-indigo-400">Command</span>
              </h1>
              <p className="text-gray-400 text-sm mt-1">PitchSense Global Intelligence Network</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button 
              onClick={fetchSessions}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-600/30 transition-colors text-sm font-bold tracking-wide"
            >
              <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
              Sync Database
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-500/20 transition-colors text-sm font-bold tracking-wide"
              title="Log out"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10 animate-in fade-in slide-in-from-bottom-4 delay-100">
          <div className="bg-[#111118] border border-white/10 p-6 rounded-2xl flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400">
              <Database size={24} />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-bold uppercase tracking-wider">Total Pitches</p>
              <h3 className="text-3xl font-black">{sessions.length}</h3>
            </div>
          </div>
          <div className="bg-[#111118] border border-white/10 p-6 rounded-2xl flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Activity size={24} />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-bold uppercase tracking-wider">Active Sessions</p>
              <h3 className="text-3xl font-black">{sessions.filter(s => s.status === 'active').length}</h3>
            </div>
          </div>
          <div className="bg-[#111118] border border-white/10 p-6 rounded-2xl flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400">
              <Users size={24} />
            </div>
            <div>
              <p className="text-gray-400 text-sm font-bold uppercase tracking-wider">Unique Customers</p>
              <h3 className="text-3xl font-black">{new Set(sessions.map(s => s.username)).size}</h3>
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="bg-[#111118] border border-white/10 rounded-2xl overflow-hidden shadow-2xl animate-in fade-in slide-in-from-bottom-8 delay-200">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/5 bg-white/5">
                  <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Session ID</th>
                  <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Customer</th>
                  <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider">Status</th>
                  <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-center">Turn</th>
                  <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-center">Scorecard</th>
                  <th className="p-4 text-xs font-bold text-gray-400 uppercase tracking-wider text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && sessions.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="p-8 text-center text-gray-500">Decrypting streams...</td>
                  </tr>
                ) : sessions.map(session => (
                  <tr key={session.id} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                    <td className="p-4 text-sm font-mono text-gray-400">{session.id.split('-')[0]}...</td>
                    <td className="p-4 font-bold">{session.username}</td>
                    <td className="p-4">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-bold tracking-wider ${
                        session.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                        session.status === 'active' ? 'bg-blue-500/10 text-blue-400 animate-pulse' :
                        'bg-gray-500/10 text-gray-400'
                      }`}>
                        {session.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-4 text-center font-black text-gray-300">{session.current_turn}</td>
                    <td className="p-4 text-center">
                      {session.scorecard ? '✅' : '❌'}
                    </td>
                    <td className="p-4 text-right">
                      <button 
                        onClick={() => {
                          sessionStorage.setItem('pitchsense_session_id', session.id);
                          navigate('/debate');
                        }}
                        className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1.5 rounded-lg font-bold transition-colors"
                      >
                        Hijack Session
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
